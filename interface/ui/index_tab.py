import streamlit as st
import pandas as pd
import sys
import os
import uuid
import json
import subprocess
from sqlalchemy import text
from core.extractors.discovery import sync_series_by_id

# Detect Mode
IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"

# Local-only imports
if not IS_ONLINE:
    from ui.sidebar import AVAILABLE_MODELS
else:
    AVAILABLE_MODELS = [] # Placeholder for cloud mode

def run_synchronously(cmd_list, cwd):
    """Local-only: Runs shell commands for real-time log streaming."""
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

@st.cache_data(ttl=60)
def fetch_series_index(_engine):
    """
    Cached database query. 
    🎯 HYBRID LOGIC: Cloud mode joins directly to 'summaries' since 
    'chapter_processing' metadata isn't synced to the cloud replica.
    """
    if IS_ONLINE:
        query = text("""
            SELECT 
                s.id, s.title, s.created_at, ss.url as primary_source,
                COUNT(c.id) as total_chapters,
                COUNT(summ.id) as summaries_done
            FROM series s
            LEFT JOIN series_sources ss ON s.id = ss.series_id AND ss.priority = 1
            LEFT JOIN chapters c ON s.id = c.series_id
            LEFT JOIN summaries summ ON c.id = summ.chapter_id
            GROUP BY s.id, s.title, s.created_at, ss.url
            ORDER BY s.created_at DESC
        """)
    else:
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
    """Styles the dataframe based on pipeline progress."""
    styles = [''] * len(row)
    if row['total_chapters'] == 0:
        return styles

    # Mobile/Cloud View: Just show green when 100% summarized
    if IS_ONLINE:
        if row['summaries_done'] >= row['total_chapters']:
            idx = row.index.get_loc('summaries_done')
            styles[idx] = 'background-color: rgba(46, 204, 113, 0.2);'
        return styles

    # Local View: Full pipeline status colors
    if row['extracted_done'] < row['total_chapters']:
        idx = row.index.get_loc('extracted_done')
        styles[idx] = 'background-color: rgba(231, 76, 60, 0.2);' 
    elif row['ocr_done'] < row['total_chapters']:
        idx = row.index.get_loc('ocr_done')
        styles[idx] = 'background-color: rgba(241, 196, 15, 0.2);' 
    elif row['summaries_done'] < row['total_chapters']:
        idx = row.index.get_loc('summaries_done')
        styles[idx] = 'background-color: rgba(52, 152, 219, 0.2);'
    return styles

@st.fragment
def render_index(engine, root_path):
    col_header, col_ref = st.columns([5, 1])
    with col_header:
        st.subheader("Library Status")
    with col_ref:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun(scope="fragment")

    df_raw = fetch_series_index(engine)
    if df_raw.empty:
        st.info("No series found in database yet.")
        return

    search_query = st.text_input("Search Library", placeholder="🔍 Filter by title...", label_visibility="collapsed")
    df = df_raw.copy()
    if search_query:
        df = df[df['title'].str.contains(search_query, case=False, na=False)]

    df['id'] = df['id'].astype(str)

    # Dynamic Metrics
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Series", f"{len(df)}")
    
    summarized_count = len(df[(df['summaries_done'] >= df['total_chapters']) & (df['total_chapters'] > 0)])
    m_col2.metric("Summaries Done", f"{summarized_count}")
    
    if not IS_ONLINE:
        extracted_count = len(df[(df['extracted_done'] >= df['total_chapters']) & (df['total_chapters'] > 0)])
        m_col3.metric("Images Local", f"{extracted_count}")
    else:
        m_col3.metric("Status", "Read-Only")

    # Table Configuration
    column_config = {
        "id": None,
        "title": "Series Title",
        "created_at": st.column_config.DatetimeColumn("Added", format="D MMM YYYY"),
        "primary_source": None if IS_ONLINE else st.column_config.LinkColumn("Source"),
        "total_chapters": "Total",
        "summaries_done": "Read ✅" if IS_ONLINE else "Summaries 📝"
    }
    
    if not IS_ONLINE:
        column_config.update({
            "extracted_done": "Images 📥",
            "ocr_done": "OCR ✅",
            "errors": st.column_config.NumberColumn("Errors ⚠️", format="%d")
        })

    event = st.dataframe(
        df.style.apply(highlight_discrepancies, axis=1),
        column_config=column_config,
        width="stretch",
        height=400 if IS_ONLINE else 450,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="index_table_widget" 
    )

    if len(event.selection.rows) > 0:
        selected_row = df.iloc[event.selection.rows[0]]
        st.session_state.selected_series_id = selected_row['id']
        st.session_state.selected_series_title = selected_row['title']

        if IS_ONLINE:
            st.success(f"Selected: **{selected_row['title']}**")
            st.info("📖 Switch to **Deep Dive** to read.")
        else:
            render_management_panel(engine, selected_row, root_path)

def render_management_panel(engine, selected_row, root_path):
    """Local-only dashboard controls."""
    st.divider()
    with st.container(border=True):
        st.subheader(f"⚡ Manage: {selected_row['title']}")
        
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
        
        # Action Helpers
        def queue_task(action, context=None):
            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO processing_queue (id, series_id, action, status, priority, context, created_at, updated_at)
                        VALUES (:uuid, :s_id, :action, 'PENDING'::queuestatus, 10, :context, now(), now())
                    """), {
                        "uuid": str(uuid.uuid4()),
                        "s_id": selected_row['id'],
                        "action": action,
                        "context": json.dumps(context) if context else None
                    })
                st.toast(f"✅ Queued {action.upper()}")
            except Exception as e:
                st.error(f"Failed to queue task: {e}")

        def run_now_task(action, series_id, series_title, cwd_path, context=None):
            task_id = str(uuid.uuid4())
            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO processing_queue (id, series_id, action, status, priority, context, created_at, updated_at)
                        VALUES (:uuid, :s_id, :action, 'RUNNING'::queuestatus, 10, :context, now(), now())
                    """), {"uuid": task_id, "s_id": series_id, "action": action, "context": json.dumps(context) if context else None})

                cmd = [sys.executable, "processor.py", "-t", series_title]
                if action == "extract": cmd.append("--extract")
                elif action == "ocr": cmd.append("--ocr")
                elif action == "summary": cmd.append("--summarize")
                elif action == "full": cmd.extend(["--extract", "--ocr", "--summarize"])
                
                if context and "model" in context and action in ["summary", "full"]:
                    cmd.extend(["--model", context["model"]])

                st.write(f"### Live Execution Logs: {action.upper()}")
                log_container = st.empty()
                log_lines = []

                with st.spinner("Processing..."):
                    for line in run_synchronously(cmd, cwd_path):
                        if line:
                            log_lines.append(f"> {line}")
                            log_container.code("\n".join(log_lines[-15:]), language="shell")

                with engine.begin() as conn:
                    conn.execute(text("UPDATE processing_queue SET status = 'COMPLETED'::queuestatus, updated_at = now() WHERE id = :id"), {"id": task_id})
                st.cache_data.clear()
                st.success(f"Completed {action.upper()}!")
            except Exception as e:
                with engine.begin() as conn:
                    conn.execute(text("UPDATE processing_queue SET status = 'FAILED'::queuestatus, updated_at = now() WHERE id = :id"), {"id": task_id})
                st.error(f"Failed: {e}")

        # Action Panel
        st.caption("Trigger Pipeline Actions")
        q_model = st.session_state.get("sidebar_model_select", AVAILABLE_MODELS[0] if AVAILABLE_MODELS else "")
        
        if st.button("🔍 Scan for New Chapters", use_container_width=True, disabled=not selected_row['primary_source']):
            with st.spinner("Scouting..."):
                sync_series_by_id(selected_row['id'])
            st.cache_data.clear()
            st.rerun(scope="fragment")

        pipeline_actions = [
            ("extract", "📥 Extract Images", None),
            ("ocr", "📷 OCR Panels", None),
            ("summary", "📝 Generate Summaries", {"model": q_model}),
            ("full", "🔄 Full Pipeline", {"model": q_model})
        ]

        for act_key, act_label, act_ctx in pipeline_actions:
            col_label, col_q, col_run = st.columns([2, 1, 1])
            col_label.write(f"**{act_label}**")
            if col_q.button("Add to Queue", key=f"q_{act_key}_{selected_row['id']}", use_container_width=True):
                queue_task(act_key, context=act_ctx)
            if col_run.button("Run Now", type="primary", key=f"run_{act_key}_{selected_row['id']}", use_container_width=True):
                run_now_task(act_key, selected_row['id'], selected_row['title'], root_path, context=act_ctx)

        # Danger Zone
        with st.expander("🛠️ Advanced / Maintenance"):
            st.warning("Destructive Actions below.")
            reset_col1, reset_col2 = st.columns([3, 1])
            reset_input = reset_col1.text_input("Chapters (all, 1-10)", value="all", key=f"reset_field_{selected_row['id']}")
            
            if reset_col2.button("🗑️ Reset", use_container_width=True):
                cmd = [sys.executable, "processor.py", "-t", selected_row['title'], "--reset-summaries", reset_input]
                subprocess.run(cmd, env={"PYTHONPATH": str(root_path), **os.environ})
                st.cache_data.clear()
                st.rerun(scope="fragment")
            
            st.divider()
            st.error("Permanent Deletion")
            delete_col1, delete_col2 = st.columns([3, 1])
            confirm_text = delete_col1.text_input("Confirm Title:", placeholder=selected_row['title'], key=f"del_confirm_{selected_row['id']}")
            if delete_col2.button("🚨 DELETE", use_container_width=True, disabled=(confirm_text != selected_row['title']), type="primary"):
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM series WHERE id = :id"), {"id": selected_row['id']})
                st.cache_data.clear()
                st.session_state.selected_series_id = None
                st.rerun(scope="fragment")