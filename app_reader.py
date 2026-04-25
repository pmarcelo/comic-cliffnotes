import sys
import os
from pathlib import Path
import streamlit as st

root_path = Path(__file__).resolve().parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from database.session import cloud_engine, local_engine
from interface.ui.reader_index_tab import render_reader_index
from interface.ui.reader_deep_dive_tab import render_reader_deep_dive

IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"

# Premium Typography & Layout
st.set_page_config(page_title="Comic CliffNotes", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS: Inter globally, Merriweather for blockquotes
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Merriweather:wght@400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    blockquote {
        font-family: 'Merriweather', Georgia, serif !important;
        font-style: italic;
        border-left: 4px solid #ccc;
        padding-left: 1rem;
        margin: 1.5rem 0;
        color: #555;
    }

    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 900px !important;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        .stButton > button {
            min-height: 48px !important;
            font-weight: 500 !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'selected_series_id' not in st.session_state:
    st.session_state.selected_series_id = None
if 'selected_series_title' not in st.session_state:
    st.session_state.selected_series_title = None

# Get database engine
engine = cloud_engine if (IS_ONLINE and cloud_engine) else local_engine

# Header
st.markdown("# 📚 Comic CliffNotes")

# Tabs: Index & Deep Dive
tab_library, tab_reader = st.tabs(["📚 Library", "📖 Reader"])

with tab_library:
    render_reader_index(engine)

with tab_reader:
    if st.session_state.selected_series_id:
        render_reader_deep_dive(engine)
    else:
        st.info("Select a series from the Library to begin reading.")
