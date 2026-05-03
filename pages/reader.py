import sys
import os
from pathlib import Path
import streamlit as st
import pandas as pd
import json
from sqlalchemy import text

# Setup path
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from database.session import engine

# Page config
st.set_page_config(page_title="Reader - Comic CliffNotes", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for improved typography and layout
CUSTOM_CSS = """
<style>
    /* Reduce top padding to bring content above the fold */
    .main {
        padding-top: 0.5rem !important;
    }

    /* Summary container styling */
    .summary-container {
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        line-height: 1.7;
    }

    /* Summary text styling */
    .summary-text {
        color: #E0E0E0;
        font-size: 1rem;
        font-style: normal;
        line-height: 1.7;
        margin: 0;
    }

    /* Section headers */
    .section-header {
        color: #E0E0E0;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
        font-size: 0.95rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* List items spacing */
    .key-events-list {
        color: #E0E0E0;
        line-height: 1.8;
    }

    .key-events-list li {
        margin-bottom: 0.5rem;
    }

    /* World state items */
    .world-state-item {
        color: #E0E0E0;
        margin-bottom: 0.5rem;
        line-height: 1.6;
    }
</style>
"""


@st.cache_data(ttl=30)
def fetch_chapter_details(_engine, series_id):
    """Fetch chapter-by-chapter content for a specific series."""
    query = text("""
        SELECT c.chapter_number, c.url,
               (summ.id IS NOT NULL) as summary_complete,
               summ.content as summary_json
        FROM chapters c
        LEFT JOIN summaries summ ON c.id = summ.chapter_id
        WHERE c.series_id = :series_id
        ORDER BY c.chapter_number ASC
    """)
    return pd.read_sql(query, _engine, params={"series_id": series_id})


@st.cache_data(ttl=30)
def fetch_series_stats(_engine, series_id):
    """Fetch chapter counts and summary availability."""
    query = text("""
        SELECT COUNT(c.id) as total,
               COUNT(summ.id) as summaries_done
        FROM chapters c
        LEFT JOIN summaries summ ON c.id = summ.chapter_id
        WHERE c.series_id = :series_id
    """)
    return pd.read_sql(query, _engine, params={"series_id": series_id})


def move_chapter(key, new_val):
    st.session_state[key] = new_val


def render_summary_json(summary_json):
    """Parse JSON and render with improved typography and container styling."""
    try:
        data = json.loads(summary_json) if isinstance(summary_json, str) else summary_json
    except:
        st.error("Failed to parse summary.")
        return

    # Main chapter summary in styled container (no blockquote/italics)
    if "chapter_summary" in data:
        summary_text = data['chapter_summary']
        st.markdown(
            f'<div class="summary-container"><p class="summary-text">{summary_text}</p></div>',
            unsafe_allow_html=True
        )

    # World State
    if "world_state" in data and data["world_state"]:
        st.markdown('<div class="section-header">World State</div>', unsafe_allow_html=True)
        world = data["world_state"]
        if isinstance(world, dict):
            for key, value in world.items():
                st.markdown(
                    f'<div class="world-state-item"><strong>{key}:</strong> {value}</div>',
                    unsafe_allow_html=True
                )
        elif isinstance(world, list):
            for item in world:
                st.markdown(
                    f'<div class="world-state-item">• {item}</div>',
                    unsafe_allow_html=True
                )

    # Key Events
    if "key_events" in data and data["key_events"]:
        st.markdown('<div class="section-header">Key Events</div>', unsafe_allow_html=True)
        events = data["key_events"]
        if isinstance(events, list):
            events_html = '<ol class="key-events-list">'
            for event in events:
                events_html += f'<li>{event}</li>'
            events_html += '</ol>'
            st.markdown(events_html, unsafe_allow_html=True)


# Inject custom CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Check if series_id is in session state
if not st.session_state.get('selected_series_id'):
    st.warning("No series selected. Please go back to the Library and select a series.")
    if st.button("← Back to Library"):
        st.switch_page("app_reader.py")
    st.stop()

series_id = st.session_state.selected_series_id
series_title = st.session_state.selected_series_title

# Header with back button
col_header, col_back = st.columns([4, 1])
col_header.markdown(f"# 📖 {series_title}")

if col_back.button("← Back", use_container_width=True):
    st.switch_page("app_reader.py")

# Fetch chapter details
df_details = fetch_chapter_details(engine, series_id)
if df_details.empty:
    st.info("No chapters found for this series.")
    st.stop()

# Stats
stats_res = fetch_series_stats(engine, series_id)
if not stats_res.empty:
    stats = stats_res.iloc[0]
    total = int(stats['total'] or 0)
    summaries = int(stats['summaries_done'] or 0)

    stat_col1, stat_col2 = st.columns(2)
    stat_col1.metric("Total Chapters", total)
    stat_col2.metric("Summaries Available", summaries)

# Chapter navigator
chapters_list = df_details['chapter_number'].tolist()
sb_key = f"reader_sb_{series_id}"

if sb_key not in st.session_state:
    st.session_state[sb_key] = chapters_list[0]

chapter_to_view = st.selectbox("Chapter", chapters_list, key=sb_key, label_visibility="collapsed")
current_idx = chapters_list.index(chapter_to_view)

# CONDENSED NAVIGATION: Prev/Next buttons in single row
nav_col1, nav_col2 = st.columns(2, gap="small")

with nav_col1:
    if current_idx > 0:
        prev_val = chapters_list[current_idx - 1]
        st.button("⬅️ PREV", use_container_width=True, on_click=move_chapter, args=(sb_key, prev_val))
    else:
        st.button("⬅️ PREV", use_container_width=True, disabled=True)

with nav_col2:
    if current_idx < len(chapters_list) - 1:
        next_val = chapters_list[current_idx + 1]
        st.button("NEXT ➡️", use_container_width=True, on_click=move_chapter, args=(sb_key, next_val))
    else:
        st.button("NEXT ➡️", use_container_width=True, disabled=True)

# Content rendering
row = df_details[df_details['chapter_number'] == chapter_to_view].iloc[0]

col_header, col_link = st.columns([2, 1])
col_header.markdown(f"### Chapter {row['chapter_number']}")

if row['url']:
    col_link.link_button("🌐 Source", row['url'], use_container_width=True)

# Summary section with improved typography
if row['summary_json']:
    render_summary_json(row['summary_json'])
else:
    st.info("Summary not yet generated.")
