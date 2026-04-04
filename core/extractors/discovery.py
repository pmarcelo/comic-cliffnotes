import subprocess
import json
import logging
import uuid
from typing import List
from sqlalchemy import text, select
from database.session import SessionLocal 
from database.models import Series, SeriesSource, Chapter, ChapterProcessing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Discovery")

def get_web_chapters(source_url: str, offset: float) -> List[float]:
    """Parses the native gallery-dl JSON output for supported sites like WeebCentral."""
    # -j: JSON output
    # -s: Simulate (no download)
    cmd = ["gallery-dl", "-j", "-s", source_url]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # gallery-dl -j usually returns a large JSON array [...]
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error("Failed to parse gallery-dl JSON output.")
            return []

        chapters = []
        
        # Iterate through the returned list of lists
        # Each entry looks like: [6, "url", {"chapter": 135, ...}]
        for entry in data:
            if isinstance(entry, list) and len(entry) >= 3:
                metadata = entry[2]
                if isinstance(metadata, dict) and 'chapter' in metadata:
                    try:
                        raw_num = float(metadata['chapter'])
                        
                        # 🎯 THE FILTER: Only keep whole numbers (23.0, 24.0, etc.)
                        # This skips 23.1, 23.2, 23.5, etc.
                        if raw_num.is_integer():
                            chapters.append(raw_num + offset)
                        else:
                            logger.info(f"⏭️ Skipping intermediary chapter: {raw_num}")
                            
                    except (ValueError, TypeError):
                        continue
        
        return sorted(list(set(chapters))) # Unique and sorted
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Gallery-dl failed: {e.stderr}")
        return []

def sync_series_by_id(series_id: uuid.UUID):
    """The main entry point to update a specific series."""
    # Convert string ID to UUID object if necessary
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

        logger.info(f"Syncing: {source.url}")
        
        web_nums = get_web_chapters(source.url, source.chapter_offset or 0.0)
        
        existing_nums = db.execute(
            select(Chapter.chapter_number).where(Chapter.series_id == series_id)
        ).scalars().all()
        existing_set = set(existing_nums)

        new_chapters = [n for n in web_nums if n not in existing_set]

        if not new_chapters:
            logger.info("Database is already up to date.")
            return

        for num in new_chapters:
            new_chap = Chapter(series_id=series_id, chapter_number=num)
            db.add(new_chap)
            db.flush() 

            new_proc = ChapterProcessing(chapter_id=new_chap.id)
            db.add(new_proc)
            logger.info(f"✨ Found New Chapter: {num}")

        source.last_synced_at = db.execute(text("SELECT now()")).scalar()
        db.commit()
        logger.info(f"Sync complete. Added {len(new_chapters)} chapters.")