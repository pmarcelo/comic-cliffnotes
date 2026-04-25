import streamlit as st
import os

from core.config import SUPPORTED_MODELS as AVAILABLE_MODELS

@st.fragment
def render_api_usage():
    """Cloud-only: Read-only API usage tracker."""
    st.divider()
    st.header("📊 API Usage")

    active_project = os.getenv("GEMINI_PROJECT", "default")

    # In cloud mode, we can't track usage since the tracking DB is local-only
    # Display a placeholder message
    st.info("Usage tracking is local-only. Cloud mode has no request history.")
