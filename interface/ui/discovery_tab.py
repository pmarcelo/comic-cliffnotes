import streamlit as st
import uuid
from sqlalchemy import text

def render_discovery(engine):
    """Admin-only: Series discovery and library sync."""
    from core.extractors.discovery import sync_series_by_id

    st.header("Series Discovery")

    st.subheader("Add New Series")
    search_query = st.text_input("Search MangaDex", placeholder="Enter series title...")

    if st.button("Search") and search_query:
        st.warning("Search functionality pending MangaDex API client implementation.")