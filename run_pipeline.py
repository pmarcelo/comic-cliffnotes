import argparse
import time
from datetime import datetime
from core import config, helpers
from core.usage_tracker import check_usage, log_success

# NATIVE IMPORTS - These only load into memory once!
from core import mangadex
from core import ocr_engine
from core import ai_agent

THROTTLE_TIME = 0

def run_chapter_pipeline(title: str, chapter_str: str, mode: str = "full", force: bool = False) -> bool:
    chapter_float = float(chapter_str)
    start_pipeline = time.perf_counter()
    paths = helpers.get_paths(title, chapter_str)

    print("\n" + "="*50)
    print(f"🚀 PIPELINE MODE: {mode.upper()} | {title} Ch {chapter_str}")
    print("="*50)

    # --- PHASE 1: EXTRACTION (MangaDex & OCR) ---
    if mode in ["full", "extract"]:
        if paths["summary"].exists() and not force:
            print(f"✅ Summary already exists. Skipping Extraction.")
        else:
            # 1. Fetch Metadata natively
            if not paths["metadata"].exists() or force:
                m_id, m_title = helpers.fetch_manga_id_and_title(title)
                if m_id:
                    metadata = mangadex.build_metadata(m_id, m_title, chapter_float)
                    if metadata.get("chapter_map"):
                        helpers.save_json(metadata, paths["metadata"])
                    else:
                        print(f"❌ Chapter {chapter_str} not found.")
                        return False
                else:
                    return False

            # 2. Run OCR natively
            if paths["metadata"].exists():
                if not paths["artifact"].exists() or force:
                    raw_text, metrics = ocr_engine.extract_text_from_chapter(str(paths["metadata"]), chapter_str)
                    
                    if raw_text:
                        meta = helpers.load_json(paths["metadata"])
                        artifact = {
                            "manga_title": meta["manga_title"],
                            "chapter_number": chapter_str,
                            "source_language": meta["chapter_map"][chapter_str]["lang"],
                            "raw_text": raw_text,
                            "metrics": metrics
                        }
                        helpers.save_json(artifact, paths["artifact"])
                        print(f"✅ Chapter {chapter_str} OCR complete. Time: {metrics['total_time']}s")
                    else:
                        print(f"❌ OCR Failed for Chapter {chapter_str}")
                        return False

    # --- PHASE 2: AI SUMMARIZATION ---
    if mode in ["full", "summarize"]:
        if not paths["artifact"].exists():
            print(f"❌ Cannot summarize: Artifact missing.")
            return False

        if paths["summary"].exists() and not force:
            print(f"✅ Summary already exists. Skipping AI phase.")
        else:
            if not check_usage():
                print("🚦 AI Daily Limit Reached! Skipping AI phase.")
                return False
            
            time.sleep(THROTTLE_TIME)
            
            # Run AI natively
            artifact = helpers.load_json(paths["artifact"])
            context, gap = ai_agent.get_nearest_context(paths, chapter_float)
            summary_content = ai_agent.generate_summary(artifact, context_memory=context, is_gap=gap)

            if summary_content:
                final_output = {
                    "schema_version": config.SCHEMA_VERSION,
                    "generated_at": datetime.now().isoformat(),
                    "model_used": config.TARGET_MODEL,
                    "source_artifact": str(paths["artifact"]),
                    "summary": summary_content
                }
                helpers.save_json(final_output, paths["summary"])
                ai_agent.update_manifest(title, helpers.get_safe_title(title), chapter_str, paths)
                log_success()
            else:
                return False

    print("\n" + "✨" + "-"*48 + "✨")
    print(f"📊 Total Wall Clock (Ch {chapter_str}): {time.perf_counter() - start_pipeline:.2f}s")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--title", type=str, required=True)
    parser.add_argument("-c", "--chapter", type=float, required=True)
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-m", "--mode", type=str, choices=["full", "extract", "summarize"], default="full")
    args = parser.parse_args()
    
    run_chapter_pipeline(args.title, str(args.chapter), args.mode, args.force)

if __name__ == "__main__":
    main()