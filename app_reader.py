import sys
import os
from pathlib import Path
import streamlit as st

root_path = Path(__file__).resolve().parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from core import config
from database.session import cloud_engine
from interface.ui.sidebar_reader import render_api_usage
from interface.ui.index_tab import render_index
from interface.ui.deep_dive_tab import render_deep_dive

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

st.set_page_config(page_title="Manga OS", layout="wide", initial_sidebar_state="expanded")

if 'selected_series_id' not in st.session_state:
    st.session_state.selected_series_id = None
if 'selected_series_title' not in st.session_state:
    st.session_state.selected_series_title = None

engine = cloud_engine
if not engine:
    st.error("🌐 Cloud database connection failed. Check CLOUD_DATABASE_URL.")
    st.stop()

with st.sidebar:
    st.success("🌐 Cloud Read-Only Mode")
    st.caption("Background workers and local file management are disabled.")
    render_api_usage()

st.title("📖 Manga Processing Dashboard")

tabs = st.tabs(["📚 Series Index", "🔍 Series Deep Dive"])
tab_index, tab_details = tabs

with tab_index:
    render_index(engine, is_admin=False)

with tab_details:
    render_deep_dive(engine, is_admin=False)
