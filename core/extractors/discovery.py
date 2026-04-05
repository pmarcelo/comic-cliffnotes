import subprocess
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from sqlalchemy import text, select
from database.session import SessionLocal 
from database.models import Series, SeriesSource, Chapter, ChapterProcessing

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Discovery")

def get_web_chapters(source_url: str, offset: float) -> List[Dict[str, Any]]:
    """
    Parses native gallery-dl JSON to extract chapter numbers AND direct URLs.
    Returns: List of dicts e.g., [{"number": 1.0, "url": "https://..."}]
    """
    # -j: JSON output
    # -s: Simulate (no download)
    cmd = ["gallery-dl", "-j", "-s", source_url]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error("Failed to parse gallery-dl JSON output.")
            return []

        chapter_data = []
        seen_numbers = set()
        
        # entry looks like: [6, "https://weebcentral.com/chapters/xyz", {"chapter": "1", ...}]
        for entry in data:
            if isinstance(entry, list) and len(entry) >= 3:
                direct_url = entry[1]
                metadata = entry[2]
                
                if isinstance(metadata, dict) and 'chapter' in metadata:
                    try:
                        raw_num = float(metadata['chapter'])
                        
                        # 🎯 THE FILTER: Only whole numbers (skips 23.1, etc.)
                        if raw_num.is_integer():
                            final_num = raw_num + offset
                            
                            # Avoid duplicates in the same scan
                            if final_num not in seen_numbers:
                                chapter_data.append({
                                    "number": final_num,
                                    "url": direct_url
                                })
                                seen_numbers.add(final_num)
                        else:
                            logger.info(f"⏭️ Skipping intermediary chapter: {raw_num}")
                            
                    except (ValueError, TypeError):
                        continue
        
        # Sort by chapter number
        return sorted(chapter_data, key=lambda x: x["number"])
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Gallery-dl failed: {e.stderr}")
        return []

def sync_series_by_id(series_id: uuid.UUID):
    """Updates the database with new chapters and populates URLs for existing ones."""
    if isinstance(series_id, str):
        series_id = uuid.UUID(series_id)

    with SessionLocal() as db:
        source = db.execute(
            select(SeriesSource).where(
                SeriesSource.series_id == series_id, 
                SeriesSource.is_active == True
            ).order_by(SeriesSource.priority.asc())
        ).scalars().first()

        if not source:
            logger.error(f"❌ Series {series_id} has no active source.")
            return

        logger.info(f"🔍 Scanning for updates: {source.url}")
        
        # 1. Get fresh data from the web (numbers + URLs)
        web_chapters = get_web_chapters(source.url, source.chapter_offset or 0.0)
        
        # 2. Get existing chapters from DB to check for missing URLs or new entries
        existing_chapters = db.execute(
            select(Chapter).where(Chapter.series_id == series_id)
        ).scalars().all()
        
        # Create a mapping for quick lookup: {number: ChapterObject}
        chapter_map = {c.chapter_number: c for c in existing_chapters}

        new_count = 0
        update_count = 0

        for web_item in web_chapters:
            num = web_item["number"]
            url = web_item["url"]

            if num not in chapter_map:
                # ✨ CASE A: Brand new chapter
                new_chap = Chapter(
                    series_id=series_id, 
                    chapter_number=num,
                    url=url  # 🎯 Populating the new URL field
                )
                db.add(new_chap)
                db.flush() # Get the ID for ChapterProcessing

                new_proc = ChapterProcessing(chapter_id=new_chap.id)
                db.add(new_proc)
                
                logger.info(f"✨ New Chapter found: {num}")
                new_count += 1
            else:
                # 🔄 CASE B: Existing chapter, check if we need to update the URL
                existing_chap = chapter_map[num]
                if not existing_chap.url:
                    existing_chap.url = url
                    update_count += 1

        # Update the sync timestamp
        source.last_synced_at = datetime.now(timezone.utc)
        
        db.commit()
        
        if new_count > 0 or update_count > 0:
            logger.info(f"✅ Sync complete: {new_count} new, {update_count} URLs updated.")
        else:
            logger.info("ℹ️ Database is already up to date.")