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
from core.intelligence import local_agent 

class BatchProcessor:
    def __init__(self, title, start_chapter=1):
        self.title = title
        self.slug = file_io.get_safe_title(title)
        self.manga_dir = config.ARTIFACTS_DIR / self.slug
        self.metadata_path = self.manga_dir / "metadata.json"
        self.extract_dir = config.DATA_DIR / "extracted_images" / self.slug
        self.manifest = self._load_or_create_manifest()
        self.start_chapter = start_chapter 

    def _load_or_create_manifest(self):
        if self.metadata_path.exists():
            return file_io.load_json(self.metadata_path)
        return {"manga_title": self.title, "chapter_map": {}}

    def tier_1_ingest(self, url):
        if not url and self.metadata_path.exists():
            print(f"⏩ Tier 1: Metadata exists and no new URL provided. Skipping.")
            return True

        print(f"📥 Tier 1: Downloading/Processing archive...")
        success = cloud_drive.process_archive(self.title, "MASTER_BATCH", url, self.start_chapter)
        if success:
            self.manifest = file_io.load_json(self.metadata_path)
        return success

    def tier_2_ocr(self):
        chapters = self.manifest.get("chapter_map", {})
        all_sorted_ids = sorted(chapters.keys(), key=lambda x: int(x) if str(x).isdigit() else x)
        todo = [id for id in all_sorted_ids if not chapters[id].get("ocr_completed")]

        if not todo:
            print("⏩ Tier 2: OCR complete. Skipping.")
            return

        print(f"📖 Tier 2: Starting Batch OCR for {len(todo)} chapters...")
        for count, ch_id in enumerate(todo, 1):
            print(f"[{count}/{len(todo)}] OCRing Folder: {ch_id}")
            # ⚠️ Ensure your easyocr.Reader is initialized INSIDE this function call!
            raw_text, metrics = ocr_engine.extract_text_from_chapter(str(self.metadata_path), ch_id)
            
            if raw_text:
                paths = file_io.get_paths(self.title, ch_id)
                with open(paths["raw_text"], "w", encoding="utf-8") as f:
                    f.write(raw_text)
                
                self.manifest["chapter_map"][ch_id]["ocr_completed"] = True
                file_io.save_json(self.manifest, self.metadata_path)

    def tier_3_ai(self, use_local_ai=False): 
        chapters = self.manifest.get("chapter_map", {})
        all_sorted_ids = sorted(chapters.keys(), key=lambda x: int(x) if str(x).isdigit() else x)
        todo = [id for id in all_sorted_ids if chapters[id].get("ocr_completed") and not chapters[id].get("ai_completed")]

        if not todo:
            print("⏩ Tier 3: AI summaries complete. Skipping.")
            return

        print(f"🧠 Tier 3: Running AI Discovery for {len(todo)} chapters...")
        for count, ch_id in enumerate(todo, 1):
            narrative_chapter = chapters[ch_id].get("target_chapter")
            paths = file_io.get_paths(self.title, ch_id)
            
            with open(paths["raw_text"], "r", encoding="utf-8") as f:
                ocr_text = f.read()

            try:
                if use_local_ai:
                    print(f"🤖 Routing Chapter {narrative_chapter} to Local LLM (Ollama)...")
                    ai_results = local_agent.generate_summary(ocr_text)
                else:
                    print(f"☁️ Routing Chapter {narrative_chapter} to Cloud API (Gemini)...")
                    ai_results = ai_agent.generate_summary(ocr_text)
            except Exception as e:
                print("\n🛑 FATAL: AI Service Failed or Quota Reached.")
                break 
            
            if ai_results:
                ai_results["identified_chapter_num"] = str(narrative_chapter)
                file_io.save_json(ai_results, paths["summary"])
                self.manifest["chapter_map"][ch_id].update({
                    "ai_chapter_num": str(narrative_chapter),
                    "ai_completed": True
                })
                file_io.save_json(self.manifest, self.metadata_path)
                print(f"✅ Folder {ch_id} -> Saved Summary for Chapter {narrative_chapter}")
                
            if not use_local_ai:
                print("⏳ Pacing Cloud API to avoid rate limits (waiting 10 seconds)...")
                time.sleep(10)

    def tier_4_cleanup(self):
        chapters = self.manifest.get("chapter_map", {})
        total = len(chapters)
        completed = sum(1 for data in chapters.values() if data.get("ai_completed"))

        if total > 0 and completed == total:
            print(f"\n🧹 Tier 4: All {total} chapters processed. Cleaning up images...")
            if self.extract_dir.exists():
                shutil.rmtree(self.extract_dir)
                print(f"🗑️ Deleted image directory: {self.extract_dir}")
        else:
            print(f"\n⏳ Tier 4: Cleanup skipped ({completed}/{total} chapters finished).")

    def run_full_pipeline(self, url=None, run_extract=False, run_summarize=False, use_local_ai=False):
        print(f"\n🚀 BATCH PROCESSOR: {self.title}")
        print("-" * 40)
        
        # If no explicit phase flags are passed, run everything.
        run_all = not run_extract and not run_summarize

        if run_extract or run_all:
            print("\n--- PHASE 1: EXTRACTION ---")
            if not self.tier_1_ingest(url): return
            self.tier_2_ocr()
            
        if run_summarize or run_all:
            print("\n--- PHASE 2: INTELLIGENCE ---")
            self.tier_3_ai(use_local_ai)
            self.tier_4_cleanup()
        
        print("\n✨ PIPELINE COMPLETE ✨")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--title", required=True)
    parser.add_argument("-u", "--url", help="GDrive URL for Ingest")
    parser.add_argument("-c", "--start-chapter", type=int, default=1)
    
    # The new, simplified task runners
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