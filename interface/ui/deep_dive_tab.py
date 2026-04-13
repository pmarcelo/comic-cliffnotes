import streamlit as st
import pandas as pd
import os
from sqlalchemy import text

# Detect Mode
IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"

@st.cache_data(ttl=30)
def fetch_series_stats(_engine, series_title):
    """
    🎯 HYBRID LOGIC: 
    If Online, we check for the existence of summary/ocr records directly.
    If Local, we use the 'chapter_processing' metadata table.
    """
    if IS_ONLINE:
        query = text("""
            SELECT COUNT(c.id) as total,
                   COUNT(ocr.id) as ocr_done,
                   COUNT(summ.id) as summaries_done,
                   0 as errors -- Error tracking is local-only
            FROM chapters c 
            JOIN series s ON c.series_id = s.id
            LEFT JOIN summaries summ ON c.id = summ.chapter_id
            LEFT JOIN ocr_results ocr ON c.id = ocr.chapter_id
            WHERE s.title = :title
        """)
    else:
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
    """
    Fetches chapter-by-chapter content.
    """
    if IS_ONLINE:
        query = text("""
            SELECT c.chapter_number, c.url, 
                   (summ.id IS NOT NULL) as summary_complete, 
                   (ocr.id IS NOT NULL) as ocr_extracted,
                   summ.content as summary_json, ocr.raw_text as ocr_text
            FROM chapters c 
            JOIN series ser ON c.series_id = ser.id
            LEFT JOIN summaries summ ON c.id = summ.chapter_id
            LEFT JOIN ocr_results ocr ON c.id = ocr.chapter_id
            WHERE ser.title = :title 
            ORDER BY c.chapter_number ASC
        """)
    else:
        query = text("""
            SELECT c.chapter_number, c.url, cp.ocr_extracted, cp.summary_complete, 
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
    st.session_state[key] = new_val

@st.fragment
def render_deep_dive(engine):
    # 1. Fetch Full Series List
    titles_df = pd.read_sql("SELECT id, title FROM series ORDER BY title ASC", engine)
    
    if titles_df.empty:
        st.warning("Database empty. Sync data from your local machine to begin.")
        return

    # 2. Search & Select Layout
    col_search, col_select = st.columns([1, 2])
    with col_search:
        search_term = st.text_input("🔍 Search Series", placeholder="Filter...", label_visibility="collapsed")

    filtered_df = titles_df[titles_df['title'].str.contains(search_term, case=False)] if search_term else titles_df

    with col_select:
        if filtered_df.empty:
            st.error("No matches.")
            return
            
        default_ix = 0
        if st.session_state.selected_series_id:
            match = filtered_df[filtered_df['id'].astype(str) == str(st.session_state.selected_series_id)]
            if not match.empty:
                default_ix = int(filtered_df.index.get_loc(match.index[0]))

        target_title = st.selectbox("Select Series", filtered_df['title'], index=default_ix, label_visibility="collapsed")
    
    # 3. Render Stats
    stats_res = fetch_series_stats(engine, target_title)
    if not stats_res.empty:
        stats = stats_res.iloc[0]
        total = stats['total'] or 0
        
        # Mobile-friendly columns: Use 2x2 for metrics on cloud
        if IS_ONLINE:
            m1, m2 = st.columns(2)
            m3, m4 = st.columns(2)
        else:
            m1, m2, m3, m4 = st.columns(4)

        m1.metric("Chapters", total)
        m2.metric("OCR", f"{int((stats['ocr_done']/total)*100 if total > 0 else 0)}%")
        m3.metric("Summarized", f"{int(stats['summaries_done'] or 0)}")
        
        if not IS_ONLINE:
            m4.metric("Errors", f"{int(stats['errors'] or 0)}", delta_color="inverse")
        else:
            m4.metric("Mode", "Remote")

    st.divider()

    # 4. Fetch Chapter Data
    df_details = fetch_chapter_details(engine, target_title)
    if df_details.empty:
        st.info("No content found for this series.")
        return

    sub_tab_inspect, sub_tab_grid = st.tabs(["🔍 Inspector", "📊 Chapter List"])

    with sub_tab_grid:
        st.dataframe(
            df_details[['chapter_number', 'summary_complete', 'ocr_extracted']], 
            column_config={
                "chapter_number": "Ch #",
                "summary_complete": "Summary ✅",
                "ocr_extracted": "OCR ✅"
            },
            width="stretch", 
            hide_index=True, 
            use_container_width=True
        )

    with sub_tab_inspect:
        chapters_list = df_details['chapter_number'].tolist()
        sb_key = f"sb_inspect_{target_title}"
        
        if sb_key not in st.session_state:
            st.session_state[sb_key] = chapters_list[0]

        chapter_to_view = st.selectbox("Jump to Chapter", chapters_list, key=sb_key)

        current_idx = chapters_list.index(chapter_to_view)
        btn_col1, btn_col2 = st.columns(2)
        
        # Massive buttons for mobile thumbs
        with btn_col1:
            if current_idx > 0:
                prev_val = chapters_list[current_idx - 1]
                st.button("⬅️ PREV", use_container_width=True, on_click=move_chapter, args=(sb_key, prev_val))
            else:
                st.button("⬅️ PREV", use_container_width=True, disabled=True)

        with btn_col2:
            if current_idx < len(chapters_list) - 1:
                next_val = chapters_list[current_idx + 1]
                st.button("NEXT ➡️", use_container_width=True, on_click=move_chapter, args=(sb_key, next_val))
            else:
                st.button("NEXT ➡️", use_container_width=True, disabled=True)

        st.divider()

        # --- CONTENT RENDERING ---
        row = df_details[df_details['chapter_number'] == chapter_to_view].iloc[0]
        
        col_header, col_link = st.columns([2, 1])
        col_header.markdown(f"### Chapter {row['chapter_number']}")
        
        if row['url']:
            col_link.link_button("🌐 Source", row['url'], use_container_width=True)
        
        st.markdown("#### 📝 AI Summary")
        if row['summary_json']:
            # Render the structured JSON content
            st.json(row['summary_json'])
        else:
            st.info("Summary not yet generated.")

        if row['ocr_text']:
            with st.expander("📄 Raw Transcript", expanded=False):
                st.text(row['ocr_text'])