import sys
from pathlib import Path
from sqlalchemy import create_engine  
import streamlit as st  

# This forces Python to look at the root 'comic-cliffnotes' folder before doing anything else.
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from core import config  # noqa: E402
from ui.sidebar import render_pipeline_control, render_active_tasks, render_api_usage # noqa: E402
from ui.index_tab import render_index # noqa: E402
from ui.deep_dive_tab import render_deep_dive # noqa: E402
from ui.discovery_tab import render_discovery # noqa: E402
from ui.queue_tab import render_queue_tab # noqa: E402

def inject_mobile_ui():
    st.markdown("""
    <style>
        /* 1. Kill the massive top padding */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        /* Mobile-Specific Tweaks (triggers on screens smaller than 768px) */
        @media (max-width: 768px) {
            /* 2. Make buttons massive for thumbs */
            .stButton > button {
                width: 100% !important;
                min-height: 50px !important;
                font-weight: bold !important;
            }
            
            /* 3. Shrink text slightly so metrics and tables fit */
            html, body, [class*="css"] {
                font-size: 14px;
            }
            
            /* 4. Fix selectbox and text input tap targets */
            .stTextInput>div>div>input, .stSelectbox>div>div>div {
                min-height: 45px !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)

# Call it immediately
inject_mobile_ui()

# --- PAGE CONFIG ---
st.set_page_config(page_title="Manga OS", layout="wide", initial_sidebar_state="expanded")

# --- 🎯 INITIALIZE SESSION STATE ---
if 'selected_series_id' not in st.session_state:
    st.session_state.selected_series_id = None
if 'selected_series_title' not in st.session_state:
    st.session_state.selected_series_title = None

# --- DATABASE CONNECTION ---
@st.cache_resource
def get_db_engine():
    return create_engine(config.DATABASE_URL)

engine = get_db_engine()

# --- RENDER SIDEBAR ---
with st.sidebar:
    render_pipeline_control(root_path)
    render_active_tasks()
    render_api_usage()

# --- MAIN CONTENT ---
st.title("📖 Manga Processing Dashboard")

# Added the 4th tab for the Pipeline Queue
tab_index, tab_details, tab_discover, tab_queue = st.tabs([
    "📚 Series Index", 
    "🔍 Series Deep Dive", 
    "🌐 Global Discovery",
    "📋 Pipeline Queue"
])

with tab_index:
    render_index(engine, root_path)

with tab_details:
    # This acts as your 'Reader/Summary' view
    render_deep_dive(engine)

with tab_discover:
    render_discovery(engine)

with tab_queue:
    # 🎯 NEW: Mission Control for background workers
    render_queue_tab(engine)