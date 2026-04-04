import streamlit as st
import pandas as pd
import sys
import os
import uuid
import subprocess
from sqlalchemy import text
from core.extractors.discovery import sync_series_by_id

# We import the model list to keep the selection in sync with the sidebar
from ui.sidebar import AVAILABLE_MODELS

@st.cache_data(ttl=60) # Cache for 1 minute to prevent flicker
def fetch_series_index(_engine):
    """Cached database query for the main index."""
    query = text("""
        SELECT 
            s.id, s.title, s.created_at, ss.url as primary_source,
            COUNT(c.id) as total_chapters,
            SUM(CASE WHEN cp.ocr_extracted THEN 1 ELSE 0 END) as ocr_done,
            SUM(CASE WHEN cp.summary_complete THEN 1 ELSE 0 END) as summaries_done,
            SUM(CASE WHEN cp.has_error THEN 1 ELSE 0 END) as errors
        FROM series s
        LEFT JOIN series_sources ss ON s.id = ss.series_id AND ss.priority = 1
        LEFT JOIN chapters c ON s.id = c.series_id
        LEFT JOIN chapter_processing cp ON c.id = cp.chapter_id
        GROUP BY s.id, s.title, s.created_at, ss.url
        ORDER BY s.created_at DESC
    """)
    return pd.read_sql(query, _engine)

def highlight_discrepancies(row):
    """Styles the dataframe to show progress gaps."""
    styles = [''] * len(row)
    if row['ocr_done'] < row['total_chapters']:
        idx = row.index.get_loc('ocr_done')
        styles[idx] = 'background-color: rgba(241, 196, 15, 0.2);'
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

    # 1. Metric Overview
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Total Library", f"{len(df)} Series")
    m_col2.metric("Fully OCR'd", f"{len(df[df['ocr_done'] >= df['total_chapters']])}")
    m_col3.metric("Fully Summarized", f"{len(df[df['summaries_done'] >= df['total_chapters']])}")

    # 2. The Interactive Table
    # The 'key' ensures Streamlit remembers which row is selected during reruns
    event = st.dataframe(
        df.style.apply(highlight_discrepancies, axis=1),
        column_config={
            "id": None,
            "title": "Series Title",
            "created_at": st.column_config.DatetimeColumn("Added On", format="D MMM YYYY, h:mm a"),
            "primary_source": st.column_config.LinkColumn("Source URL"),
            "total_chapters": "Total",
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
        
        # Sync the selection to the global session state for Tab 2
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
                        # Check/Update Source
                        exists = conn.execute(text("SELECT id FROM series_sources WHERE series_id = :id AND priority = 1"), {"id": selected_row['id']}).fetchone()
                        if exists:
                            conn.execute(text("UPDATE series_sources SET url = :url, updated_at = now() WHERE id = :s_id"), {"url": new_url, "s_id": exists[0]})
                        else:
                            conn.execute(text("INSERT INTO series_sources (id, series_id, url, priority, created_at, updated_at) VALUES (:uuid, :id, :url, 1, now(), now())"), {"uuid": str(uuid.uuid4()), "id": selected_row['id'], "url": new_url})
                    
                    st.cache_data.clear() # Clear cache so table updates
                    st.success("Saved!")
                    st.rerun(scope="fragment")
                except Exception as e:
                    st.error(f"Error: {e}")

            st.divider()
            
            # Action Buttons
            st.caption("Trigger Pipeline Actions")
            # Pull the model from the sidebar's state so they match
            q_model = st.session_state.get("sidebar_model_select", AVAILABLE_MODELS[0])
            
            b1, b2, b3, b4 = st.columns(4)
            
            if b1.button("🔍 Scan", use_container_width=True, disabled=not selected_row['primary_source']):
                with st.spinner("Scouting..."):
                    sync_series_by_id(selected_row['id'])
                st.cache_data.clear()
                st.rerun(scope="fragment")

            if b2.button("📷 OCR", use_container_width=True):
                # 🎯 Updated to use smart auto-routing
                cmd = [
                    sys.executable, "processor.py", 
                    "-t", selected_row['title'], 
                    "--extract", 
                    "--model", q_model, 
                    "--ingest-method", "auto"
                ]
                subprocess.Popen(cmd, env={"PYTHONPATH": str(root_path), **os.environ})
                st.toast("OCR Started (Auto-detecting source)")

            if b3.button("📝 Summary", use_container_width=True):
                cmd = [sys.executable, "processor.py", "-t", selected_row['title'], "--summarize", "--model", q_model]
                subprocess.Popen(cmd, env={"PYTHONPATH": str(root_path), **os.environ})
                st.toast("Summary Started")

            if b4.button("🔄 Full", use_container_width=True):
                # 🎯 Updated to use smart auto-routing
                cmd = [
                    sys.executable, "processor.py", 
                    "-t", selected_row['title'], 
                    "--extract", "--summarize", 
                    "--model", q_model, 
                    "--ingest-method", "auto"
                ]
                subprocess.Popen(cmd, env={"PYTHONPATH": str(root_path), **os.environ})
                st.toast("Full Pipeline Started (Auto-detecting source)")