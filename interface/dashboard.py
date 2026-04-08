import sys
from pathlib import Path
from sqlalchemy import create_engine

# --- PATH FIX ---
root_path = Path(__file__).resolve().parent.parent
sys.path.append(str(root_path))

import streamlit as st
from core import config
from ui.sidebar import render_pipeline_control, render_active_tasks, render_api_usage
from ui.index_tab import render_index
from ui.deep_dive_tab import render_deep_dive
from ui.discovery_tab import render_discovery

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

# --- 🎯 THE FIX: INITIALIZE SESSION STATE ---
# This must happen before the tabs or fragments are rendered
if 'selected_series_id' not in st.session_state:
    st.session_state.selected_series_id = None
if 'selected_series_title' not in st.session_state:
    st.session_state.selected_series_title = None

# --- DATABASE CONNECTION ---
engine = create_engine(config.DATABASE_URL)

# --- RENDER SIDEBAR ---
with st.sidebar:
    render_pipeline_control(root_path)
    render_active_tasks()
    render_api_usage()

# --- MAIN CONTENT ---
st.title("📖 Manga Processing Dashboard")
tab_index, tab_details, tab_discover = st.tabs(["📚 Series Index", "🔍 Series Deep Dive", "🌐 Global Discovery"])

with tab_index:
    render_index(engine, root_path)

with tab_details:
    render_deep_dive(engine)

with tab_discover:
    render_discovery(engine)