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
    def __init__(self, title, start_chapter=1):
        self.title = title
        
        # Initialize DB Session
        self.db = SessionLocal()
        self.series = self._get_or_create_series()

        # 🧠 Domain Managers
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
            run_summarize=False, 
            use_local_ai=False, 
            redo_targets=None, 
            run_arcs=False, 
            model_name=None,
            ingest_method="auto",
            skip_input=""): # 🎯 NEW: Added skip_input parameter
        
        print(f"\n🚀 PROCESSING: {self.title}")
        print(f"🛠️  Method: {ingest_method} | Model: {model_name}")
        if skip_input:
            print(f"⏭️  Skipping Chapters: {skip_input}")
        print("-" * 40)

        try:
            if redo_targets:
                self.summary_manager.reset_summaries(redo_targets)
                run_summarize = True

            # Logic gate: if no specific flags are passed, we assume a full run
            run_all = not run_extract and not run_summarize and not run_arcs

            # --- PHASE 1: EXTRACTION & OCR ---
            if run_extract or run_all:
                print("\n--- PHASE 1: EXTRACTION & OCR ---")
                
                # 🎯 Smart Ingestion: Pass the skip argument
                success = self.ingest_manager.ingest(
                    gdrive_url=url, 
                    manual_method=ingest_method,
                    skip_input=skip_input
                )

                if not success:
                    print("❌ Ingestion failed. Aborting pipeline.")
                    return

                self.ocr_manager.process_chapters()

            # --- PHASE 2: AI SUMMARY ---
            if run_summarize or run_all:
                print("\n--- PHASE 2: AI SUMMARY ---")
                
                # Check daily request quota before calling LLM
                if not use_local_ai and not usage_tracker.check_usage(model_name):
                    print("🛑 Aborting: Daily API limit reached.")
                    return
                    
                self.summary_manager.generate_chapter_summaries(use_local_ai, model_name=model_name)
                
                # Clean up local image files only if summaries are fully finished
                self.ingest_manager.cleanup()

            # --- PHASE 3: ARC SYNTHESIS ---
            if run_arcs or run_all:
                print("\n--- PHASE 3: ARC SYNTHESIS ---")
                
                if not use_local_ai and not usage_tracker.check_usage(model_name):
                    print("🛑 Aborting: Daily API limit reached.")
                    return
                    
                self.arc_manager.generate_arc_summaries()

        finally:
            self.db.close()

        print("\n✨ PIPELINE COMPLETE ✨")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--title", required=True)
    parser.add_argument("-u", "--url", help="GDrive URL for Ingest")
    parser.add_argument("-c", "--start-chapter", type=int, default=1)
    parser.add_argument("-m", "--model", default="gemini-3.1-flash-lite-preview", help="Gemini model name")
    
    # 🎯 NEW: Add the skip argument to the parser
    parser.add_argument("--skip", type=str, default="", help="Comma-separated chapters to skip (for GDrive ingestion)")
    
    # Updated Ingest Method: Added "auto" as the default choice
    parser.add_argument(
        "--ingest-method", 
        default="auto", 
        choices=["auto", "google_drive", "web_gallery-dl"], 
        help="Method to acquire images. 'auto' checks DB for web source first."
    )

    parser.add_argument("--extract", action="store_true", help="Run Download and OCR only.")
    parser.add_argument("--summarize", action="store_true", help="Run AI and Cleanup only.")
    parser.add_argument("--build-arcs", action="store_true", help="Run Arc Synthesis only.")
    
    parser.add_argument("--local-ai", action="store_true", help="Use Ollama instead of Gemini.")
    parser.add_argument("--redo-summaries", nargs="+", help="Reset specific summaries.")

    args = parser.parse_args()

    orchestrator = PipelineOrchestrator(args.title, start_chapter=args.start_chapter)
    orchestrator.run(
        url=args.url,
        run_extract=args.extract,
        run_summarize=args.summarize,
        use_local_ai=args.local_ai,
        redo_targets=args.redo_summaries,
        run_arcs=args.build_arcs,
        model_name=args.model,
        ingest_method=args.ingest_method,
        skip_input=args.skip # 🎯 Pass it to the orchestrator here
    )