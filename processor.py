import argparse
import sys
import os

from core.pipeline.arc_manager import ArcManager
from core.pipeline.ingest_manager import IngestManager
from core.pipeline.ocr_manager import OCRManager
from core.pipeline.summary_manager import SummaryManager
from database.models import Series
from database.session import SessionLocal
from core.utils import usage_tracker


class PipelineOrchestrator:
    def __init__(self, title, start_chapter=-1):
        self.title = title
        
        # Initialize DB Session
        self.db = SessionLocal()
        self.series = self._get_or_create_series()

        # Domain Managers
        self.ingest_manager = IngestManager(self.db, self.series, self.title, start_chapter)
        self.ocr_manager = OCRManager(self.db, self.series, self.title)
        self.summary_manager = SummaryManager(self.db, self.series, self.title)
        self.arc_manager = ArcManager(self.db, self.series, self.title)

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

    def run(self, 
            url=None, 
            run_extract=False, 
            run_ocr=False, 
            run_summarize=False, 
            use_local_ai=False, 
            reset_targets=None, 
            run_arcs=False, 
            model_name=None,
            ingest_method="auto",
            skip_input=""):
        
        print(f"\n🚀 PROCESSING: {self.title}")
        print(f"🛠️  Method: {ingest_method} | Model: {model_name}")
        if skip_input:
            print(f"⏭️  Skipping Chapters: {skip_input}")
        print("-" * 40)

        try:
            # --- MAINTENANCE: RESET SUMMARIES ---
            if reset_targets:
                # If the UI sends 'all' or a range, we clear the DB before running
                self.summary_manager.reset_summaries(reset_targets)
                # If we reset, we usually want to re-summarize immediately
                run_summarize = True

            # Logic gate: if no specific flags are passed, we assume a full run
            run_all = not (run_extract or run_ocr or run_summarize or run_arcs)

            # --- PHASE 1: EXTRACTION (Ingest) ---
            if run_extract or run_all:
                print("\n--- PHASE 1: EXTRACTION ---")
                success = self.ingest_manager.ingest(
                    gdrive_url=url, 
                    manual_method=ingest_method,
                    skip_input=skip_input
                )

                if not success:
                    print("❌ Ingestion failed. Aborting pipeline.")
                    return

            # --- PHASE 2: OCR ---
            if run_ocr or run_all:
                print("\n--- PHASE 2: OCR ---")
                self.ocr_manager.process_chapters()

            # --- PHASE 3: AI SUMMARY (Stateful) ---
            if run_summarize or run_all:
                print("\n--- PHASE 3: AI SUMMARY ---")
                
                if not use_local_ai and not usage_tracker.check_usage(model_name):
                    print("🛑 Aborting: Daily API limit reached.")
                    return
                
                # The SummaryManager now handles context-fetching and state-saving automatically
                self.summary_manager.generate_chapter_summaries(use_local_ai, model_name=model_name)
                
                # Cleanup: Deletes images once summaries are 100% finished
                self.ingest_manager.cleanup()

            # --- PHASE 4: ARC SYNTHESIS ---
            if run_arcs or run_all:
                print("\n--- PHASE 4: ARC SYNTHESIS ---")
                
                if not use_local_ai and not usage_tracker.check_usage(model_name):
                    print("🛑 Aborting: Daily API limit reached.")
                    return
                    
                self.arc_manager.generate_arc_summaries()

        finally:
            self.db.close()

        print("\n✨ PIPELINE COMPLETE ✨")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Comic Cliff-Notes Pipeline Processor")
    parser.add_argument("-t", "--title", required=True, help="Title of the series (Must match DB)")
    parser.add_argument("-u", "--url", help="Google Drive URL for ingestion")
    
    # Auto-Append logic: default to -1
    parser.add_argument("-c", "--start-chapter", type=int, default=-1, 
                        help="-1 to auto-append based on last DB entry, or specify a number to override.")
    
    parser.add_argument("-m", "--model", default="gemini-3.1-flash-lite-preview", help="Gemini model name")
    parser.add_argument("--skip", type=str, default="", help="Comma-separated chapters or ranges to skip")
    
    parser.add_argument(
        "--ingest-method", 
        default="auto", 
        choices=["auto", "google_drive", "web_gallery-dl"], 
        help="Method to acquire images. 'auto' checks DB for web source first."
    )

    # Granular Phase Flags
    parser.add_argument("-e", "--extract", action="store_true", help="Run Phase 1: Image Extraction only.")
    parser.add_argument("-o", "--ocr", action="store_true", help="Run Phase 2: OCR extraction only.")
    parser.add_argument("-s", "--summarize", action="store_true", help="Run Phase 3: AI Synthesis only.")
    parser.add_argument("--build-arcs", action="store_true", help="Run Phase 4: Arc Generation only.")
    
    parser.add_argument("--local-ai", action="store_true", help="Use Ollama instead of Cloud Gemini.")
    
    # 🎯 Reset Summaries (Matches the UI button call)
    parser.add_argument("--reset-summaries", nargs="+", help="Resets summaries for target chapters (e.g., 'all', '1-10').")

    args = parser.parse_args()

    orchestrator = PipelineOrchestrator(args.title, start_chapter=args.start_chapter)
    orchestrator.run(
        url=args.url,
        run_extract=args.extract,
        run_ocr=args.ocr,
        run_summarize=args.summarize,
        use_local_ai=args.local_ai,
        reset_targets=args.reset_summaries,
        run_arcs=args.build_arcs,
        model_name=args.model,
        ingest_method=args.ingest_method,
        skip_input=args.skip
    )