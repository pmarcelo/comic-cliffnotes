import sys
import os
from pathlib import Path
import streamlit as st  

# This forces Python to look at the root folder
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from core import config  
from database.session import local_engine, cloud_engine 
from ui.sidebar import render_pipeline_control, render_active_tasks, render_api_usage 
from ui.index_tab import render_index 
from ui.deep_dive_tab import render_deep_dive 
from ui.discovery_tab import render_discovery 
from ui.queue_tab import render_queue_tab 

# Detect mode once to use throughout
IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"

def inject_mobile_ui():
    st.markdown("""
    <style>
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        @media (max-width: 768px) {
            .stButton > button {
                width: 100% !important;
                min-height: 50px !important;
                font-weight: bold !important;
            }
            html, body, [class*="css"] {
                font-size: 14px;
            }
            .stTextInput>div>div>input, .stSelectbox>div>div>div {
                min-height: 45px !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)

inject_mobile_ui()

# --- PAGE CONFIG ---
st.set_page_config(page_title="Manga OS", layout="wide", initial_sidebar_state="expanded")

# --- INITIALIZE SESSION STATE ---
if 'selected_series_id' not in st.session_state:
    st.session_state.selected_series_id = None
if 'selected_series_title' not in st.session_state:
    st.session_state.selected_series_title = None

# --- DATABASE CONNECTION ---
def get_db_engine():
    if IS_ONLINE and cloud_engine:
        return cloud_engine
    return local_engine

engine = get_db_engine()

# --- RENDER SIDEBAR ---
with st.sidebar:
    if IS_ONLINE:
        st.success("🌐 Cloud Read-Only Mode")
        st.caption("Background workers and local file management are disabled.")
    else:
        # Local-only controls
        render_pipeline_control(root_path)
        render_active_tasks()
        
    render_api_usage()

# --- MAIN CONTENT ---
st.title("📖 Manga Processing Dashboard")

# 🎯 DYNAMIC TABS: Only show what's functional for the current mode
if IS_ONLINE:
    tabs = st.tabs(["📚 Series Index", "🔍 Series Deep Dive"])
    tab_index, tab_details = tabs
else:
    tabs = st.tabs(["📚 Series Index", "🔍 Series Deep Dive", "🌐 Global Discovery", "📋 Pipeline Queue"])
    tab_index, tab_details, tab_discover, tab_queue = tabs

with tab_index:
    render_index(engine, root_path)

with tab_details:
    render_deep_dive(engine)

# Only render management tabs if local
if not IS_ONLINE:
    with tab_discover:
        render_discovery(engine)

    with tab_queue:
        render_queue_tab(engine)