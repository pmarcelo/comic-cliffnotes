import sys
import os
import json
from pathlib import Path

# --- PATH FIX ---
# Add the project root to the python path so it can find 'core' and 'database'
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

import streamlit as st
import pandas as pd
import subprocess
from sqlalchemy import create_engine, text
from core import config
from core.utils import usage_tracker 

# --- SAFE FALLBACK FOR MODELS ---
AVAILABLE_MODELS = getattr(config, 'SUPPORTED_MODELS', [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-2.5-pro",
    "gemini-1.5-pro"
])

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
    
    # ---> NEW: Model Selection Dropdown <---
    selected_model = st.selectbox("AI Model", AVAILABLE_MODELS, index=0)
    
    # Checkboxes for flags
    do_extract = st.checkbox("Extract & OCR", value=True)
    do_summarize = st.checkbox("Summarize", value=True)
    
    submit_btn = st.form_submit_button("🚀 Start Processor")

if submit_btn:
    # Logic Update: URL is only mandatory if we are extracting/OCR-ing
    url_needed_but_missing = do_extract and not input_url
    nothing_checked = not do_extract and not do_summarize
    
    if not input_title:
        st.sidebar.error("Series Title is required.")
    elif url_needed_but_missing:
        st.sidebar.error("GDrive URL is required for Extraction/OCR.")
    elif nothing_checked:
        st.sidebar.error("Please select at least one action (Extract or Summarize).")
    else:
        # Use the current venv's python executable
        python_path = sys.executable 
        
        # Build command
        cmd = [python_path, "processor.py", "-t", input_title, "-c", str(starting_chapter)]
        
        # ---> NEW: Append the selected model flag <---
        cmd.extend(["--model", selected_model])
        
        # Only add URL flag if provided
        if input_url:
            cmd.extend(["-u", input_url])
            
        if do_extract: cmd.append("--extract")
        if do_summarize: cmd.append("--summarize")
        
        st.sidebar.info(f"Running via: {python_path}")
        
        # Inherit environment variables
        current_env = os.environ.copy()
        current_env["PYTHONPATH"] = str(root_path)
        
        subprocess.Popen(cmd, env=current_env) 
        st.sidebar.success(f"Started background process for {input_title} using {selected_model}!")

# --- SIDEBAR: API USAGE TRACKER ---
st.sidebar.divider()
st.sidebar.header("📊 API Usage Tracker")

# Dynamically fetch stats based on the model currently selected in the dropdown
tracker_data = usage_tracker.get_today_tokens(selected_model)
used_tokens = tracker_data["used"]
DAILY_LIMIT = tracker_data["limit"]

st.sidebar.caption(f"Tracking tier for: {selected_model}")
st.sidebar.metric(label="Tokens Used Today", value=f"{used_tokens:,}")

remaining_pct = max(0, (DAILY_LIMIT - used_tokens) / DAILY_LIMIT)
st.sidebar.write(f"**Limit:** {used_tokens:,} / {DAILY_LIMIT:,}")
st.sidebar.progress(remaining_pct)

if remaining_pct < 0.1:
    st.sidebar.error("⚠️ Approaching daily token limit for this tier!")

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# --- MAIN CONTENT ---
st.title("📖 Manga Processing Dashboard")

# Create the top-level Tabs
tab_index, tab_details = st.tabs(["📚 Series Index", "🔍 Series Deep Dive"])

# --- TAB 1: SERIES INDEX ---
with tab_index:
    st.subheader("All Series Library")
    
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

    if not df_index.empty:
        event = st.dataframe(
            df_index,
            column_config={
                "title": "Series Title",
                "total_chapters": "Total Chapters",
                "ocr_done": "OCR ✅",
                "summaries_done": "Summaries 📝",
                "errors": st.column_config.NumberColumn("Errors ⚠️", format="%d")
            },
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        # --- QUICK ACTIONS PANEL (POPS UP ON CLICK) ---
        if len(event.selection.rows) > 0:
            selected_row_idx = event.selection.rows[0]
            selected_title = df_index.iloc[selected_row_idx]['title']
            st.session_state.selected_series = selected_title
            
            st.divider()
            
            # Container with a border for a cohesive control panel look
            with st.container(border=True):
                st.subheader(f"⚡ Quick Actions: {selected_title}")
                
                # ---> NEW: Allow model selection right in the quick actions panel <---
                quick_model = st.selectbox(
                    "Select AI Model for Quick Action", 
                    AVAILABLE_MODELS, 
                    index=0, 
                    key=f"qm_{selected_title}"
                )
                
                col1, col2, col3 = st.columns([1, 1, 2])
                
                # Button 1: Just Summarize
                with col1:
                    if st.button("📝 Run Summaries", key=f"sum_btn_{selected_title}", use_container_width=True):
                        python_path = sys.executable 
                        # Appended the model flag
                        cmd = [python_path, "processor.py", "-t", selected_title, "--summarize", "--model", quick_model]
                        
                        current_env = os.environ.copy()
                        current_env["PYTHONPATH"] = str(root_path)
                        
                        subprocess.Popen(cmd, env=current_env)
                        st.success(f"Background summary process started for {selected_title} using {quick_model}!")

                # Button 2: Extract & Summarize (Full Pipeline)
                with col2:
                    if st.button("🔄 Run Full Pipeline", key=f"full_btn_{selected_title}", use_container_width=True):
                        python_path = sys.executable 
                        # Appended the model flag
                        cmd = [python_path, "processor.py", "-t", selected_title, "--extract", "--summarize", "--model", quick_model]
                        
                        current_env = os.environ.copy()
                        current_env["PYTHONPATH"] = str(root_path)
                        
                        subprocess.Popen(cmd, env=current_env)
                        st.success(f"Full pipeline started for {selected_title} using {quick_model}!")
    else:
        st.info("No series found in database yet.")

# --- TAB 2: SERIES DEEP DIVE ---
with tab_details:
    all_titles = pd.read_sql("SELECT title FROM series ORDER BY title ASC", engine)['title'].tolist()
    
    if all_titles:
        default_ix = 0
        if st.session_state.selected_series in all_titles:
            default_ix = all_titles.index(st.session_state.selected_series)

        target_series = st.selectbox(
            "Select Series to Inspect", 
            all_titles, 
            index=default_ix,
            key="series_selector_main"
        )
        
        st.session_state.selected_series = target_series

        if target_series:
            # 1. High-Level Stats
            stats_query = text("""
                SELECT 
                    COUNT(c.id) as total,
                    SUM(CASE WHEN cp.ocr_extracted THEN 1 ELSE 0 END) as ocr_done,
                    SUM(CASE WHEN cp.summary_complete THEN 1 ELSE 0 END) as summaries_done,
                    SUM(CASE WHEN cp.has_error THEN 1 ELSE 0 END) as errors
                FROM chapters c
                JOIN series s ON c.series_id = s.id
                JOIN chapter_processing cp ON c.id = cp.chapter_id
                WHERE s.title = :title
            """)
            stats = pd.read_sql(stats_query, engine, params={"title": target_series}).iloc[0]
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Chapters", stats['total'])
            m2.metric("OCR Progress", f"{int((stats['ocr_done']/stats['total'])*100 if stats['total'] > 0 else 0)}%")
            m3.metric("Summaries", stats['summaries_done'])
            m4.metric("Errors", stats['errors'], delta_color="inverse")

            st.divider()

            # 2. Detail Data Fetch
            detail_query = text("""
                SELECT 
                    c.chapter_number,
                    cp.ocr_extracted,
                    cp.summary_complete,
                    s.content as summary_json,
                    ocr.raw_text as ocr_text
                FROM chapters c
                JOIN series ser ON c.series_id = ser.id
                JOIN chapter_processing cp ON c.id = cp.chapter_id
                LEFT JOIN summaries s ON c.id = s.chapter_id
                LEFT JOIN ocr_results ocr ON c.id = ocr.chapter_id
                WHERE ser.title = :title
                ORDER BY c.chapter_number ASC
            """)
            df_details = pd.read_sql(detail_query, engine, params={"title": target_series})

            sub_tab1, sub_tab2 = st.tabs(["📊 Grid View", "🔍 Chapter Inspector"])

            with sub_tab1:
                st.dataframe(
                    df_details[['chapter_number', 'ocr_extracted', 'summary_complete']], 
                    width="stretch",
                    hide_index=True
                )

            with sub_tab2:
                chapter_to_view = st.selectbox("Pick a chapter", df_details['chapter_number'])
                row = df_details[df_details['chapter_number'] == chapter_to_view].iloc[0]
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Raw OCR Text**")
                    st.text_area("OCR Data", value=row['ocr_text'][:5000] if row['ocr_text'] else "No data.", height=300)
                with c2:
                    st.markdown("**AI Summary**")
                    if row['summary_json']:
                        st.json(row['summary_json'])
                    else:
                        st.info("AI Summary not yet generated.")
    else:
        st.warning("Database empty. Launch a process to begin.")