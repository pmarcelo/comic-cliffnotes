import subprocess
import argparse
import os
import sys
import time
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
    parser = argparse.ArgumentParser(description="Comic-CliffNotes Multi-Mode Pipeline")
    parser.add_argument("-t", "--title", type=str, required=True, help="Manga title")
    parser.add_argument("-c", "--chapter", type=float, required=True, help="Chapter number")
    parser.add_argument("-f", "--force", action="store_true", help="Force re-run even if files exist")
    parser.add_argument("-m", "--mode", type=str, choices=["full", "extract", "summarize"], 
                        default="full", help="Pipeline mode: full, extract, or summarize")
    
    args = parser.parse_args()
    chapter_str = str(args.chapter)
    
    # --- NEW STANDARDIZED SLUGGING LOGIC ---
    # Ensures folder names match core/mangadex.py, core/ocr_engine.py, and core/ai_agent.py
    safe_title = "".join([c for c in args.title if c.isalpha() or c.isspace()]).replace(" ", "_").lower()
    
    # Define the 3-Tier path structure
    metadata_file = f"./data/metadata/{safe_title}/ch{chapter_str}_metadata.json"
    artifact_file = f"./data/artifacts/{safe_title}/ch{chapter_str}_artifact.json"
    summary_file = f"./data/summaries/{safe_title}/ch{chapter_str}_summary.json"

    print("\n" + "="*50)
    print(f"🚀 PIPELINE MODE: {args.mode.upper()} | {args.title} Ch {chapter_str}")
    print(f"📂 Project Root: ./data/.../{safe_title}/")
    print("="*50)

    # --- PHASE 1: EXTRACTION (Metadata + OCR) ---
    if args.mode in ["full", "extract"]:
        # Skip check: If the final summary exists, we usually don't need to re-extract
        if os.path.exists(summary_file) and not args.force:
            print(f"✅ Summary already exists. Skipping Extraction.")
        else:
            # 1. Metadata Fetching
            if not os.path.exists(metadata_file) or args.force:
                run_command(["python", "core/mangadex.py", "-t", args.title, "-c", chapter_str])
            
            # 2. OCR Ingestion
            # We only run OCR if the metadata was successfully created/found
            if os.path.exists(metadata_file):
                if not os.path.exists(artifact_file) or args.force:
                    run_command(["python", "core/ocr_engine.py", "-m", metadata_file, "-c", chapter_str])
            else:
                print(f"❌ Aborting OCR: Metadata file missing at {metadata_file}")

    # --- PHASE 2: SUMMARIZATION (AI) ---
    if args.mode in ["full", "summarize"]:
        # 1. Check for artifact
        if not os.path.exists(artifact_file):
            print(f"❌ Cannot summarize: Artifact missing at {artifact_file}")
            return

        # 2. Check if already summarized
        if os.path.exists(summary_file) and not args.force:
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
        
        if run_command(["python", "core/ai_agent.py", "-f", artifact_file]):
            log_success() # Increment our daily usage tracker

    print("\n✨ PIPELINE STEP COMPLETE ✨\n")

if __name__ == "__main__":
    main()