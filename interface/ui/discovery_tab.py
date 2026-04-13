import streamlit as st
import uuid
import os
from sqlalchemy import text

# 🎯 REMOVED: from core.extractors.discovery import sync_series_by_id
# We move this import inside the local-only logic below.

# Detect Mode
IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"

def render_discovery(engine):
    st.header("Series Discovery")
    
    if IS_ONLINE:
        st.info("💡 Discovery and syncing are disabled in the Cloud Dashboard.")
        st.warning("Please use the Local Environment to add new series to the library.")
        return

    # 🎯 LAZY IMPORT: Only loads when actually running locally
    from core.extractors.discovery import search_mangadex, sync_series_by_id

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