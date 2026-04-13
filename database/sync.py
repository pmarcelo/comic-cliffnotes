import logging
from sqlalchemy.dialects.postgresql import insert
from database.session import SessionLocal, CloudSession
from database.models import Series, SeriesMetadata, Chapter, Summary, BridgeCache, StoryArc

logger = logging.getLogger(__name__)

import json

def upsert_record(cloud_db, model, record):
    """
    Dynamically generates a PostgreSQL UPSERT for any SQLAlchemy model.
    Handles JSONB conversion and 'null' string cleanup.
    """
    record_dict = {}
    for c in record.__table__.columns:
        value = getattr(record, c.name)
        
        # 🎯 FIX: Convert 'null' strings or JSON strings back into objects
        # This prevents CockroachDB from crashing on '::JSONB' casts
        if c.type.python_type in [dict, list] or "JSON" in str(c.type):
            if isinstance(value, str):
                if value.lower() == "null" or value.strip() == "":
                    value = None
                else:
                    try:
                        value = json.loads(value)
                    except:
                        pass # Leave as string if it's not valid JSON
        
        record_dict[c.name] = value
    
    stmt = insert(model).values(record_dict)
    
    update_dict = {
        c.name: c
        for c in stmt.excluded
        if not c.primary_key and c.name != "created_at"
    }
    
    if update_dict:
        stmt = stmt.on_conflict_do_update(
            index_elements=[model.id],
            set_=update_dict
        )
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=[model.id])

    cloud_db.execute(stmt)


def push_chapter_to_cloud(chapter_id: str):
    """
    Pushes a specific chapter, its summary, and its parent series 
    up to the CockroachDB cloud replica.
    """
    if not CloudSession:
        logger.warning("CloudSession not configured. Skipping cloud sync.")
        return

    local_db = SessionLocal()
    cloud_db = CloudSession()

    try:
        # 1. Fetch the local records
        chapter = local_db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            return
            
        series = local_db.query(Series).filter(Series.id == chapter.series_id).first()
        summary = local_db.query(Summary).filter(Summary.chapter_id == chapter_id).first()
        metadata = local_db.query(SeriesMetadata).filter(SeriesMetadata.series_id == series.id).first()

        # 2. Push to Cloud (Order matters due to Foreign Keys!)
        # First: Series & Metadata
        if series:
            upsert_record(cloud_db, Series, series)
        if metadata:
            upsert_record(cloud_db, SeriesMetadata, metadata)
            
        # Second: Chapter
        upsert_record(cloud_db, Chapter, chapter)
        
        # Third: Summary
        if summary:
            upsert_record(cloud_db, Summary, summary)
            
        cloud_db.commit()
        logger.info(f"Successfully synced Chapter {chapter.chapter_number} to cloud.")

    except Exception as e:
        cloud_db.rollback()
        logger.error(f"Cloud sync failed for chapter {chapter_id}: {str(e)}")
    finally:
        local_db.close()
        cloud_db.close()

def push_series_bridge_cache(series_id: str):
    """
    Pushes all BridgeCache (Previously On...) entries for a series to the cloud.
    """
    if not CloudSession:
        return

    local_db = SessionLocal()
    cloud_db = CloudSession()

    try:
        caches = local_db.query(BridgeCache).filter(BridgeCache.series_id == series_id).all()
        for cache in caches:
            upsert_record(cloud_db, BridgeCache, cache)
            
        cloud_db.commit()
    except Exception as e:
        cloud_db.rollback()
        logger.error(f"Cloud sync failed for BridgeCache (Series {series_id}): {str(e)}")
    finally:
        local_db.close()
        cloud_db.close()

# -------------------------------------------------------------------------
# RUNNER UTILITY: Bulk sync all historical data
# -------------------------------------------------------------------------
def sync_all_to_cloud():
    """One-off utility to push the entire local database to the cloud replica."""
    if not CloudSession:
        print("❌ CloudSession not configured. Check CLOUD_DATABASE_URL in your .env")
        return

    local_db = SessionLocal()
    print("🚀 Starting full cloud sync...")

    try:
        # 1. Sync all chapters (which automatically syncs the Series, Metadata, and Summaries)
        all_chapters = local_db.query(Chapter).all()
        total = len(all_chapters)
        
        if total == 0:
            print("No chapters found in local database.")
            return

        for i, chapter in enumerate(all_chapters, 1):
            print(f"Syncing chapter {i}/{total}: {chapter.chapter_number}...")
            push_chapter_to_cloud(str(chapter.id))
        
        # 2. Sync all BridgeCaches
        print("Syncing Bridge Caches...")
        all_series = local_db.query(Series).all()
        for series in all_series:
            push_series_bridge_cache(str(series.id))
            
        print("✅ Full sync complete! Your cloud replica is up to date.")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
    finally:
        local_db.close()

if __name__ == "__main__":
    sync_all_to_cloud()