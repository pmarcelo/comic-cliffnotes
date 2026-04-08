import streamlit as st
import subprocess
import sys
import os
import psutil
from datetime import datetime
from core.utils import usage_tracker

AVAILABLE_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash"
]

def get_active_tasks():
    """Scans system processes for active Manga OS workers."""
    tasks = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            cmd = proc.info['cmdline']
            if cmd and any("processor.py" in arg for arg in cmd):
                title = "Unknown Task"
                try:
                    if "-t" in cmd: title = cmd[cmd.index("-t") + 1]
                    elif "--title" in cmd: title = cmd[cmd.index("--title") + 1]
                except (ValueError, IndexError): pass
                
                tasks.append({
                    "pid": proc.info['pid'],
                    "title": title,
                    "start_time": datetime.fromtimestamp(proc.info['create_time'])
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return tasks

@st.fragment
def render_pipeline_control(root_path):
    """Isolated fragment for launching new processes."""
    st.header("🛠️ Pipeline Control")
    with st.form("run_processor", clear_on_submit=False):
        st.write("Launch New Process")
        input_title = st.text_input("Series Title")
        
        ingest_method = st.selectbox(
            "Ingest Method", 
            ["Auto-Detect", "Google Drive", "Web (gallery-dl)"]
        )
        
        url_label = "GDrive URL" if ingest_method == "Google Drive" else "GDrive URL (Optional)"
        input_url = st.text_input(url_label)
        
        # 🎯 NEW: 0 tells the backend to auto-detect. Any other number forces an override.
        starting_chapter = st.number_input(
            "Starting Chapter (0 = Auto-Append)", 
            min_value=0, 
            value=0,
            help="Leave at 0 to automatically append to the end of the series. Enter a number to force the pipeline to overwrite or fill a specific chapter."
        )
        
        # 🎯 NEW: Added the Skip Chapters input field
        skip_chapters_input = st.text_input(
            "Chapters to Skip (Optional)",
            placeholder="e.g., 20, 25-30",
            help="Comma-separated list of chapters or ranges to completely ignore during GDrive ingestion."
        )
        
        selected_model = st.selectbox(
            "AI Model", 
            AVAILABLE_MODELS, 
            key="sidebar_model_select"
        )
        
        do_extract = st.checkbox("Extract & OCR", value=True)
        do_summarize = st.checkbox("Summarize", value=False)
        
        submit_btn = st.form_submit_button("🚀 Start Processor")

    if submit_btn:
        if not input_title:
            st.error("Series Title is required.")
        elif ingest_method == "Google Drive" and not input_url:
            st.error("GDrive URL required for Google Drive ingestion.")
        else:
            mapping = {
                "Auto-Detect": "auto",
                "Google Drive": "google_drive",
                "Web (gallery-dl)": "web_gallery-dl"
            }
            method_flag = mapping[ingest_method]

            cmd = [
                sys.executable, "processor.py", 
                "-t", input_title, 
                "-c", str(starting_chapter), 
                "--model", selected_model,
                "--ingest-method", method_flag
            ]
            
            if input_url: cmd.extend(["-u", input_url])
            
            # 🎯 NEW: Pass the skip argument to the subprocess
            if skip_chapters_input: cmd.extend(["--skip", skip_chapters_input])
                
            if do_extract: cmd.append("--extract")
            if do_summarize: cmd.append("--summarize")
            
            subprocess.Popen(cmd, env={"PYTHONPATH": str(root_path), **os.environ})
            st.success(f"Started {input_title}!")

@st.fragment
def render_active_tasks():
    """Isolated fragment to monitor and kill background PIDs."""
    st.divider()
    st.header("⏳ Active Tasks")
    active_tasks = get_active_tasks()
    
    if active_tasks:
        for task in active_tasks:
            with st.container(border=True):
                st.write(f"🏷️ **{task['title']}**")
                st.caption(f"PID: {task['pid']} | {task['start_time'].strftime('%H:%M:%S')}")
                if st.button("🛑 Stop", key=f"kill_{task['pid']}", use_container_width=True):
                    try:
                        psutil.Process(task['pid']).terminate()
                        st.rerun(scope="fragment") 
                    except: pass
    else:
        st.info("No active processes.")

@st.fragment
def render_api_usage():
    """Isolated fragment for request tracking, project-aware (Requests only)."""
    st.divider()
    st.header("📊 API Usage")
    
    # Identify Active Project from Env
    active_project = os.getenv("GEMINI_PROJECT", "default")
    
    # Get current model for tier logic (Flash vs Pro)
    current_model = st.session_state.get("sidebar_model_select", AVAILABLE_MODELS[0])
    stats = usage_tracker.get_today_stats(current_model)
    
    # Clean Display: Project name and simple request metric
    st.subheader(f"Project: {active_project.upper()}")
    st.metric("Requests Today", f"{stats.get('requests', 0):,}")

    if st.button("🔄 Refresh Stats", use_container_width=True):
        st.rerun(scope="fragment")