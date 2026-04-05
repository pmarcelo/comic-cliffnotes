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
        st.warning("Database empty. Add a series to begin.")
        return

    # 2. Search & Select Layout
    # Use columns to put the search bar and dropdown side-by-side
    col_search, col_select = st.columns([1, 2])
    
    with col_search:
        search_term = st.text_input("🔍 Search Series", placeholder="Type to filter...", label_visibility="collapsed")

    # Filter the dataframe based on search term
    filtered_df = titles_df[titles_df['title'].str.contains(search_term, case=False)] if search_term else titles_df

    with col_select:
        if filtered_df.empty:
            st.error("No matches found.")
            return
            
        # Handle index logic for the selectbox
        # We try to match the session_state ID against our FILTERED list
        default_ix = 0
        if st.session_state.selected_series_id:
            match = filtered_df[filtered_df['id'].astype(str) == str(st.session_state.selected_series_id)]
            if not match.empty:
                default_ix = int(filtered_df.index.get_loc(match.index[0]))

        target_title = st.selectbox(
            "Select Series", 
            filtered_df['title'], 
            index=default_ix, 
            label_visibility="collapsed"
        )
    
    # 3. Render Stats
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

    # 4. Fetch Chapter Data
    df_details = fetch_chapter_details(engine, target_title)
    if df_details.empty:
        st.info("No chapters found. Run a 'Scan' in the Index tab.")
        return

    sub_tab_grid, sub_tab_inspect = st.tabs(["📊 Grid View", "🔍 Chapter Inspector"])

    with sub_tab_grid:
        st.dataframe(
            df_details[['chapter_number', 'url', 'ocr_extracted', 'summary_complete']], 
            column_config={
                "url": st.column_config.LinkColumn("Source URL", width="medium"),
                "chapter_number": "Ch #",
                "ocr_extracted": "OCR ✅",
                "summary_complete": "Summary ✅"
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
        
        with btn_col1:
            if current_idx > 0:
                prev_val = chapters_list[current_idx - 1]
                st.button("⬅️ Previous", use_container_width=True, on_click=move_chapter, args=(sb_key, prev_val))
            else:
                st.button("⬅️ Previous", use_container_width=True, disabled=True)

        with btn_col2:
            if current_idx < len(chapters_list) - 1:
                next_val = chapters_list[current_idx + 1]
                st.button("Next ➡️", use_container_width=True, on_click=move_chapter, args=(sb_key, next_val))
            else:
                st.button("Next ➡️", use_container_width=True, disabled=True)

        st.divider()

        # --- CONTENT RENDERING ---
        row = df_details[df_details['chapter_number'] == chapter_to_view].iloc[0]
        
        col_header, col_link = st.columns([3, 1])
        with col_header:
            st.markdown(f"### Chapter {row['chapter_number']}")
        with col_link:
            if row['url']:
                st.link_button("🌐 Open Source", row['url'], use_container_width=True)
        
        st.markdown("#### 📝 AI Summary")
        if row['summary_json']:
            st.json(row['summary_json'])
        else:
            st.info("AI Summary not yet generated for this chapter.")

        with st.expander("📄 View Raw OCR Text", expanded=False):
            st.text_area("OCR Content", value=row['ocr_text'] if row['ocr_text'] else "No OCR available.", height=400)