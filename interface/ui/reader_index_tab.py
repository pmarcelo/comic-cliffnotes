import streamlit as st
import pandas as pd
import os
from sqlalchemy import text

IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"

@st.cache_data(ttl=60)
def fetch_series_index(_engine):
    """Fetch series with chapter counts and summary progress."""
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
    st.subheader("Library")

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
                    st.rerun()
