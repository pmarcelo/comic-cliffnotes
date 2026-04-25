import streamlit as st
import uuid
from sqlalchemy import text
from core.extractors.discovery import search_mangadex, sync_series_by_id

def render_discovery(engine):
    """Admin-only: Series discovery and library sync."""
    st.header("Series Discovery")

    st.subheader("Add New Series")
    search_query = st.text_input("Search MangaDex", placeholder="Enter series title...")
    
    if st.button("Search") and search_query:
        with st.spinner("Searching..."):
            results = search_mangadex(search_query)
            if not results:
                st.warning("No results found.")
            else:
                for res in results:
                    with st.container(border=True):
                        col1, col2 = st.columns([4, 1])
                        col1.write(f"**{res['title']}**")
                        col1.caption(f"ID: {res['id']}")
                        
                        if col2.button("Add to Library", key=f"add_{res['id']}"):
                            with st.spinner("Syncing..."):
                                success = sync_series_by_id(res['id'])
                                if success:
                                    st.success(f"Added {res['title']}!")
                                    st.cache_data.clear()
                                else:
                                    st.error("Failed to add series.")