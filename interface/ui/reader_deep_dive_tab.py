import streamlit as st
import pandas as pd
import json
import os
from sqlalchemy import text

IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"

@st.cache_data(ttl=30)
def fetch_series_stats(_engine, series_title):
    """Fetch chapter counts and summary availability."""
    query = text("""
        SELECT COUNT(c.id) as total,
               COUNT(summ.id) as summaries_done
        FROM chapters c
        JOIN series s ON c.series_id = s.id
        LEFT JOIN summaries summ ON c.id = summ.chapter_id
        WHERE s.title = :title
    """)
    return pd.read_sql(query, _engine, params={"title": series_title})

@st.cache_data(ttl=30)
def fetch_chapter_details(_engine, series_title):
    """Fetch chapter-by-chapter content."""
    query = text("""
        SELECT c.chapter_number, c.url,
               (summ.id IS NOT NULL) as summary_complete,
               summ.content as summary_json
        FROM chapters c
        JOIN series ser ON c.series_id = ser.id
        LEFT JOIN summaries summ ON c.id = summ.chapter_id
        WHERE ser.title = :title
        ORDER BY c.chapter_number ASC
    """)
    return pd.read_sql(query, _engine, params={"title": series_title})

def move_chapter(key, new_val):
    st.session_state[key] = new_val

def render_summary_json(summary_json):
    """Parse JSON and render beautifully with markdown."""
    try:
        data = json.loads(summary_json) if isinstance(summary_json, str) else summary_json
    except:
        st.error("Failed to parse summary.")
        return

    # Main chapter summary as blockquote
    if "chapter_summary" in data:
        st.markdown(f"> {data['chapter_summary']}")

    # World State
    if "world_state" in data and data["world_state"]:
        st.markdown("**World State**")
        world = data["world_state"]
        if isinstance(world, dict):
            for key, value in world.items():
                st.markdown(f"- **{key}:** {value}")
        elif isinstance(world, list):
            for item in world:
                st.markdown(f"- {item}")

    # Key Events
    if "key_events" in data and data["key_events"]:
        st.markdown("**Key Events**")
        events = data["key_events"]
        if isinstance(events, list):
            for idx, event in enumerate(events, 1):
                st.markdown(f"{idx}. {event}")

@st.fragment
def render_reader_deep_dive(engine):
    # Fetch all series
    titles_df = pd.read_sql("SELECT id, title FROM series ORDER BY title ASC", engine)

    if titles_df.empty:
        st.warning("No series available.")
        return

    # Series selection
    search_term = st.text_input("🔍 Search Series", placeholder="Filter...", label_visibility="collapsed")
    filtered_df = titles_df[titles_df['title'].str.contains(search_term, case=False)] if search_term else titles_df

    if filtered_df.empty:
        st.error("No matches.")
        return

    default_ix = 0
    if st.session_state.selected_series_id:
        match = filtered_df[filtered_df['id'].astype(str) == str(st.session_state.selected_series_id)]
        if not match.empty:
            default_ix = int(filtered_df.index.get_loc(match.index[0]))

    target_title = st.selectbox("Select Series", filtered_df['title'], index=default_ix, label_visibility="collapsed")

    # Stats: Total Chapters & Summaries Available
    stats_res = fetch_series_stats(engine, target_title)
    if not stats_res.empty:
        stats = stats_res.iloc[0]
        total = int(stats['total'] or 0)
        summaries = int(stats['summaries_done'] or 0)

        m1, m2 = st.columns(2)
        m1.metric("Total Chapters", total)
        m2.metric("Summaries Available", summaries)

    st.divider()

    # Fetch chapter details
    df_details = fetch_chapter_details(engine, target_title)
    if df_details.empty:
        st.info("No chapters found.")
        return

    # Chapter navigator
    chapters_list = df_details['chapter_number'].tolist()
    sb_key = f"reader_sb_{target_title}"

    if sb_key not in st.session_state:
        st.session_state[sb_key] = chapters_list[0]

    chapter_to_view = st.selectbox("Chapter", chapters_list, key=sb_key, label_visibility="collapsed")
    current_idx = chapters_list.index(chapter_to_view)

    # Prev/Next buttons in [1, 2, 1] layout
    btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])

    with btn_col1:
        if current_idx > 0:
            prev_val = chapters_list[current_idx - 1]
            st.button("⬅️ PREV", use_container_width=True, on_click=move_chapter, args=(sb_key, prev_val))
        else:
            st.button("⬅️ PREV", use_container_width=True, disabled=True)

    with btn_col3:
        if current_idx < len(chapters_list) - 1:
            next_val = chapters_list[current_idx + 1]
            st.button("NEXT ➡️", use_container_width=True, on_click=move_chapter, args=(sb_key, next_val))
        else:
            st.button("NEXT ➡️", use_container_width=True, disabled=True)

    st.divider()

    # Content rendering
    row = df_details[df_details['chapter_number'] == chapter_to_view].iloc[0]

    col_header, col_link = st.columns([2, 1])
    col_header.markdown(f"### Chapter {row['chapter_number']}")

    if row['url']:
        col_link.link_button("🌐 Source", row['url'], use_container_width=True)

    st.markdown("#### 📝 Summary")
    if row['summary_json']:
        render_summary_json(row['summary_json'])
    else:
        st.info("Summary not yet generated.")
