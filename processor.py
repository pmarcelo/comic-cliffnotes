import os
import argparse
import shutil
from pathlib import Path
from core import config
from core.utils import file_io
from core.extractors import cloud_drive
from core.processors import ocr_engine
from core.intelligence import ai_agent

class BatchProcessor:
    def __init__(self, title):
        self.title = title
        self.slug = file_io.get_safe_title(title)
        self.manga_dir = config.ARTIFACTS_DIR / self.slug
        self.metadata_path = self.manga_dir / "metadata.json"
        self.extract_dir = config.DATA_DIR / "extracted_images" / self.slug
        self.manifest = self._load_or_create_manifest()

    def _load_or_create_manifest(self):
        if self.metadata_path.exists():
            return file_io.load_json(self.metadata_path)
        return {"manga_title": self.title, "chapter_map": {}}

    def tier_1_ingest(self, url):
        """STATION 1: Ingest logic (Now smarter about existing files)."""
        if self.metadata_path.exists():
            print(f"⏩ Tier 1: Metadata exists. Skipping.")
            return True

        # Just call it. The new logic in cloud_drive.py will handle the 'Skip'
        success = cloud_drive.process_archive(self.title, "MASTER_BATCH", url)
        
        if success:
            # Reload the manifest once the scan is finished
            self.manifest = file_io.load_json(self.metadata_path)
            
        return success
        
        if self.extract_dir.exists() and any(self.extract_dir.iterdir()):
            print(f"📍 Tier 1: Detected existing extracted images. Generating metadata map...")
            # If images exist but metadata doesn't, just run the scan logic
            success = cloud_drive.process_archive(self.title, "MASTER_BATCH", url)
            if success:
                self.manifest = file_io.load_json(self.metadata_path)
            return success

        print(f"📥 Tier 1: Downloading master archive...")
        success = cloud_drive.process_archive(self.title, "MASTER_BATCH", url)
        if success:
            self.manifest = file_io.load_json(self.metadata_path)
        return success

    def tier_2_ocr(self):
        """STATION 2: Turn Pixels to Text."""
        chapters = self.manifest.get("chapter_map", {})
        todo = [id for id, data in chapters.items() if not data.get("ocr_completed")]

        if not todo:
            print("⏩ Tier 2: OCR complete. Skipping.")
            return

        print(f"📖 Tier 2: Starting Batch OCR for {len(todo)} chapters...")
        for count, ch_id in enumerate(todo, 1):
            print(f"[{count}/{len(todo)}] OCRing Folder: {ch_id}")
            raw_text, metrics = ocr_engine.extract_text_from_chapter(str(self.metadata_path), ch_id)
            
            if raw_text:
                paths = file_io.get_paths(self.title, ch_id)
                with open(paths["raw_text"], "w", encoding="utf-8") as f:
                    f.write(raw_text)
                
                self.manifest["chapter_map"][ch_id]["ocr_completed"] = True
                file_io.save_json(self.manifest, self.metadata_path)

    def tier_3_ai(self):
        """STATION 3: Summarize and Map Identity."""
        chapters = self.manifest.get("chapter_map", {})
        todo = [id for id, data in chapters.items() if data.get("ocr_completed") and not data.get("ai_completed")]

        if not todo:
            print("⏩ Tier 3: AI summaries complete. Skipping.")
            return

        print(f"🧠 Tier 3: Running AI Discovery for {len(todo)} chapters...")
        for count, ch_id in enumerate(todo, 1):
            paths = file_io.get_paths(self.title, ch_id)
            with open(paths["raw_text"], "r", encoding="utf-8") as f:
                ocr_text = f.read()

            ai_results = ai_agent.generate_summary(ocr_text)
            if ai_results:
                file_io.save_json(ai_results, paths["summary"])
                self.manifest["chapter_map"][ch_id].update({
                    "ai_chapter_num": ai_results.get("identified_chapter_num"),
                    "ai_title": ai_results.get("identified_title"),
                    "ai_completed": True
                })
                file_io.save_json(self.manifest, self.metadata_path)
                print(f"✅ Folder {ch_id} -> Chapter {ai_results.get('identified_chapter_num')}")

    def tier_4_cleanup(self):
        """STATION 4: Reclaim Disk Space."""
        chapters = self.manifest.get("chapter_map", {})
        total = len(chapters)
        completed = sum(1 for data in chapters.values() if data.get("ai_completed"))

        # Safety Check: Only delete if EVERY chapter in the manifest is finished
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
    args = parser.parse_args()

    processor = BatchProcessor(args.title)
    processor.run_full_pipeline(url=args.url)