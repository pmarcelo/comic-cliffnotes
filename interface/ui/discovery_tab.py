import streamlit as st
import uuid
import os
from sqlalchemy import text
from core.extractors.discovery import sync_series_by_id

# Detect Mode
IS_ONLINE = os.getenv("CLIFFNOTES_MODE") == "ONLINE"

@st.fragment
def render_discovery(engine):
    """
    Modular fragment for Global Discovery.
    """
    st.header("🌐 Global Discovery")
    
    # 🎯 CLOUD DEFENSE: Disable writes in online mode
    if IS_ONLINE:
        st.info("💡 **Discovery is in Read-Only Mode.**")
        st.markdown("""
        New series must be added via your local machine to ensure correct processing.
        Once added and synced locally, they will appear here automatically.
        """)
        return

    st.caption("Provide a Title and a WeebCentral/MangaBuddy URL to instantly scout and add a series.")

    # Use a form to prevent rerun on every keystroke
    with st.form("quick_import_form", clear_on_submit=True):
        new_title = st.text_input("Series Title", placeholder="e.g. Demon Devourer")
        new_source_url = st.text_input("Source URL", placeholder="https://weebcentral.com/series/...")
        import_btn = st.form_submit_button("🚀 Add & Scan Series")

    if import_btn:
        if not new_title or not new_source_url:
            st.error("Both Title and Source URL are required.")
            return

        try:
            with engine.begin() as conn:
                # 1. Duplicate Check
                exists = conn.execute(
                    text("SELECT id FROM series WHERE title = :t"), 
                    {"t": new_title}
                ).fetchone()
                
                if exists:
                    st.warning(f"'{new_title}' is already in your library.")
                    return

                # 2. Database Insertion
                series_uuid = str(uuid.uuid4())
                conn.execute(text("""
                    INSERT INTO series (id, title, created_at, updated_at)
                    VALUES (:id, :t, now(), now())
                """), {"id": series_uuid, "t": new_title})

                conn.execute(text("""
                    INSERT INTO series_sources (
                        id, series_id, url, chapter_offset, priority, 
                        is_active, created_at, updated_at
                    ) VALUES (
                        :s_id, :ser_id, :url, 0.0, 1, 
                        True, now(), now()
                    )
                """), {
                    "s_id": str(uuid.uuid4()),
                    "ser_id": series_uuid,
                    "url": new_source_url
                })

            # 3. Trigger Discovery (Inside the fragment)
            with st.spinner(f"Scouting '{new_title}' for chapters..."):
                sync_series_by_id(series_uuid)
            
            st.success(f"✨ Successfully added '{new_title}'!")
            st.balloons()
            
            # Clear the Index cache so the new series appears in Tab 1
            st.cache_data.clear()
            
        except Exception as e:
            st.error(f"Failed to import series: {str(e)}")