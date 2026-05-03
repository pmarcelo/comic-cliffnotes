"""Cache management utilities for Streamlit app."""
import streamlit as st


def clear_library_cache():
    """Clear the library/series index cache."""
    st.cache_data.clear()


def show_cache_controls():
    """Display cache management controls in the UI (e.g., in sidebar)."""
    with st.sidebar:
        st.divider()
        st.markdown("#### Cache Controls")
        if st.button("🔄 Refresh Library", use_container_width=True, help="Clear cache and reload library from database"):
            clear_library_cache()
            st.success("Library cache cleared!")
            st.rerun()
