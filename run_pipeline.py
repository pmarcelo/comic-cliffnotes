import subprocess
import argparse
import time
from core import config  # Central Single Source of Truth
from core.usage_tracker import check_usage, log_success

# --- CONFIGURATION ---
THROTTLE_TIME = 5 

def run_command(command):
    """Utility to run a terminal command and stream output."""
    print(f"🛠️ Executing: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end="")
    process.wait()
    return process.returncode == 0

def main():
    parser = argparse.ArgumentParser(description="Comic-CliffNotes Orchestrator")
    parser.add_argument("-t", "--title", type=str, required=True, help="Manga title")
    parser.add_argument("-c", "--chapter", type=float, required=True, help="Chapter number")
    parser.add_argument("-f", "--force", action="store_true", help="Force re-run")
    parser.add_argument("-m", "--mode", type=str, choices=["full", "extract", "summarize"], 
                        default="full", help="Pipeline mode")
    
    args = parser.parse_args()
    chapter_str = str(args.chapter)
    
    # --- GET CENTRALIZED PATHS ---
    # We let config.py handle all the slugging and directory creation logic
    paths = config.get_paths(args.title, chapter_str)
    
    metadata_file = paths["metadata"]
    artifact_file = paths["artifact"]
    summary_file = paths["summary"]

    print("\n" + "="*50)
    print(f"🚀 PIPELINE MODE: {args.mode.upper()} | {args.title} Ch {chapter_str}")
    print(f"📂 Data Root: {config.DATA_DIR}/.../{config.get_safe_title(args.title)}/")
    print("="*50)

    # --- PHASE 1: EXTRACTION (Metadata + OCR) ---
    if args.mode in ["full", "extract"]:
        # Skip check: If the final summary exists, we usually don't need to re-extract
        if summary_file.exists() and not args.force:
            print(f"✅ Summary already exists. Skipping Extraction.")
        else:
            # 1. Metadata Fetching
            if not metadata_file.exists() or args.force:
                run_command(["python", "core/mangadex.py", "-t", args.title, "-c", chapter_str])
            
            # 2. OCR Ingestion
            if metadata_file.exists():
                if not artifact_file.exists() or args.force:
                    # Pass the path as a string to the subprocess
                    run_command(["python", "core/ocr_engine.py", "-m", str(metadata_file), "-c", chapter_str])
            else:
                print(f"❌ Aborting OCR: Metadata file missing at {metadata_file}")

    # --- PHASE 2: SUMMARIZATION (AI) ---
    if args.mode in ["full", "summarize"]:
        # 1. Check for artifact
        if not artifact_file.exists():
            print(f"❌ Cannot summarize: Artifact missing at {artifact_file}")
            return

        # 2. Check if already summarized
        if summary_file.exists() and not args.force:
            print(f"✅ Summary already exists. Skipping AI phase.")
            return

        # 3. Check AI Quota (Wallet Protection)
        if not check_usage():
            print("🚦 AI Daily Limit Reached! Artifact is saved, but skipping AI.")
            print("💡 Finish this later with: --mode summarize")
            return

        # 4. Execute AI Agent
        print(f"⏳ Cooling down for {THROTTLE_TIME}s (Free Tier Safety)...")
        time.sleep(THROTTLE_TIME)
        
        # We pass the artifact path string to the AI agent
        if run_command(["python", "core/ai_agent.py", "-f", str(artifact_file)]):
            log_success() 

    print("\n✨ PIPELINE STEP COMPLETE ✨\n")

if __name__ == "__main__":
    main()