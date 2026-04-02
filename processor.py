import argparse

from core.pipeline.arc_manager import ArcManager
from core.pipeline.ingest_manager import IngestManager
from core.pipeline.ocr_manager import OCRManager
from core.pipeline.summary_manager import SummaryManager
from database.models import Series
from database.session import SessionLocal


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

    def run(self, url=None, run_extract=False, run_summarize=False, use_local_ai=False, redo_targets=None, run_arcs=False):
        print(f"\n🚀 PROCESSING: {self.title}")
        print("-" * 40)

        try:
            if redo_targets:
                self.summary_manager.reset_summaries(redo_targets)
                run_summarize = True

            # Only run the base pipeline if run_arcs is NOT the only flag
            if not run_arcs or run_extract or run_summarize:
                run_all = not run_extract and not run_summarize and not run_arcs

                if run_extract or run_all:
                    print("\n--- PHASE 1: EXTRACTION & OCR ---")
                    if not self.ingest_manager.ingest(url):
                        return
                    self.ocr_manager.process_chapters()

                if run_summarize or run_all:
                    print("\n--- PHASE 2: AI SUMMARY ---")
                    self.summary_manager.generate_chapter_summaries(use_local_ai)
                    self.ingest_manager.cleanup()

            if run_arcs:
                print("\n--- PHASE 3: ARC SYNTHESIS ---")
                self.arc_manager.generate_arc_summaries()

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
    parser.add_argument("--redo-summaries", nargs="+", help="Reset summaries. Accepts numbers (1 2), ranges (1-5), mixes (1 3-5), or 'all'")

    args = parser.parse_args()

    orchestrator = PipelineOrchestrator(args.title, start_chapter=args.start_chapter)
    orchestrator.run(
        url=args.url,
        run_extract=args.extract,
        run_summarize=args.summarize,
        use_local_ai=args.local_ai,
        redo_targets=args.redo_summaries,
        run_arcs=args.build_arcs,
    )