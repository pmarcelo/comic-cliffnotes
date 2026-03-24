import argparse
import time
from datetime import datetime
from core import config
from core.utils import file_io

try:
    from core.usage_tracker import check_usage, log_success
except ImportError:
    def check_usage(): return True
    def log_success(): pass

# NEW NATIVE IMPORTS
from core.extractors import mangadex_api, cloud_drive
from core.processors import ocr_engine
from core.intelligence import ai_agent

def run_chapter_pipeline(title: str, chapter_str: str, mode: str = "full", force: bool = False, url: str = None) -> bool:
    chapter_float = float(chapter_str)
    start_pipeline = time.perf_counter()
    paths = file_io.get_paths(title, chapter_str)

    print("\n" + "="*50)
    print(f"🚀 PIPELINE MODE: {mode.upper()} | {title} Ch {chapter_str}")
    print("="*50)

    # --- PHASE 1: EXTRACTION ---
    if mode in ["full", "extract"]:
        if paths["summary"].exists() and not force:
            print(f"✅ Summary already exists. Skipping Extraction.")
        else:
            if not paths["metadata"].exists() or force:
                if url:
                    success = cloud_drive.process_archive(title, chapter_str, url)
                    if not success: return False
                else:
                    m_id, m_title = mangadex_api.fetch_manga_id_and_title(title)
                    if m_id:
                        metadata = mangadex_api.build_metadata(m_id, m_title, chapter_float)
                        if metadata.get("chapter_map"):
                            file_io.save_json(metadata, paths["metadata"])
                        else:
                            print(f"❌ Chapter {chapter_str} not found on MangaDex.")
                            return False
                    else:
                        print(f"❌ Manga '{title}' not found on MangaDex.")
                        return False

            if paths["metadata"].exists():
                if not paths["artifact"].exists() or force:
                    raw_text, metrics = ocr_engine.extract_text_from_chapter(str(paths["metadata"]), chapter_str)
                    
                    if raw_text:
                        meta = file_io.load_json(paths["metadata"])
                        artifact = {
                            "manga_title": meta["manga_title"],
                            "chapter_number": chapter_str,
                            "source_language": meta["chapter_map"][chapter_str]["lang"],
                            "raw_text": raw_text,
                            "metrics": metrics
                        }
                        file_io.save_json(artifact, paths["artifact"])
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
            
            artifact = file_io.load_json(paths["artifact"])
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
                file_io.save_json(final_output, paths["summary"])
                ai_agent.update_manifest(title, file_io.get_safe_title(title), chapter_str, paths)
                log_success()
            else:
                return False

    print("\n" + "✨" + "-"*48 + "✨")
    print(f"📊 Total Wall Clock (Ch {chapter_str}): {time.perf_counter() - start_pipeline:.2f}s")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--title", required=True)
    parser.add_argument("-c", "--chapter", required=True)
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-m", "--mode", choices=["full", "extract", "summarize"], default="full")
    parser.add_argument("-u", "--url", default=None, help="Direct link or Google Drive URL to a .zip archive")
    args = parser.parse_args()
    
    run_chapter_pipeline(args.title, str(args.chapter), args.mode, args.force, args.url)

if __name__ == "__main__":
    main()