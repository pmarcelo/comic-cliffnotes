import streamlit as st
import pandas as pd
from sqlalchemy import text

@st.cache_data(ttl=30)
def fetch_series_stats(_engine, series_title):
    query = text("""
        SELECT COUNT(c.id) as total,
               SUM(CASE WHEN cp.ocr_extracted THEN 1 ELSE 0 END) as ocr_done,
               SUM(CASE WHEN cp.summary_complete THEN 1 ELSE 0 END) as summaries_done,
               SUM(CASE WHEN cp.has_error THEN 1 ELSE 0 END) as errors
        FROM chapters c 
        JOIN series s ON c.series_id = s.id
        JOIN chapter_processing cp ON c.id = cp.chapter_id 
        WHERE s.title = :title
    """)
    return pd.read_sql(query, _engine, params={"title": series_title})

@st.cache_data(ttl=30)
def fetch_chapter_details(_engine, series_title):
    query = text("""
        SELECT c.chapter_number, cp.ocr_extracted, cp.summary_complete, 
               s.content as summary_json, ocr.raw_text as ocr_text
        FROM chapters c 
        JOIN series ser ON c.series_id = ser.id
        JOIN chapter_processing cp ON c.id = cp.chapter_id
        LEFT JOIN summaries s ON c.id = s.chapter_id
        LEFT JOIN ocr_results ocr ON c.id = ocr.chapter_id
        WHERE ser.title = :title 
        ORDER BY c.chapter_number ASC
    """)
    return pd.read_sql(query, _engine, params={"title": series_title})

def move_chapter(key, new_val):
    """Callback to update session state before the fragment reruns."""
    st.session_state[key] = new_val

@st.fragment
def render_deep_dive(engine):
    # 1. Fetch Series List
    titles_df = pd.read_sql("SELECT id, title FROM series ORDER BY title ASC", engine)
    
    if titles_df.empty:
        st.warning("Database empty. Add a series to begin.")
        return

    titles_df['id'] = titles_df['id'].astype(str)
    
    default_ix = 0
    if st.session_state.selected_series_id:
        match = titles_df[titles_df['id'] == st.session_state.selected_series_id]
        if not match.empty:
            default_ix = int(match.index[0])

    target_title = st.selectbox("Select Series to Inspect", titles_df['title'], index=default_ix)
    
    # 2. Render Stats
    stats_res = fetch_series_stats(engine, target_title)
    if not stats_res.empty:
        stats = stats_res.iloc[0]
        total = stats['total'] or 0
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Chapters", total)
        m2.metric("OCR Progress", f"{int((stats['ocr_done']/total)*100 if total > 0 else 0)}%")
        m3.metric("Summaries", f"{int(stats['summaries_done'] or 0)}")
        m4.metric("Errors", f"{int(stats['errors'] or 0)}", delta_color="inverse")

    st.divider()

    # 3. Fetch Chapter Data
    df_details = fetch_chapter_details(engine, target_title)
    if df_details.empty:
        st.info("No chapters found. Run a 'Scan' in the Index tab.")
        return

    sub_tab_grid, sub_tab_inspect = st.tabs(["📊 Grid View", "🔍 Chapter Inspector"])

    with sub_tab_grid:
        st.dataframe(df_details[['chapter_number', 'ocr_extracted', 'summary_complete']], 
                     width="stretch", hide_index=True, use_container_width=True)

    with sub_tab_inspect:
        # --- 🎯 ROBUST NAVIGATION LOGIC ---
        chapters_list = df_details['chapter_number'].tolist()
        sb_key = f"sb_inspect_{target_title}"
        
        # Initialize state if missing
        if sb_key not in st.session_state:
            st.session_state[sb_key] = chapters_list[0]

        # A. Jump to Chapter (Dropdown First)
        # Note: We don't use 'index=' here because 'key=' handles it automatically
        chapter_to_view = st.selectbox(
            "Jump to Chapter", 
            chapters_list,
            key=sb_key
        )

        # B. Previous and Next Buttons
        current_idx = chapters_list.index(chapter_to_view)
        
        btn_col1, btn_col2 = st.columns(2)
        
        with btn_col1:
            prev_disabled = (current_idx == 0)
            if not prev_disabled:
                prev_val = chapters_list[current_idx - 1]
                st.button(
                    "⬅️ Previous Chapter", 
                    use_container_width=True, 
                    on_click=move_chapter, 
                    args=(sb_key, prev_val)
                )
            else:
                st.button("⬅️ Previous Chapter", use_container_width=True, disabled=True)

        with btn_col2:
            next_disabled = (current_idx == len(chapters_list) - 1)
            if not next_disabled:
                next_val = chapters_list[current_idx + 1]
                st.button(
                    "Next Chapter ➡️", 
                    use_container_width=True, 
                    on_click=move_chapter, 
                    args=(sb_key, next_val)
                )
            else:
                st.button("Next Chapter ➡️", use_container_width=True, disabled=True)

        st.divider()

        # --- CONTENT RENDERING ---
        row = df_details[df_details['chapter_number'] == chapter_to_view].iloc[0]
        
        st.markdown(f"### Chapter {row['chapter_number']} Content")
        
        st.markdown("#### 📝 AI Summary")
        if row['summary_json']:
            st.json(row['summary_json'])
        else:
            st.info("AI Summary not yet generated for this chapter.")

        with st.expander("📄 View Raw OCR Text", expanded=False):
            st.text_area("OCR Content", value=row['ocr_text'] if row['ocr_text'] else "No OCR available.", height=400)