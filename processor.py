import os
import argparse
import shutil
import time
from pathlib import Path
from core import config
from core.utils import file_io
from core.extractors import cloud_drive
from core.processors import ocr_engine
from core.intelligence import ai_agent

class BatchProcessor:
    def __init__(self, title, start_chapter=1):
        self.title = title
        self.slug = file_io.get_safe_title(title)
        
        # 📂 Directory Setup (Categorized Artifacts)
        self.manga_dir = config.ARTIFACTS_DIR / self.slug
        self.ocr_dir = self.manga_dir / "raw_ocr"
        self.summary_dir = self.manga_dir / "summaries"
        self.metadata_path = self.manga_dir / "metadata.json"
        self.extract_dir = config.DATA_DIR / "extracted_images" / self.slug
        
        # Ensure directory hierarchy exists
        for d in [self.manga_dir, self.ocr_dir, self.summary_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.manifest = self._load_or_create_manifest()
        self.start_chapter = start_chapter

    def _load_or_create_manifest(self):
        """Loads the master ledger or initializes a new one."""
        if self.metadata_path.exists():
            return file_io.load_json(self.metadata_path)
        return {"manga_title": self.title, "slug": self.slug, "chapter_map": {}}

    def tier_1_ingest(self, url):
        """STATION 1: Cloud Ingest -> Downloads and Unpacks archives."""
        if not url and self.metadata_path.exists():
            print(f"⏩ Tier 1: Metadata exists and no new URL provided. Skipping.")
            return True

        print(f"📥 Tier 1: Downloading/Processing archive...")
        # cloud_drive now handles auto-incrementing chapter logic internally
        success = cloud_drive.process_archive(self.title, "MASTER_BATCH", url, self.start_chapter)
        
        if success:
            self.manifest = file_io.load_json(self.metadata_path)
        return success

    def tier_2_ocr(self):
        """STATION 2: Turn Pixels to Text -> Saves to raw_ocr/"""
        chapters = self.manifest.get("chapter_map", {})
        all_sorted_ids = sorted(chapters.keys(), key=lambda x: int(x) if str(x).isdigit() else x)
        todo = [id for id in all_sorted_ids if not chapters[id].get("ocr_completed")]

        if not todo:
            print("⏩ Tier 2: OCR complete. Skipping.")
            return

        print(f"📖 Tier 2: Starting Batch OCR for {len(todo)} chapters...")
        for count, ch_id in enumerate(todo, 1):
            narrative_num = chapters[ch_id].get("target_chapter")
            local_img_dir = chapters[ch_id].get("local_dir")
            ocr_file_path = self.ocr_dir / f"chapter_{narrative_num}_raw_ocr.txt"
            
            # 🚀 UPDATED: Passing the direct directory path and narrative label to the engine
            raw_text, _ = ocr_engine.extract_text_from_chapter(local_img_dir, narrative_num)
            
            if raw_text:
                with open(ocr_file_path, "w", encoding="utf-8") as f:
                    f.write(raw_text)
                
                self.manifest["chapter_map"][ch_id]["ocr_completed"] = True
                file_io.save_json(self.manifest, self.metadata_path)

    def tier_3_ai(self):
        """STATION 3: Summarize -> Saves to summaries/"""
        chapters = self.manifest.get("chapter_map", {})
        all_sorted_ids = sorted(chapters.keys(), key=lambda x: int(x) if str(x).isdigit() else x)
        todo = [id for id in all_sorted_ids if chapters[id].get("ocr_completed") and not chapters[id].get("ai_completed")]

        if not todo:
            print("⏩ Tier 3: AI summaries complete. Skipping.")
            return

        print(f"🧠 Tier 3: Running AI Discovery for {len(todo)} chapters...")
        for count, ch_id in enumerate(todo, 1):
            narrative_num = chapters[ch_id].get("target_chapter")
            ocr_file_path = self.ocr_dir / f"chapter_{narrative_num}_raw_ocr.txt"
            summary_path = self.summary_dir / f"chapter_{narrative_num}_summary.json"

            if not ocr_file_path.exists():
                print(f"⚠️ Missing OCR for Chapter {narrative_num}. Skipping.")
                continue

            with open(ocr_file_path, "r", encoding="utf-8") as f:
                ocr_text = f.read()

            try:
                # 🚀 CALL THE AI WITH CIRCUIT BREAKER
                ai_results = ai_agent.generate_summary(ocr_text)
                if ai_results:
                    # Construct the comprehensive narrative object per your spec
                    full_summary_object = {
                        "title": self.title,
                        "chapter": narrative_num,
                        "summary": ai_results.get("summary"),
                        "key_moments": ai_results.get("key_moments"),
                        "characters_present": ai_results.get("characters_present")
                    }
                    
                    file_io.save_json(full_summary_object, summary_path)
                    self.manifest["chapter_map"][ch_id].update({
                        "ai_chapter_num": str(narrative_num),
                        "ai_completed": True
                    })
                    file_io.save_json(self.manifest, self.metadata_path)
                    print(f"✅ Chapter {narrative_num} -> Summary saved to {summary_path.name}")

            except ai_agent.RateLimitExhaustedError as e:
                # 🛑 FAIL FAST: Stop processing immediately if we hit the 429 spending cap
                print(f"\n🛑 Tier 3 Halted: {e}")
                print("Manifest saved. Pipeline suspended until quota resets.")
                return 

            # ⏱️ PACING: Always wait after a request to stay within 15 RPM
            time.sleep(8)

    def tier_4_cleanup(self):
        """STATION 4: Reclaim Disk Space."""
        chapters = self.manifest.get("chapter_map", {})
        total = len(chapters)
        completed = sum(1 for data in chapters.values() if data.get("ai_completed"))

        # Only delete images if the entire batch in the manifest is finished
        if total > 0 and completed == total:
            print(f"\n🧹 Tier 4: All {total} chapters processed. Cleaning up images...")
            if self.extract_dir.exists():
                shutil.rmtree(self.extract_dir)
                print(f"🗑️ Deleted image directory: {self.extract_dir}")
        else:
            print(f"\n⏳ Tier 4: Cleanup skipped ({completed}/{total} chapters finished).")

    def run_full_pipeline(self, url=None):
        print(f"\n🚀 BATCH PROCESSOR: {self.title}")
        print("-" * 40)
        
        if not self.tier_1_ingest(url): return
        self.tier_2_ocr()
        self.tier_3_ai()
        self.tier_4_cleanup()
        
        print("\n✨ ALL TIERS COMPLETE ✨")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--title", required=True)
    parser.add_argument("-u", "--url", help="GDrive URL for Ingest")
    parser.add_argument("-c", "--start-chapter", type=int, default=1, help="Starting chapter if manifest is new")
    args = parser.parse_args()

    processor = BatchProcessor(args.title, start_chapter=args.start_chapter)
    processor.run_full_pipeline(url=args.url)