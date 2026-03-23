import subprocess
import argparse
import os
import sys
import time

# --- CONFIGURATION ---
# Gemini 1.5 Flash allows 15 RPM. 
# A 5-second sleep ensures we never exceed ~12 RPM.
THROTTLE_TIME = 5 

def run_command(command):
    """Utility to run a terminal command and stream the output."""
    print(f"🛠️ Executing: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end="")
    process.wait()
    if process.returncode != 0:
        print(f"❌ Command failed with exit code {process.returncode}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Comic-CliffNotes Smart Pipeline")
    parser.add_argument("-t", "--title", type=str, required=True, help="Manga title")
    parser.add_argument("-c", "--chapter", type=float, required=True, help="Chapter number")
    parser.add_argument("-f", "--force", action="store_true", help="Force re-run even if files exist")
    
    args = parser.parse_args()
    chapter_str = str(args.chapter)
    
    safe_title = "".join([c for c in args.title if c.isalpha() or c.isspace()]).replace(" ", "_").lower()
    safe_alphanum = "".join([c for c in args.title if c.isalnum()]).lower()
    
    summary_file = f"./data/summaries/{safe_alphanum}_ch{chapter_str}_summary.json"
    artifact_file = f"./data/artifacts/{safe_alphanum}_ch{chapter_str}.json"
    metadata_file = f"./data/metadata/{safe_title}_metadata.json"

    print("\n" + "="*50)
    print(f"🚀 PIPELINE: {args.title} | Chapter {chapter_str}")
    print("="*50)

    # 1. Skip check
    if os.path.exists(summary_file) and not args.force:
        print(f"✅ Summary already exists. Skipping.")
        return

    # 2. Metadata
    if not os.path.exists(metadata_file) or args.force:
        run_command(["python", "core/mangadex.py", "-t", args.title, "-c", chapter_str])

    # 3. OCR
    if not os.path.exists(artifact_file) or args.force:
        run_command(["python", "core/ocr_engine.py", "-m", metadata_file, "-c", chapter_str])

    # 4. AI SUMMARIZATION (with Throttle)
    if os.path.exists(artifact_file):
        print(f"⏳ Cooling down for {THROTTLE_TIME}s (Free Tier Safety)...")
        time.sleep(THROTTLE_TIME)
        
        run_command(["python", "core/ai_agent.py", "-f", artifact_file])

    print("\n✨ PIPELINE COMPLETE ✨\n")

if __name__ == "__main__":
    main()