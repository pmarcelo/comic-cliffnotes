import streamlit as st
import pandas as pd
import sys
import os
import uuid
import json  # 🎯 Required for JSONB context
import subprocess
from sqlalchemy import text
from core.extractors.discovery import sync_series_by_id

# We import the model list to keep the selection in sync with the sidebar
from ui.sidebar import AVAILABLE_MODELS

def run_synchronously(cmd_list, cwd):
    """
    Runs a shell command and yields output line-by-line for Streamlit to render.
    Enforces utf-8 encoding and fail-safe character replacement.
    """
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(cwd)}
    
    process = subprocess.Popen(
        cmd_list,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        bufsize=1,
        universal_newlines=True
    )

    for line in process.stdout:
        yield line.strip()
        
    process.wait()
    
    if process.returncode != 0:
        raise Exception(f"Process failed with exit code {process.returncode}")

@st.cache_data(ttl=60) # Cache for 1 minute to prevent flicker
def fetch_series_index(_engine):
    """Cached database query for the main index with granular progress tracking."""
    query = text("""
        SELECT 
            s.id, s.title, s.created_at, ss.url as primary_source,
            COUNT(c.id) as total_chapters,
            COALESCE(SUM(CASE WHEN cp.is_extracted THEN 1 ELSE 0 END), 0) as extracted_done,
            COALESCE(SUM(CASE WHEN cp.ocr_extracted THEN 1 ELSE 0 END), 0) as ocr_done,
            COALESCE(SUM(CASE WHEN cp.summary_complete THEN 1 ELSE 0 END), 0) as summaries_done,
            COALESCE(SUM(CASE WHEN cp.has_error THEN 1 ELSE 0 END), 0) as errors
        FROM series s
        LEFT JOIN series_sources ss ON s.id = ss.series_id AND ss.priority = 1
        LEFT JOIN chapters c ON s.id = c.series_id
        LEFT JOIN chapter_processing cp ON c.id = cp.chapter_id
        GROUP BY s.id, s.title, s.created_at, ss.url
        ORDER BY s.created_at DESC
    """)
    return pd.read_sql(query, _engine)

def highlight_discrepancies(row):
    """Styles the dataframe to show progress gaps based on pipeline order."""
    styles = [''] * len(row)
    if row['total_chapters'] == 0:
        return styles

    # 1. Highlight missing local images (Red)
    if row['extracted_done'] < row['total_chapters']:
        idx = row.index.get_loc('extracted_done')
        styles[idx] = 'background-color: rgba(231, 76, 60, 0.2);' 
    # 2. Highlight missing OCR (Yellow)
    elif row['ocr_done'] < row['total_chapters']:
        idx = row.index.get_loc('ocr_done')
        styles[idx] = 'background-color: rgba(241, 196, 15, 0.2);' 
    # 3. Highlight missing Summaries (Blue)
    elif row['summaries_done'] < row['total_chapters']:
        idx = row.index.get_loc('summaries_done')
        styles[idx] = 'background-color: rgba(52, 152, 219, 0.2);'
    return styles

@st.fragment
def render_index(engine, root_path):
    """
    The main fragment for Tab 1. 
    Selection and Actions here will NOT flicker the sidebar.
    """
    col_header, col_ref = st.columns([5, 1])
    with col_header:
        st.subheader("Library Status")
    with col_ref:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun(scope="fragment")

    df = fetch_series_index(engine)
    
    if df.empty:
        st.info("No series found in database yet.")
        return

    df['id'] = df['id'].astype(str)

    # 🎯 Series-Level Metrics
    m_col1, m_col2, m_col3 = st.columns(3)
    total_series = len(df)
    series_extracted = len(df[(df['extracted_done'] >= df['total_chapters']) & (df['total_chapters'] > 0)])
    series_summarized = len(df[(df['summaries_done'] >= df['total_chapters']) & (df['total_chapters'] > 0)])

    m_col1.metric("Library Size", f"{total_series} Series")
    m_col2.metric("Fully Extracted", f"{series_extracted} Series")
    m_col3.metric("Summaries Done", f"{series_summarized} Series")

    # 2. The Interactive Table
    event = st.dataframe(
        df.style.apply(highlight_discrepancies, axis=1),
        column_config={
            "id": None,
            "title": "Series Title",
            "created_at": st.column_config.DatetimeColumn("Added On", format="D MMM YYYY, h:mm a"),
            "primary_source": st.column_config.LinkColumn("Source URL"),
            "total_chapters": "Total",
            "extracted_done": "Images 📥",
            "ocr_done": "OCR ✅",
            "summaries_done": "Summaries 📝",
            "errors": st.column_config.NumberColumn("Errors ⚠️", format="%d")
        },
        width="stretch",
        height=450,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="index_table_widget" 
    )

    # 3. Row Selection & Management
    if len(event.selection.rows) > 0:
        selected_row = df.iloc[event.selection.rows[0]]
        
        st.session_state.selected_series_id = selected_row['id']
        st.session_state.selected_series_title = selected_row['title']

        st.divider()
        with st.container(border=True):
            st.subheader(f"⚡ Manage: {selected_row['title']}")
            
            # Edit Metadata
            edit_col1, edit_col2 = st.columns(2)
            new_title = edit_col1.text_input("Edit Title", value=selected_row['title'])
            new_url = edit_col2.text_input("Edit Source URL", value=selected_row['primary_source'] or "")

            if st.button("💾 Save Metadata Changes", type="primary"):
                try:
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE series SET title = :t, updated_at = now() WHERE id = :id"), {"t": new_title, "id": selected_row['id']})
                        exists = conn.execute(text("SELECT id FROM series_sources WHERE series_id = :id AND priority = 1"), {"id": selected_row['id']}).fetchone()
                        if exists:
                            conn.execute(text("UPDATE series_sources SET url = :url, updated_at = now() WHERE id = :s_id"), {"url": new_url, "s_id": exists[0]})
                    
                    st.cache_data.clear()
                    st.success("Saved!")
                    st.rerun(scope="fragment")
                except Exception as e:
                    st.error(f"Error: {e}")

            st.divider()
            
            # Helper Functions for Actions
            def queue_task(action, context=None):
                try:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO processing_queue (
                                id, series_id, action, status, priority, context, created_at, updated_at
                            )
                            VALUES (
                                :uuid, :s_id, :action, 'PENDING'::queuestatus, 10, :context, now(), now()
                            )
                        """), {
                            "uuid": str(uuid.uuid4()),
                            "s_id": selected_row['id'],
                            "action": action,
                            "context": json.dumps(context) if context else None
                        })
                    st.toast(f"✅ Queued {action.upper()} for {selected_row['title']}")
                except Exception as e:
                    st.error(f"Failed to queue task: {e}")

            def run_now_task(action, series_id, series_title, cwd_path, context=None):
                task_id = str(uuid.uuid4())
                try:
                    # 1. Insert RUNNING "Ghost Task"
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO processing_queue (
                                id, series_id, action, status, priority, context, created_at, updated_at
                            )
                            VALUES (
                                :uuid, :s_id, :action, 'RUNNING'::queuestatus, 10, :context, now(), now()
                            )
                        """), {
                            "uuid": task_id,
                            "s_id": series_id,
                            "action": action,
                            "context": json.dumps(context) if context else None
                        })

                    # 2. Prepare Command
                    cmd = [sys.executable, "processor.py", "-t", series_title]
                    if action == "extract": cmd.append("--extract")
                    elif action == "ocr": cmd.append("--ocr")
                    elif action == "summary": cmd.append("--summarize")
                    elif action == "full": cmd.extend(["--extract", "--ocr", "--summarize"])
                    
                    if context and "model" in context and action in ["summary", "full"]:
                        cmd.extend(["--model", context["model"]])

                    # 3. UI Streaming
                    st.write(f"### Live Execution Logs: {action.upper()}")
                    log_container = st.empty()
                    log_lines = []

                    with st.spinner("Processing in real-time..."):
                        for line in run_synchronously(cmd, cwd_path):
                            if line:
                                log_lines.append(f"> {line}")
                                log_container.code("\n".join(log_lines[-15:]), language="shell")

                    # 4. Mark Completed
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE processing_queue SET status = 'COMPLETED'::queuestatus, updated_at = now() WHERE id = :id"), {"id": task_id})
                    
                    st.cache_data.clear()
                    st.success(f"Successfully completed {action.upper()}!")
                    
                except Exception as e:
                    # Mark Failed
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE processing_queue SET status = 'FAILED'::queuestatus, updated_at = now() WHERE id = :id"), {"id": task_id})
                    st.error(f"Execution Failed: {e}")


            # --- Action Panel ---
            st.caption("Trigger Pipeline Actions")
            q_model = st.session_state.get("sidebar_model_select", AVAILABLE_MODELS[0])
            
            # Top-level scan (Synchronous only, no queue needed)
            if st.button("🔍 Scan for New Chapters", use_container_width=True, disabled=not selected_row['primary_source']):
                with st.spinner("Scouting..."):
                    sync_series_by_id(selected_row['id'])
                st.cache_data.clear()
                st.rerun(scope="fragment")

            st.write("") # Spacer

            # Action Grid Configuration
            pipeline_actions = [
                ("extract", "📥 Extract Images", None),
                ("ocr", "📷 OCR Panels", None),
                ("summary", "📝 Generate Summaries", {"model": q_model}),
                ("full", "🔄 Full Pipeline", {"model": q_model})
            ]

            # Render structured rows for each pipeline action
            for act_key, act_label, act_ctx in pipeline_actions:
                col_label, col_q, col_run = st.columns([2, 1, 1])
                
                # Align text vertically with the buttons
                with col_label:
                    st.write(f"**{act_label}**")
                
                if col_q.button("Add to Queue", key=f"q_{act_key}_{selected_row['id']}", use_container_width=True):
                    queue_task(act_key, context=act_ctx)
                
                if col_run.button("Run Now", type="primary", key=f"run_{act_key}_{selected_row['id']}", use_container_width=True):
                    run_now_task(act_key, selected_row['id'], selected_row['title'], root_path, context=act_ctx)


            # 🛠️ Maintenance / Danger Zone
            with st.expander("🛠️ Advanced / Maintenance"):
                st.warning("Destructive Actions: Resetting data will delete existing records.")
                reset_col1, reset_col2 = st.columns([3, 1])
                reset_input = reset_col1.text_input("Chapter Targets (e.g., 'all', '1-10', '25')", value="all", key=f"reset_field_{selected_row['id']}")
                
                if reset_col2.button("🗑️ Reset Summaries", use_container_width=True, type="secondary"):
                    cmd = [
                        sys.executable, "processor.py", 
                        "-t", selected_row['title'], 
                        "--reset-summaries", reset_input
                    ]
                    subprocess.run(cmd, env={"PYTHONPATH": str(root_path), **os.environ})
                    st.cache_data.clear()
                    st.success(f"Successfully reset summaries for: {reset_input}")
                    st.rerun(scope="fragment")
                
                st.divider()
                st.subheader("⚠️ Danger Zone")
                st.error("Deleting a series is permanent. This destroys all database records associated with the series.")

                delete_col1, delete_col2 = st.columns([3, 1])
                
                confirm_text = delete_col1.text_input(
                    "Type the series title exactly to confirm deletion:", 
                    placeholder=selected_row['title'],
                    key=f"del_confirm_{selected_row['id']}"
                )
                
                can_delete = confirm_text == selected_row['title']
                
                if delete_col2.button("🚨 Delete Series", use_container_width=True, disabled=not can_delete, type="primary"):
                    with st.spinner("Purging database records..."):
                        try:
                            # 1. Delete from DB (Relies on SQLAlchemy Cascades)
                            with engine.begin() as conn:
                                conn.execute(text("DELETE FROM series WHERE id = :id"), {"id": selected_row['id']})
                                
                            st.cache_data.clear()
                            st.success(f"Successfully deleted {selected_row['title']} from the database.")
                            st.session_state.selected_series_id = None
                            st.rerun(scope="fragment")
                        except Exception as e:
                            st.error(f"Failed to delete series: {e}")