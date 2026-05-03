import streamlit as st
import pandas as pd
import os
from sqlalchemy import text

IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_series_index(_engine):
    """Fetch series with chapter counts and summary progress.

    Cached for 1 hour to reduce load on remote CockroachDB.
    Use cache_manager.clear_library_cache() to manually refresh.
    """
    query = text("""
        SELECT
            s.id, s.title, s.created_at,
            COUNT(c.id) as total_chapters,
            COUNT(summ.id) as summaries_done
        FROM series s
        LEFT JOIN chapters c ON s.id = c.series_id
        LEFT JOIN summaries summ ON c.id = summ.chapter_id
        GROUP BY s.id, s.title, s.created_at
        ORDER BY s.created_at DESC
    """)
    return pd.read_sql(query, _engine)

@st.fragment
def render_reader_index(engine):
    # Sticky header CSS (targets first 4 Streamlit containers: title, search, sort radio, spacer)
    st.markdown("""
    <style>
        /* Make header and filter controls sticky at top while scrolling */
        .stVerticalBlockBQ > .element-container:nth-child(1),
        .stVerticalBlockBQ > .element-container:nth-child(2),
        .stVerticalBlockBQ > .element-container:nth-child(3) {
            position: sticky !important;
            top: 0 !important;
            background: rgba(14, 17, 23, 0.98) !important;
            z-index: 100 !important;
            padding: 0.5rem 0 !important;
            border-bottom: 1px solid #333 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.subheader("Library")

    # Refresh button (top right)
    col_title, col_refresh = st.columns([4, 1])
    with col_refresh:
        if st.button("🔄", help="Refresh library from database (clears cache)"):
            st.cache_data.clear()
            st.rerun()

    df_raw = fetch_series_index(engine)
    if df_raw.empty:
        st.info("No series found yet.")
        return

    # Search & Sort Controls
    search_query = st.text_input("Search", placeholder="Filter by title...", label_visibility="collapsed")
    sort_option = st.radio(
        "Sort by",
        ["Recently Added", "A-Z", "Chapter Count"],
        horizontal=True,
        label_visibility="collapsed"
    )

    df = df_raw.copy()

    # Convert numeric columns to int to remove floats
    df['total_chapters'] = df['total_chapters'].astype(int)
    df['summaries_done'] = df['summaries_done'].astype(int)

    # Apply search
    if search_query:
        df = df[df['title'].str.contains(search_query, case=False, na=False)]

    # Apply sort
    if sort_option == "A-Z":
        df = df.sort_values("title", ascending=True)
    elif sort_option == "Chapter Count":
        df = df.sort_values("total_chapters", ascending=False)
    else:  # Recently Added (default)
        df = df.sort_values("created_at", ascending=False)

    df['id'] = df['id'].astype(str)

    if df.empty:
        st.info("No matches found.")
        return

    # 3-column grid
    cols = st.columns(3)
    for i, (_, row) in enumerate(df.iterrows()):
        col = cols[i % 3]
        with col:
            with st.container(border=True):
                st.subheader(row['title'][:40])
                st.caption(f"{int(row['total_chapters'])} chapters")

                total = max(1, int(row['total_chapters']))
                done = int(row['summaries_done'])
                progress = done / total
                st.progress(progress, text=f"{done}/{total}")

                if st.button("📖 Read", key=f"read_{row['id']}", use_container_width=True):
                    st.session_state.selected_series_id = row['id']
                    st.session_state.selected_series_title = row['title']
                    st.session_state.navigate_to_reader = True
                    st.rerun()
