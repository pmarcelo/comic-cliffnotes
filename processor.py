import os
import argparse
import shutil
import time
import uuid
from pathlib import Path
import json 

from core import config
from core.utils import file_io
from core.extractors import cloud_drive
from core.processors import ocr_engine
from core.intelligence import ai_agent, local_agent 

from database.session import SessionLocal
from database.models import Series, Chapter, ChapterProcessing, Summary

class BatchProcessor:
    def __init__(self, title, start_chapter=1):
        self.title = title
        self.slug = file_io.get_safe_title(title)
        self.start_chapter = start_chapter
        
        # 📂 Directory Setup (Image workspace only)
        self.extract_dir = config.DATA_DIR / "extracted_images" / self.slug
        
        # Initialize DB Session
        self.db = SessionLocal()
        self.series = self._get_or_create_series()

    def _get_or_create_series(self):
        """Ensures the series exists in Postgres."""
        series = self.db.query(Series).filter(Series.title == self.title).first()
        if not series:
            print(f"🆕 Initializing Series in Database: {self.title}")
            series = Series(title=self.title)
            self.db.add(series)
            self.db.commit()
            self.db.refresh(series)
        return series

    def tier_1_ingest(self, url):
        print(f"📥 Tier 1: Ingesting...")
        
        try:
            # --- 1. Pre-Flight Check (Smart Skip) ---
            series_slug = file_io.get_safe_title(self.title)
            series_base_dir = config.DATA_DIR / "extracted_images" / series_slug
            base_extract_path = None
            
            # Check if we already have numbered folders on disk
            if series_base_dir.exists():
                existing_folders = [d for d in series_base_dir.iterdir() if d.is_dir() and d.name.isdigit()]
                if existing_folders:
                    print(f"  ℹ️ Found {len(existing_folders)} existing chapter folders for {series_slug}.")
                    print(f"  ⏩ Skipping download; verifying DB sync.")
                else:
                    base_extract_path = cloud_drive.fetch_and_unpack(self.title, url)
            else:
                base_extract_path = cloud_drive.fetch_and_unpack(self.title, url)

            # --- 2. Smart Scanner (Only run if we actually unzipped something) ---
            if base_extract_path:
                chapter_folders = cloud_drive.scan_for_chapter_folders(base_extract_path)
            else:
                chapter_folders = [] # No new files to move, but we will still check DB rows

        except Exception as e:
            print(f"❌ Ingest Failed during Download/Scan: {e}")
            return False
            print(f"❌ Ingest Failed during Download/Scan: {e}")
            return False

        # 3. Determine our starting point
        # Get all existing numbers to check against
        existing_nums = [n[0] for n in self.db.query(Chapter.chapter_number)
                         .filter(Chapter.series_id == self.series.id).all()]
        
        # If DB has chapters, start after the highest. Otherwise, use passed-in start_chapter.
        next_num = max(existing_nums) + 1 if existing_nums else self.start_chapter

        # 4. The "Librarian" Loop: Register AND Reorganize
        for folder_path in chapter_folders:
            # Check if this specific chapter number already exists
            exists = self.db.query(Chapter).filter(
                Chapter.series_id == self.series.id, 
                Chapter.chapter_number == next_num
            ).first()

            if not exists:
                # --- DATABASE WORK ---
                new_ch = Chapter(series_id=self.series.id, chapter_number=next_num)
                self.db.add(new_ch)
                self.db.flush() # Get the new_ch.id
                
                proc = ChapterProcessing(chapter_id=new_ch.id)
                self.db.add(proc)
                print(f"  ✅ DB Registered: Ch {next_num}")
            else:
                print(f"  ℹ️  Ch {next_num} already exists in DB. Checking files...")

            # --- FILESYSTEM WORK ---
            # We do this even if 'exists' is true, in case a previous run crashed 
            # after DB registration but before file movement.
            series_slug = file_io.get_safe_title(self.title)
            target_base = config.DATA_DIR / "extracted_images" / series_slug
            target_path = target_base / str(next_num)

            # Only move files if the target folder is empty/missing
            if not target_path.exists() or not any(target_path.iterdir()):
                target_path.mkdir(parents=True, exist_ok=True)
                for file in folder_path.iterdir():
                    if file.is_file():
                        shutil.move(str(file), str(target_path / file.name))
                print(f"  📂 Files Organized: {target_path}")

            # ALWAYS increment next_num to move to the next folder/record in the sequence
            next_num += 1
                
        # 5. Cleanup the empty 'sync_ingest' shell
        if base_extract_path and base_extract_path.exists():
            shutil.rmtree(base_extract_path)
                
        self.db.commit()
        return True
    
    def tier_2_ocr(self):
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
        
        print(f"📖 Tier 2: Starting Batch OCR for {series_slug} ({len(todo)} chapters)...")
        
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
                proc.raw_ocr_text = raw_text
                proc.ocr_extracted = True
                proc.has_error = False
                # Use flush here if you want to commit all at the end, 
                # or keep commit() to save progress as you go (safer for long runs)
                self.db.commit()
                print(f"✅ OCR Saved to DB.")
            else:
                print(f"⚠️ OCR Failed: No text found in {image_path}")
                proc.has_error = True
                self.db.commit()

    def tier_3_ai(self, use_local_ai=False): 
        """Generates summaries for OCR-ready chapters."""
        todo = (
            self.db.query(ChapterProcessing)
            .join(Chapter)
            .filter(Chapter.series_id == self.series.id)
            .filter(ChapterProcessing.ocr_extracted == True)
            .filter(ChapterProcessing.summary_complete == False)
            .order_by(Chapter.chapter_number)
            .all()
        )

        if not todo:
            print("⏩ Tier 3: AI summaries complete. Skipping.")
            return

        print(f"🧠 Tier 3: Running AI Synthesis for {len(todo)} chapters...")
        for count, proc in enumerate(todo, 1):
            chapter = proc.chapter
            ocr_text = proc.raw_ocr_text

            # --- 1. Skip Empty OCR (Action-only chapters) ---
            if not ocr_text or len(ocr_text.strip()) < 10:
                print(f"⚠️ Ch {chapter.chapter_number} has no meaningful OCR text. Marking as processed.")
                proc.summary_complete = True 
                self.db.commit()
                continue

            try:
                if use_local_ai:
                    print(f"🤖 Routing Ch {chapter.chapter_number} to Local LLM (Ollama)...")
                    ai_results = local_agent.generate_summary(ocr_text)
                else:
                    print(f"☁️ Routing Ch {chapter.chapter_number} to Cloud API (Gemini)...")
                    ai_results = ai_agent.generate_summary(ocr_text)
                
                if ai_results:
                    # --- 2. JSON Integrity Check ---
                    # ensure_ascii=False keeps the text readable in the DB
                    content_json_str = json.dumps(ai_results, ensure_ascii=False) 
                    
                    new_summary = Summary(
                        chapter_id=chapter.id,
                        content=content_json_str
                    )
                    self.db.add(new_summary)
                    
                    # --- 3. Finalize DB State ---
                    proc.summary_complete = True
                    self.db.commit()
                    print(f"✅ Saved Summary for Chapter {chapter.chapter_number}")
                
            except Exception as e:
                # We break here because if the AI service is down/rate-limited, 
                # there's no point in looping through the rest of the batch.
                print(f"\n🛑 FATAL: AI Service Failed on Ch {chapter.chapter_number}: {e}")
                break 
            
            # Rate limiting for Cloud APIs (skip on last item)
            if not use_local_ai and count < len(todo):
                print("⏳ Pacing Cloud API (10s)...")
                time.sleep(10)

    def tier_4_cleanup(self):
        """Cleanup image workspace if all DB processing flags are set."""
        total_ch = self.db.query(Chapter).filter(Chapter.series_id == self.series.id).count()
        completed_ch = (
            self.db.query(ChapterProcessing)
            .join(Chapter)
            .filter(Chapter.series_id == self.series.id)
            .filter(ChapterProcessing.summary_complete == True)
            .count()
        )

        if total_ch > 0 and completed_ch == total_ch:
            print(f"\n🧹 Tier 4: All chapters processed in DB. Cleaning up workspace...")
            if self.extract_dir.exists():
                shutil.rmtree(self.extract_dir)
                print(f"🗑️ Deleted image workspace: {self.extract_dir}")
        else:
            print(f"\n⏳ Tier 4: Cleanup deferred ({completed_ch}/{total_ch} complete).")

    def run_full_pipeline(self, url=None, run_extract=False, run_summarize=False, use_local_ai=False):
        print(f"\n🚀 PROCESSING: {self.title}")
        print("-" * 40)
        
        # Determine which phases to run based on flags. If neither is set, run all.
        run_all = not run_extract and not run_summarize

        try:
            if run_extract or run_all:
                print("\n--- PHASE 1: EXTRACTION & OCR ---")
                if not self.tier_1_ingest(url): return
                self.tier_2_ocr()
                
            if run_summarize or run_all:
                print("\n--- PHASE 2: AI SUMMARY ---")
                self.tier_3_ai(use_local_ai)
                self.tier_4_cleanup()
        finally:
            self.db.close()
        
        print("\n✨ PIPELINE COMPLETE ✨")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--title", required=True)
    parser.add_argument("-u", "--url", help="GDrive URL for Ingest")
    parser.add_argument("-c", "--start-chapter", type=int, default=1)
    
    parser.add_argument("--extract", action="store_true", help="Run Tiers 1 & 2 (Download and OCR) only.")
    parser.add_argument("--summarize", action="store_true", help="Run Tiers 3 & 4 (AI and Cleanup) only.")
    parser.add_argument("--local-ai", action="store_true", help="Route summaries to local Ollama instead of Gemini.")
    
    args = parser.parse_args()

    processor = BatchProcessor(args.title, start_chapter=args.start_chapter)
    processor.run_full_pipeline(
        url=args.url, 
        run_extract=args.extract, 
        run_summarize=args.summarize, 
        use_local_ai=args.local_ai
    )