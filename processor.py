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
from core.intelligence import ai_agent, local_agent, arc_agent

from database.session import SessionLocal
from database.models import Series, Chapter, ChapterProcessing, Summary, OCRResult, StoryArc

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
                # 1. Create the new Result record in the new table
                new_result = OCRResult(
                    chapter_id=chapter.id,
                    raw_text=raw_text
                )
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
            
            # Using the 1-to-1 relationship defined in models.py
            ocr_record = chapter.ocr_result
            ocr_text = ocr_record.raw_text if ocr_record else None

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

    def reset_summaries(self, target_inputs):
        """
        Deletes existing summaries and resets the processing flag so Tier 3 will run again.
        Accepts 'all', individual numbers ('1', '2'), or ranges ('1-5', '10-15').
        """
        parsed_targets = set()
        run_all = False

        # --- 1. The Parser ---
        for t in target_inputs:
            t_str = str(t).lower()
            if t_str == 'all':
                run_all = True
                break
            
            if '-' in t_str:
                # Handle ranges like '1-5'
                try:
                    start, end = map(int, t_str.split('-'))
                    if start <= end:
                        parsed_targets.update(range(start, end + 1))
                except ValueError:
                    print(f"⚠️ Warning: Ignored invalid range format '{t}'")
            elif t_str.isdigit():
                # Handle single numbers
                parsed_targets.add(int(t_str))

        # --- 2. Database Query ---
        if run_all:
            chapters_to_reset = self.db.query(Chapter).filter(Chapter.series_id == self.series.id).all()
            print(f"🔄 Preparing to reset ALL summaries for {self.title}...")
        else:
            targets_list = list(parsed_targets)
            if not targets_list:
                print("⚠️ No valid chapter targets provided for reset.")
                return

            chapters_to_reset = self.db.query(Chapter).filter(
                Chapter.series_id == self.series.id,
                Chapter.chapter_number.in_(targets_list)
            ).all()
            
            targets_list.sort()
            print(f"🔄 Preparing to reset summaries for Chapters: {targets_list}...")

        if not chapters_to_reset:
            print("⚠️ No matching chapters found in the DB to reset.")
            return

        # --- 3. The Reset Execution ---
        reset_count = 0
        for ch in chapters_to_reset:
            existing_summary = self.db.query(Summary).filter(Summary.chapter_id == ch.id).first()
            if existing_summary:
                self.db.delete(existing_summary)
            
            proc = self.db.query(ChapterProcessing).filter(ChapterProcessing.chapter_id == ch.id).first()
            if proc:
                proc.summary_complete = False
                reset_count += 1

        self.db.commit()
        print(f"✅ Reset AI status for {reset_count} chapter(s). They are queued for Tier 3.")

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


    def tier_5_arc_synthesis(self):
        """
        Stateful Arc Synthesizer: Batches chapters into chunks to protect API limits,
        passing unresolved narrative arcs to the next batch.
        """
        print(f"\n🗺️ Tier 5: Starting Stateful Arc Synthesis for {self.title}...")

        completed_chapters = (
            self.db.query(Chapter)
            .join(Summary)
            .filter(Chapter.series_id == self.series.id)
            .order_by(Chapter.chapter_number)
            .all()
        )

        if not completed_chapters:
            print("⚠️ No completed chapter summaries found to synthesize.")
            return

        # 1. Prepare all metadata
        all_metadata = []
        for ch in completed_chapters:
            try:
                all_metadata.append({
                    "chapter_number": ch.chapter_number,
                    "metadata": json.loads(ch.summary.content)
                })
            except Exception as e:
                print(f"⚠️ Skipping Ch {ch.chapter_number} due to invalid JSON: {e}")

        # 2. Stateful Batching Logic
        BATCH_SIZE = 100
        all_final_arcs = []
        ongoing_arc_state = None  # The "Baton" we pass between batches

        # Slice the list into chunks of 100
        chunks = [all_metadata[i:i + BATCH_SIZE] for i in range(0, len(all_metadata), BATCH_SIZE)]
        
        print(f"📦 Grouped {len(all_metadata)} chapters into {len(chunks)} batch(es).")

        for index, chunk in enumerate(chunks, 1):
            print(f"🧠 Routing Batch {index}/{len(chunks)} to Arc Agent...")
            
            # Pass the chunk AND the baton
            arc_results = arc_agent.generate_arc_summaries(chunk, previous_ongoing_arc=ongoing_arc_state)

            if not arc_results:
                print(f"❌ Arc Synthesis failed on Batch {index}. Halting.")
                return

            # Add the completed arcs from this batch to our master list
            if arc_results.get("completed_arcs"):
                all_final_arcs.extend(arc_results["completed_arcs"])
            
            # Grab the baton (ongoing arc) for the next loop
            ongoing_arc_state = arc_results.get("ongoing_arc")

        # 3. Cleanup: If the very last batch ends with an ongoing arc, we force it to close
        if ongoing_arc_state:
            print("📝 Finalizing the last ongoing arc...")
            ongoing_arc_state["end_chapter"] = all_metadata[-1]["chapter_number"]
            ongoing_arc_state["status_quo_shift"] = "Series is currently ongoing or arc boundary not yet reached."
            all_final_arcs.append(ongoing_arc_state)

        # 4. Save to Database
        self.db.query(StoryArc).filter(StoryArc.series_id == self.series.id).delete()
        
        new_arcs_count = 0
        for arc_data in all_final_arcs:
            try:
                new_arc = StoryArc(
                    series_id=self.series.id,
                    arc_title=arc_data.get("arc_title", "Unknown Arc"),
                    start_chapter=arc_data.get("start_chapter"),
                    end_chapter=arc_data.get("end_chapter"),
                    arc_summary=json.dumps({
                        "summary": arc_data.get("arc_summary", ""),
                        "core_cast": arc_data.get("core_cast", []),
                        "status_quo_shift": arc_data.get("status_quo_shift", "")
                    }, ensure_ascii=False)
                )
                self.db.add(new_arc)
                new_arcs_count += 1
            except Exception as e:
                print(f"⚠️ Failed to save an arc: {e}")

        self.db.commit()
        print(f"✅ Successfully synthesized and saved {new_arcs_count} Story Arcs.")

    def run_full_pipeline(self, url=None, run_extract=False, run_summarize=False, use_local_ai=False, redo_targets=None, run_arcs=False):
        print(f"\n🚀 PROCESSING: {self.title}")
        print("-" * 40)
        
        try:
            if redo_targets:
                self.reset_summaries(redo_targets)
                run_summarize = True 

            # Only run the base pipeline if run_arcs is NOT the only flag
            if not run_arcs or run_extract or run_summarize:
                run_all = not run_extract and not run_summarize and not run_arcs

                if run_extract or run_all:
                    print("\n--- PHASE 1: EXTRACTION & OCR ---")
                    if not self.tier_1_ingest(url): return
                    self.tier_2_ocr()
                    
                if run_summarize or run_all:
                    print("\n--- PHASE 2: AI SUMMARY ---")
                    self.tier_3_ai(use_local_ai)
                    self.tier_4_cleanup()
            
            # --- NEW: Phase 3 ---
            if run_arcs:
                print("\n--- PHASE 3: ARC SYNTHESIS ---")
                self.tier_5_arc_synthesis()
                
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
    parser.add_argument("--build-arcs", action="store_true", help="Run Tier 5 (Arc Synthesis) to group completed chapters.")

    parser.add_argument("--local-ai", action="store_true", help="Route summaries to local Ollama instead of Gemini.")
    parser.add_argument(
        "--redo-summaries", 
        nargs='+', 
        help="Reset summaries. Accepts numbers (1 2), ranges (1-5), mixes (1 3-5), or 'all'"
    )

    args = parser.parse_args()

    processor = BatchProcessor(args.title, start_chapter=args.start_chapter)
    processor.run_full_pipeline(
        url=args.url, 
        run_extract=args.extract, 
        run_summarize=args.summarize, 
        use_local_ai=args.local_ai,
        redo_targets=args.redo_summaries,
        run_arcs=args.build_arcs # Pass it here
    )