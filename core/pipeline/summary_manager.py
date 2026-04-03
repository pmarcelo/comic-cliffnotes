import json
import time

from core.intelligence import ai_agent, local_agent
from database.models import Chapter, ChapterProcessing, Summary
from core.utils import usage_tracker


class SummaryManager:
    def __init__(self, db_session, series, title):
        self.db = db_session
        self.series = series
        self.title = title

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
            if t_str == "all":
                run_all = True
                break

            if "-" in t_str:
                # Handle ranges like '1-5'
                try:
                    start, end = map(int, t_str.split("-"))
                    if start <= end:
                        parsed_targets.update(range(start, end + 1))
                except ValueError:
                    print(f"⚠️ Warning: Ignored invalid range format '{t}'")
            elif t_str.isdigit():
                # Handle single numbers
                parsed_targets.add(int(t_str))

        # --- 2. Database Query ---
        if run_all:
            chapters_to_reset = (
                self.db.query(Chapter).filter(Chapter.series_id == self.series.id).all()
            )
            print(f"🔄 Preparing to reset ALL summaries for {self.title}...")
        else:
            targets_list = list(parsed_targets)
            if not targets_list:
                print("⚠️ No valid chapter targets provided for reset.")
                return

            chapters_to_reset = (
                self.db.query(Chapter)
                .filter(
                    Chapter.series_id == self.series.id,
                    Chapter.chapter_number.in_(targets_list),
                )
                .all()
            )

            targets_list.sort()
            print(f"🔄 Preparing to reset summaries for Chapters: {targets_list}...")

        if not chapters_to_reset:
            print("⚠️ No matching chapters found in the DB to reset.")
            return

        # --- 3. The Reset Execution ---
        reset_count = 0
        for ch in chapters_to_reset:
            existing_summary = (
                self.db.query(Summary).filter(Summary.chapter_id == ch.id).first()
            )
            if existing_summary:
                self.db.delete(existing_summary)

            proc = (
                self.db.query(ChapterProcessing)
                .filter(ChapterProcessing.chapter_id == ch.id)
                .first()
            )
            if proc:
                proc.summary_complete = False
                reset_count += 1

        self.db.commit()
        print(
            f"✅ Reset AI status for {reset_count} chapter(s). They are queued for Tier 3."
        )

    # ---> NEW: Added model_name parameter <---
    def generate_chapter_summaries(self, use_local_ai=False, model_name=None):
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
            
        # Fallback to default if not provided
        if not model_name:
            from core import config
            model_name = getattr(config, 'DEFAULT_MODEL', 'gemini-3.1-flash-lite-preview')

        print(f"🧠 Tier 3: Running AI Synthesis for {len(todo)} chapters...")
        for count, proc in enumerate(todo, 1):
            chapter = proc.chapter

            # Using the 1-to-1 relationship defined in models.py
            ocr_record = chapter.ocr_result
            ocr_text = ocr_record.raw_text if ocr_record else None

            # --- 1. Skip Empty OCR (Action-only chapters) ---
            if not ocr_text or len(ocr_text.strip()) < 10:
                print(
                    f"⚠️ Ch {chapter.chapter_number} has no meaningful OCR text. Marking as processed."
                )
                proc.summary_complete = True
                self.db.commit()
                continue

            try:
                if use_local_ai:
                    print(
                        f"🤖 Routing Ch {chapter.chapter_number} to Local LLM (Ollama)..."
                    )
                    ai_results = local_agent.generate_summary(ocr_text)
                else:
                    # ---> NEW: Print the specific model being used and pass it to the agent <---
                    print(
                        f"☁️ Routing Ch {chapter.chapter_number} to Cloud API ({model_name})..."
                    )
                    ai_results = ai_agent.generate_summary(ocr_text, model_name=model_name)

                if ai_results:
                    # Safely extract tokens (defaults to 0 if local_ai or missing)
                    tokens_used = ai_results.get("_usage_stats", {}).get("total_tokens", 0)
                    
                    # Log the run to our shared JSON file for the dashboard
                    usage_tracker.log_success(tokens_used=tokens_used, model_name=model_name)

                    # Strip the usage stats so they don't get saved to Postgres
                    clean_ai_results = {k: v for k, v in ai_results.items() if k != "_usage_stats"}

                    # --- 2. JSON Integrity Check ---
                    content_json_str = json.dumps(clean_ai_results, ensure_ascii=False)

                    new_summary = Summary(
                        chapter_id=chapter.id, content=content_json_str
                    )
                    self.db.add(new_summary)

                    # --- 3. Finalize DB State ---
                    proc.summary_complete = True
                    self.db.commit()
                    print(f"✅ Saved Summary for Chapter {chapter.chapter_number}")

            except Exception as e:
                # Break here because if the AI service is down/rate-limited, no point looping
                print(
                    f"\n🛑 FATAL: AI Service Failed on Ch {chapter.chapter_number}: {e}"
                )
                break

            # Rate limiting for Cloud APIs (skip on last item)
            if not use_local_ai and count < len(todo):
                print("⏳ Pacing Cloud API (10s)...")
                time.sleep(10)