import streamlit as st
import subprocess
import sys
import os
from datetime import datetime

# Detect Mode
IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"

# 🎯 CLOUD-SAFE: Only import psutil if we're not online
# This prevents the ModuleNotFoundError on Streamlit Cloud
if not IS_ONLINE:
    try:
        import psutil
    except ImportError:
        psutil = None
else:
    psutil = None

# We still need the usage tracker for the local view
from core.utils import usage_tracker

AVAILABLE_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash"
]

def get_active_tasks():
    """Local-only: Scans system processes for active Manga OS workers."""
    if not psutil:
        return []
        
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
    """Local-only: Isolated fragment for launching new processes."""
    if IS_ONLINE:
        return # Safety guard

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
        
        auto_append = st.checkbox(
            "Auto-Append (Continue from latest)", 
            value=True,
            help="Automatically finds the highest chapter in the database."
        )
        
        starting_chapter = st.number_input(
            "Override Starting Chapter", 
            min_value=1, 
            value=1
        )
        
        skip_chapters_input = st.text_input(
            "Chapters to Skip (Optional)",
            placeholder="e.g., 20, 25-30"
        )
        
        selected_model = st.selectbox(
            "AI Model", 
            AVAILABLE_MODELS, 
            key="sidebar_model_select"
        )
        
        st.write("Pipeline Stages:")
        do_extract = st.checkbox("Extract Images", value=True)
        do_ocr = st.checkbox("Run OCR", value=True)
        do_summarize = st.checkbox("Summarize (AI)", value=False)
        
        submit_btn = st.form_submit_button("🚀 Start Processor")

    if submit_btn:
        if not input_title:
            st.error("Series Title is required.")
        else:
            mapping = {
                "Auto-Detect": "auto",
                "Google Drive": "google_drive",
                "Web (gallery-dl)": "web_gallery-dl"
            }
            method_flag = mapping[ingest_method]
            actual_start_chapter = -1 if auto_append else starting_chapter

            cmd = [
                sys.executable, "processor.py", 
                "-t", input_title, 
                "-c", str(actual_start_chapter), 
                "--model", selected_model,
                "--ingest-method", method_flag
            ]
            
            if input_url: cmd.extend(["-u", input_url])
            if skip_chapters_input: cmd.extend(["--skip", skip_chapters_input])
            if do_extract: cmd.append("--extract")
            if do_ocr: cmd.append("--ocr")
            if do_summarize: cmd.append("--summarize")
            
            subprocess.Popen(cmd, env={"PYTHONPATH": str(root_path), **os.environ})
            st.success(f"Started {input_title}!")

@st.fragment
def render_active_tasks():
    """Local-only: Isolated fragment to monitor and kill background PIDs."""
    if IS_ONLINE:
        return # Safety guard

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
    """Isolated fragment for request tracking."""
    st.divider()
    st.header("📊 API Usage")
    
    if IS_ONLINE:
        st.info("Usage tracking is local-only.")
        return

    # Identify Active Project from Env
    active_project = os.getenv("GEMINI_PROJECT", "default")
    
    # Get current model for tier logic
    current_model = st.session_state.get("sidebar_model_select", AVAILABLE_MODELS[0])
    stats = usage_tracker.get_today_stats(current_model)
    
    st.subheader(f"Project: {active_project.upper()}")
    st.metric("Requests Today", f"{stats.get('requests', 0):,}")

    if st.button("🔄 Refresh Stats", use_container_width=True):
        st.rerun(scope="fragment")