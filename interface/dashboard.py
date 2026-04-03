import sys
import os
import json
from pathlib import Path

# --- PATH FIX ---
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

import streamlit as st
import pandas as pd
import subprocess
from sqlalchemy import create_engine, text
from core import config
from core.utils import usage_tracker 

# --- UPDATED MODELS LIST ---
AVAILABLE_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash"
]

# --- PAGE CONFIG ---
st.set_page_config(page_title="Manga OS", layout="wide", initial_sidebar_state="expanded")

# --- DATABASE CONNECTION ---
engine = create_engine(config.DATABASE_URL)

# --- SESSION STATE INITIALIZATION ---
if 'selected_series' not in st.session_state:
    st.session_state.selected_series = None

# --- SIDEBAR: CONTROL PANEL ---
st.sidebar.header("🛠️ Pipeline Control")
with st.sidebar.form("run_processor"):
    st.write("Launch New Process")
    input_title = st.text_input("Series Title")
    input_url = st.text_input("GDrive URL (Optional if only summarizing)")
    starting_chapter = st.number_input("Starting Chapter", min_value=1, value=1)
    
    selected_model = st.selectbox("AI Model", AVAILABLE_MODELS, index=0)
    
    do_extract = st.checkbox("Extract & OCR", value=True)
    do_summarize = st.checkbox("Summarize", value=True)
    
    submit_btn = st.form_submit_button("🚀 Start Processor")

if submit_btn:
    url_needed_but_missing = do_extract and not input_url
    nothing_checked = not do_extract and not do_summarize
    
    if not input_title:
        st.sidebar.error("Series Title is required.")
    elif url_needed_but_missing:
        st.sidebar.error("GDrive URL is required for Extraction/OCR.")
    elif nothing_checked:
        st.sidebar.error("Please select at least one action.")
    else:
        python_path = sys.executable 
        cmd = [python_path, "processor.py", "-t", input_title, "-c", str(starting_chapter), "--model", selected_model]
        
        if input_url:
            cmd.extend(["-u", input_url])
        if do_extract: cmd.append("--extract")
        if do_summarize: cmd.append("--summarize")
        
        current_env = os.environ.copy()
        current_env["PYTHONPATH"] = str(root_path)
        
        subprocess.Popen(cmd, env=current_env) 
        st.sidebar.success(f"Started {input_title} using {selected_model}!")

# --- SIDEBAR: API USAGE TRACKER ---
st.sidebar.divider()
st.sidebar.header("📊 API Usage Tracker")

tracker_data = usage_tracker.get_today_tokens(selected_model)
used_tokens = tracker_data["used"]
DAILY_LIMIT = tracker_data["limit"]

st.sidebar.caption(f"Tier: {selected_model}")
st.sidebar.metric(label="Tokens Used Today", value=f"{used_tokens:,}")

remaining_pct = max(0, (DAILY_LIMIT - used_tokens) / DAILY_LIMIT)
st.sidebar.progress(remaining_pct)
st.sidebar.write(f"**Limit:** {used_tokens:,} / {DAILY_LIMIT:,}")

if st.sidebar.button("🔄 Refresh Usage"):
    st.rerun()

# --- MAIN CONTENT ---
st.title("📖 Manga Processing Dashboard")
tab_index, tab_details = st.tabs(["📚 Series Index", "🔍 Series Deep Dive"])

# --- TAB 1: SERIES INDEX ---
with tab_index:
    index_query = text("""
        SELECT 
            s.title,
            COUNT(c.id) as total_chapters,
            SUM(CASE WHEN cp.ocr_extracted THEN 1 ELSE 0 END) as ocr_done,
            SUM(CASE WHEN cp.summary_complete THEN 1 ELSE 0 END) as summaries_done,
            SUM(CASE WHEN cp.has_error THEN 1 ELSE 0 END) as errors
        FROM series s
        LEFT JOIN chapters c ON s.id = c.series_id
        LEFT JOIN chapter_processing cp ON c.id = cp.chapter_id
        GROUP BY s.title
        ORDER BY s.title ASC
    """)
    df_index = pd.read_sql(index_query, engine)

    # --- UPDATED: TOP LEVEL METRICS ---
    total_series = len(df_index)
    # A series is fully processed only if the done count matches the chapter count
    total_ocrd = len(df_index[df_index['ocr_done'] >= df_index['total_chapters']])
    total_summarized = len(df_index[df_index['summaries_done'] >= df_index['total_chapters']])

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Total Library", f"{total_series} Series")
    m_col2.metric("Fully OCR'd", f"{total_ocrd} Series")
    m_col3.metric("Fully Summarized", f"{total_summarized} Series")

    if not df_index.empty:
        # --- HIGHLIGHTING LOGIC ---
        def highlight_discrepancies(row):
            styles = [''] * len(row)
            if row['ocr_done'] < row['total_chapters']:
                idx = row.index.get_loc('ocr_done')
                styles[idx] = 'background-color: rgba(241, 196, 15, 0.3);'
            elif row['summaries_done'] < row['total_chapters']:
                idx = row.index.get_loc('summaries_done')
                styles[idx] = 'background-color: rgba(52, 152, 219, 0.3);'
            return styles

        styled_df = df_index.style.apply(highlight_discrepancies, axis=1)

        event = st.dataframe(
            styled_df,
            column_config={
                "title": "Series Title",
                "total_chapters": "Total Chapters",
                "ocr_done": "OCR ✅",
                "summaries_done": "Summaries 📝",
                "errors": st.column_config.NumberColumn("Errors ⚠️", format="%d")
            },
            width="stretch",
            height=800, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        if len(event.selection.rows) > 0:
            selected_row_idx = event.selection.rows[0]
            selected_title = df_index.iloc[selected_row_idx]['title']
            st.session_state.selected_series = selected_title
            
            st.divider()
            with st.container(border=True):
                st.subheader(f"⚡ Quick Actions: {selected_title}")
                quick_model = st.selectbox("Select AI Model", AVAILABLE_MODELS, key=f"qm_{selected_title}")
                
                col1, col2, _ = st.columns([1, 1, 2])
                with col1:
                    if st.button("📝 Run Summaries", key=f"sum_btn_{selected_title}", use_container_width=True):
                        cmd = [sys.executable, "processor.py", "-t", selected_title, "--summarize", "--model", quick_model]
                        subprocess.Popen(cmd, env={"PYTHONPATH": str(root_path), **os.environ})
                        st.success(f"Summarizing {selected_title}...")
                with col2:
                    if st.button("🔄 Full Pipeline", key=f"full_btn_{selected_title}", use_container_width=True):
                        cmd = [sys.executable, "processor.py", "-t", selected_title, "--extract", "--summarize", "--model", quick_model]
                        subprocess.Popen(cmd, env={"PYTHONPATH": str(root_path), **os.environ})
                        st.success(f"Full run started for {selected_title}...")
    else:
        st.info("No series found in database yet.")

# --- TAB 2: SERIES DEEP DIVE ---
with tab_details:
    all_titles = pd.read_sql("SELECT title FROM series ORDER BY title ASC", engine)['title'].tolist()
    
    if all_titles:
        default_ix = 0
        if st.session_state.selected_series in all_titles:
            default_ix = all_titles.index(st.session_state.selected_series)

        target_series = st.selectbox("Select Series to Inspect", all_titles, index=default_ix, key="series_selector_main")
        st.session_state.selected_series = target_series

        if target_series:
            stats_query = text("""
                SELECT COUNT(c.id) as total,
                SUM(CASE WHEN cp.ocr_extracted THEN 1 ELSE 0 END) as ocr_done,
                SUM(CASE WHEN cp.summary_complete THEN 1 ELSE 0 END) as summaries_done,
                SUM(CASE WHEN cp.has_error THEN 1 ELSE 0 END) as errors
                FROM chapters c JOIN series s ON c.series_id = s.id
                JOIN chapter_processing cp ON c.id = cp.chapter_id WHERE s.title = :title
            """)
            stats = pd.read_sql(stats_query, engine, params={"title": target_series}).iloc[0]
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Chapters", stats['total'])
            m2.metric("OCR Progress", f"{int((stats['ocr_done']/stats['total'])*100 if stats['total'] > 0 else 0)}%")
            m3.metric("Summaries", stats['summaries_done'])
            m4.metric("Errors", stats['errors'], delta_color="inverse")

            st.divider()

            detail_query = text("""
                SELECT c.chapter_number, cp.ocr_extracted, cp.summary_complete, s.content as summary_json, ocr.raw_text as ocr_text
                FROM chapters c JOIN series ser ON c.series_id = ser.id
                JOIN chapter_processing cp ON c.id = cp.chapter_id
                LEFT JOIN summaries s ON c.id = s.chapter_id
                LEFT JOIN ocr_results ocr ON c.id = ocr.chapter_id
                WHERE ser.title = :title ORDER BY c.chapter_number ASC
            """)
            df_details = pd.read_sql(detail_query, engine, params={"title": target_series})

            sub_tab1, sub_tab2 = st.tabs(["📊 Grid View", "🔍 Chapter Inspector"])

            with sub_tab1:
                st.dataframe(df_details[['chapter_number', 'ocr_extracted', 'summary_complete']], width="stretch", hide_index=True)

            with sub_tab2:
                chapter_to_view = st.selectbox("Pick a chapter", df_details['chapter_number'])
                row = df_details[df_details['chapter_number'] == chapter_to_view].iloc[0]
                
                st.markdown("### 📝 AI Summary")
                if row['summary_json']:
                    st.json(row['summary_json'])
                else:
                    st.info("AI Summary not yet generated for this chapter.")

                with st.expander("📄 View Raw OCR Text", expanded=False):
                    st.text_area("OCR Content", value=row['ocr_text'] if row['ocr_text'] else "No OCR data available.", height=400)
    else:
        st.warning("Database empty. Launch a process to begin.")