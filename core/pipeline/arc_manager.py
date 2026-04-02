import json

from core.intelligence import arc_agent
from database.models import Chapter, StoryArc, Summary


class ArcManager:
    def __init__(self, db_session, series, title):
        self.db = db_session
        self.series = series
        self.title = title

    def generate_arc_summaries(self):
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
                all_metadata.append(
                    {
                        "chapter_number": ch.chapter_number,
                        "metadata": json.loads(ch.summary.content),
                    }
                )
            except Exception as e:
                print(f"⚠️ Skipping Ch {ch.chapter_number} due to invalid JSON: {e}")

        # 2. Stateful Batching Logic
        BATCH_SIZE = 100
        all_final_arcs = []
        ongoing_arc_state = None  # The "Baton" we pass between batches

        # Slice the list into chunks of 100
        chunks = [
            all_metadata[i : i + BATCH_SIZE]
            for i in range(0, len(all_metadata), BATCH_SIZE)
        ]

        print(f"📦 Grouped {len(all_metadata)} chapters into {len(chunks)} batch(es).")

        for index, chunk in enumerate(chunks, 1):
            print(f"🧠 Routing Batch {index}/{len(chunks)} to Arc Agent...")

            # Pass the chunk AND the baton
            arc_results = arc_agent.generate_arc_summaries(
                chunk, previous_ongoing_arc=ongoing_arc_state
            )

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
            ongoing_arc_state["status_quo_shift"] = (
                "Series is currently ongoing or arc boundary not yet reached."
            )
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
                    arc_summary=json.dumps(
                        {
                            "summary": arc_data.get("arc_summary", ""),
                            "core_cast": arc_data.get("core_cast", []),
                            "status_quo_shift": arc_data.get("status_quo_shift", ""),
                        },
                        ensure_ascii=False,
                    ),
                )
                self.db.add(new_arc)
                new_arcs_count += 1
            except Exception as e:
                print(f"⚠️ Failed to save an arc: {e}")

        self.db.commit()
        print(f"✅ Successfully synthesized and saved {new_arcs_count} Story Arcs.")
