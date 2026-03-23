import argparse
import time
from core import config, helpers
from core.usage_tracker import check_usage, log_success

THROTTLE_TIME = 5 

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--title", type=str, required=True)
    parser.add_argument("-c", "--chapter", type=float, required=True)
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-m", "--mode", type=str, choices=["full", "extract", "summarize"], default="full")
    args = parser.parse_args()
    
    chapter_str = str(args.chapter)
    start_pipeline = time.perf_counter()
    paths = helpers.get_paths(args.title, chapter_str)
    
    print("\n" + "="*50)
    print(f"🚀 PIPELINE MODE: {args.mode.upper()} | {args.title} Ch {chapter_str}")
    print("="*50)

    # --- PHASE 1 ---
    phase_1_start = time.perf_counter()
    if args.mode in ["full", "extract"]:
        if paths["summary"].exists() and not args.force:
            print(f"✅ Summary already exists. Skipping Extraction.")
        else:
            if not paths["metadata"].exists() or args.force:
                helpers.run_command(["python", "-m", "core.mangadex", "-t", args.title, "-c", chapter_str])
            
            if paths["metadata"].exists():
                if not paths["artifact"].exists() or args.force:
                    helpers.run_command(["python", "-m", "core.ocr_engine", "-m", str(paths["metadata"]), "-c", chapter_str])
    phase_1_duration = time.perf_counter() - phase_1_start

    # --- PHASE 2 ---
    phase_2_start = time.perf_counter()
    if args.mode in ["full", "summarize"]:
        if not paths["artifact"].exists():
            print(f"❌ Cannot summarize: Artifact missing.")
            return

        if paths["summary"].exists() and not args.force:
            print(f"✅ Summary already exists. Skipping AI phase.")
        else:
            if not check_usage():
                print("🚦 AI Daily Limit Reached! Skipping AI phase.")
            else:
                time.sleep(THROTTLE_TIME)
                if helpers.run_command(["python", "-m", "core.ai_agent", "-f", str(paths["artifact"])]):
                    log_success() 
    phase_2_duration = time.perf_counter() - phase_2_start

    print("\n" + "✨" + "-"*48 + "✨")
    print(f"📊 Total Wall Clock: {time.perf_counter() - start_pipeline:.2f}s")

if __name__ == "__main__":
    main()