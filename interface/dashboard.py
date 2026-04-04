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