import logging
from core import config
from core.processors import ocr_engine
from core.utils import file_io
from core.extractors.drive_client import DriveClient
from database.models import Chapter, ChapterProcessing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OCRManager")


class OCRManager:
    def __init__(self, db_session, series, title):
        self.db = db_session
        self.series = series
        self.title = title
        self.drive_client = DriveClient()

    def process_chapters(self):
        """Finds chapters in DB missing OCR and streams text directly to Google Drive."""
        todo = (
            self.db.query(ChapterProcessing)
            .join(Chapter)
            .filter(Chapter.series_id == self.series.id)
            .filter(ChapterProcessing.ocr_extracted == False)
            .order_by(Chapter.chapter_number)
            .all()
        )

        if not todo:
            print("🏁 OCR already complete for all chapters. Skipping.")
            return

        series_slug = file_io.get_safe_title(self.title)
        base_dir = config.DATA_DIR / "extracted_images"

        print(
            f"🧠 Starting Batch OCR for {series_slug} ({len(todo)} chapters), "
            f"streaming to Google Drive..."
        )

        for count, proc in enumerate(todo, 1):
            chapter = proc.chapter
            chapter_number_string = file_io.get_chapter_folder_name(chapter.chapter_number)
            image_path = base_dir / series_slug / chapter_number_string

            print(f"[{count}/{len(todo)}] OCRing Chapter {chapter_number_string}...")

            # 1. 🛡️ THE PENDING RECORD SAFETY CHECK
            # If the folder doesn't exist or is completely empty, it is a Pending chapter.
            if not image_path.exists() or not any(image_path.iterdir()):
                print(f"⏭️ No images found for Ch {chapter.chapter_number}. Leaving in Pending state.")
                continue

            # 2. 🛡️ .part File Sanity Check
            # If gallery-dl left .part files, the download is incomplete.
            incomplete_files = list(image_path.glob("*.part"))
            if incomplete_files:
                print(f"⚠️ Incomplete Download: {len(incomplete_files)} '.part' files in {chapter_number_string}. Skipping.")
                proc.has_error = True
                self.db.commit()
                continue

            # 3. 🛡️ Image Validation Check
            # Ensure there are actually JPEGs/PNGs to read
            images = list(image_path.glob("*.jpg")) + list(image_path.glob("*.png"))
            if not images:
                print(f"❌ No valid images found in {image_path}. Skipping.")
                proc.has_error = True
                self.db.commit()
                continue

            # 4. Perform OCR
            raw_text = ocr_engine.extract_text_from_images(image_path)

            if raw_text:
                try:
                    # Upload directly to Google Drive (no local database storage of raw text)
                    file_name = f"{series_slug}_ch{chapter.chapter_number}.txt"
                    drive_file_id = self.drive_client.upload_text(
                        config.DRIVE_OCR_FOLDER_ID,
                        file_name,
                        raw_text
                    )

                    # Save Drive file ID reference to Chapter
                    chapter.drive_file_id = drive_file_id
                    proc.ocr_extracted = True
                    proc.has_error = False

                    self.db.commit()
                    print(f"✅ Chapter {chapter.chapter_number} OCR → Drive: {drive_file_id}")

                except Exception as e:
                    # Drive upload failed - leave ocr_extracted=False for retry
                    logger.error(f"❌ Drive upload failed for Ch {chapter.chapter_number}: {e}")
                    proc.has_error = True
                    self.db.commit()
            else:
                print(f"❌ OCR Failed: No text found in {image_path}")
                proc.has_error = True
                self.db.commit()