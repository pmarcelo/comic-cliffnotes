import json
import time
import os
from sqlalchemy import select, desc

from core import config
from core.intelligence import ai_agent, local_agent
from database.models import Chapter, ChapterProcessing, Summary, SeriesMetadata
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

        for t in target_inputs:
            t_str = str(t).lower()
            if t_str == "all":
                run_all = True
                break

            if "-" in t_str:
                try:
                    start, end = map(int, t_str.split("-"))
                    if start <= end:
                        parsed_targets.update(range(start, end + 1))
                except ValueError:
                    print(f"⚠️ Warning: Ignored invalid range format '{t}'")
            elif t_str.isdigit():
                parsed_targets.add(int(t_str))

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
        print(f"✅ Reset AI status for {reset_count} chapter(s).")

    def _get_previous_context(self, current_chapter_num):
        """
        Looks back for the most relevant World State snapshot.
        Checks the immediate previous chapter first, then falls back to global metadata.
        """
        # 1. Try to find the snapshot from the closest previous chapter that has one
        prev_summary = (
            self.db.query(Summary)
            .join(Chapter)
            .filter(
                Chapter.series_id == self.series.id,
                Chapter.chapter_number < current_chapter_num
            )
            .order_by(desc(Chapter.chapter_number))
            .first()
        )

        if prev_summary and prev_summary.state_snapshot:
            return prev_summary.state_snapshot

        # 2. Fallback: Check global SeriesMetadata (useful for resumes or starting deep in a series)
        meta = self.db.query(SeriesMetadata).filter(SeriesMetadata.series_id == self.series.id).first()
        return meta.living_summary if meta else None

    def generate_chapter_summaries(self, use_local_ai=False, model_name=None):
        """Generates summaries using a stateful sliding window of snapshots."""
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
            return True
            
        if not model_name:
            model_name = getattr(config, 'DEFAULT_MODEL', 'gemini-3.1-flash-lite-preview')

        # Ensure the metadata record exists for the series
        meta_record = self.db.query(SeriesMetadata).filter(SeriesMetadata.series_id == self.series.id).first()
        if not meta_record:
            meta_record = SeriesMetadata(series_id=self.series.id)
            self.db.add(meta_record)
            self.db.flush()

        print(f"🧠 Tier 3: Running Stateful AI Synthesis for {len(todo)} chapters...")
        
        for count, proc in enumerate(todo, 1):
            chapter = proc.chapter
            ocr_record = chapter.ocr_result
            ocr_text = ocr_record.raw_text if ocr_record else None

            # Skip chapters with no meaningful dialogue
            if not ocr_text or len(ocr_text.strip()) < 10:
                print(f"⚠️ Ch {chapter.chapter_number} has no meaningful text. Skipping AI call.")
                proc.summary_complete = True
                self.db.commit()
                continue

            # 🎯 Step 1: Fetch Memory (Previous State)
            prev_snapshot = self._get_previous_context(chapter.chapter_number)

            try:
                if use_local_ai:
                    print(f"🤖 Routing Ch {chapter.chapter_number} to Local LLM...")
                    # Local agent would need to be updated to accept living_summary if used
                    ai_results = local_agent.generate_summary(ocr_text)
                else:
                    print(f"☁️ Summarizing Ch {chapter.chapter_number} with stateful context...")
                    ai_results = ai_agent.generate_summary(
                        ocr_text, 
                        living_summary=prev_snapshot, 
                        model_name=model_name
                    )

                if ai_results:
                    tokens_used = ai_results.get("_usage_stats", {}).get("total_tokens", 0)
                    usage_tracker.log_success(tokens_used=tokens_used, model_name=model_name)

                    # 🎯 Step 2: Separate the Chapter Summary from the New World State
                    new_snapshot = ai_results.get("updated_living_summary")
                    
                    # Remove non-content keys before saving to Chapter Summary
                    clean_results = {k: v for k, v in ai_results.items() if k not in ["_usage_stats", "updated_living_summary"]}

                    # 🎯 Step 3: Save versioned snapshot to the Summary table
                    new_summary = Summary(
                        chapter_id=chapter.id, 
                        content=json.dumps(clean_results, ensure_ascii=False),
                        state_snapshot=new_snapshot
                    )
                    self.db.add(new_summary)

                    # 🎯 Step 4: Update the Series-wide "Current Head" state
                    # We update this so the UI/Arc AI always sees the latest evolution
                    if new_snapshot:
                        meta_record.living_summary = new_snapshot

                    proc.summary_complete = True
                    self.db.commit()
                    print(f"✅ Saved Stateful Summary for Chapter {chapter.chapter_number}")

            except Exception as e:
                self.db.rollback()
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                    print(f"\n🚨 API QUOTA REACHED on Ch {chapter.chapter_number}! Halting.")
                    break
                else:
                    print(f"\n⚠️ Error on Ch {chapter.chapter_number}: {e}")
                    continue

            # --- API Pacing ---
            if not use_local_ai and count < len(todo):
                try:
                    max_rpm = int(getattr(config, 'GEMINI_MAX_RPM', os.getenv("GEMINI_MAX_RPM", 15)))
                except ValueError:
                    max_rpm = 15
                
                target_rpm = max(1, int(max_rpm * 0.8))
                sleep_time = round(60.0 / target_rpm, 2)
                
                print(f"⏳ Pacing {model_name} ({sleep_time}s pause)...")
                time.sleep(sleep_time)

        return True