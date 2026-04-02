from core import config
from core.processors import ocr_engine
from core.utils import file_io
from database.models import Chapter, ChapterProcessing, OCRResult


class OCRManager:
    def __init__(self, db_session, series, title):
        self.db = db_session
        self.series = series
        self.title = title

    def process_chapters(self):
        """Finds chapters in DB missing OCR and processes them."""
        todo = (
            self.db.query(ChapterProcessing)
            .join(Chapter)
            .filter(Chapter.series_id == self.series.id)
            .filter(ChapterProcessing.ocr_extracted == False)
            .order_by(Chapter.chapter_number)
            .all()
        )

        if not todo:
            print("⏩ Tier 2: OCR already complete for all chapters. Skipping.")
            return

        series_slug = file_io.get_safe_title(self.title)
        # Use the base extracted_images directory as the anchor
        base_dir = config.DATA_DIR / "extracted_images"

        print(
            f"📖 Tier 2: Starting Batch OCR for {series_slug} ({len(todo)} chapters)..."
        )

        for count, proc in enumerate(todo, 1):
            chapter = proc.chapter

            # Absolute path: .../extracted_images/test_/1
            image_path = base_dir / series_slug / str(chapter.chapter_number)

            print(f"[{count}/{len(todo)}] OCRing Chapter {chapter.chapter_number}")

            if not image_path.exists():
                # We can keep a fallback, but Tier 1 should have prevented this
                print(f"⚠️ Path not found: {image_path}")
                proc.has_error = True
                self.db.commit()
                continue

            raw_text = ocr_engine.extract_text_from_images(image_path)

            if raw_text:
                # 1. Create the new Result record in the new table
                new_result = OCRResult(chapter_id=chapter.id, raw_text=raw_text)
                self.db.add(new_result)

                # 2. Update the Processing status (State only, no text)
                proc.ocr_extracted = True
                proc.has_error = False

                self.db.commit()
                print(f"✅ OCR Saved to Vault for Chapter {chapter.chapter_number}")
            else:
                print(f"⚠️ OCR Failed: No text found in {image_path}")
                proc.has_error = True
                self.db.commit()
