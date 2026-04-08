import sys
from pathlib import Path

# --- THE BULLETPROOF PATH FIX ---
# Notice the two .parent calls to jump up from /scripts/ to /comic-cliffnotes/
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from database.session import SessionLocal
from database.models import Chapter, ChapterProcessing, OCRResult

def cleanup_chapter_zeros():
    db = SessionLocal()
    try:
        # Find all chapters where the number is exactly 0
        zero_chapters = db.query(Chapter).filter(Chapter.chapter_number == 0).all()

        if not zero_chapters:
            print("✅ No Chapter 0s found. Your database is already clean!")
            return

        print(f"🧹 Found {len(zero_chapters)} Chapter 0(s). Starting cleanup...")

        deleted_count = 0
        for chap in zero_chapters:
            print(f"🗑️ Deleting Chapter 0 from Series ID: {chap.series_id}")
            
            # 1. Delete OCR Results (if any exist)
            db.query(OCRResult).filter(OCRResult.chapter_id == chap.id).delete()
            
            # 2. Delete Processing Status
            db.query(ChapterProcessing).filter(ChapterProcessing.chapter_id == chap.id).delete()
            
            # 3. Delete the actual Chapter
            db.delete(chap)
            deleted_count += 1

        db.commit()
        print(f"\n✨ SUCCESS: Permanently removed {deleted_count} Chapter 0 records!")

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_chapter_zeros()