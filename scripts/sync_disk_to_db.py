import sys
import os
from pathlib import Path

# Path fix
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from database.session import SessionLocal
from database.models import Chapter, ChapterProcessing, Series
from core.utils import file_io

def sync_all_extracted_status():
    db = SessionLocal()
    chapters = db.query(Chapter).all()
    print(f"Checking disk for {len(chapters)} chapters...")

    updated_count = 0
    for ch in chapters:
        # Resolve the folder path
        series_slug = file_io.get_safe_title(ch.series.title)
        folder_name = file_io.get_chapter_folder_name(ch.chapter_number)
        path = Path("data/extracted_images") / series_slug / folder_name

        # If files exist, mark as extracted
        if path.exists() and any(path.iterdir()):
            proc = db.query(ChapterProcessing).filter(ChapterProcessing.chapter_id == ch.id).first()
            if not proc:
                proc = ChapterProcessing(chapter_id=ch.id)
                db.add(proc)
            
            if not proc.is_extracted:
                proc.is_extracted = True
                updated_count += 1
    
    db.commit()
    print(f"✅ Finished! Synchronized {updated_count} chapters to the database.")
    db.close()

if __name__ == "__main__":
    sync_all_extracted_status()