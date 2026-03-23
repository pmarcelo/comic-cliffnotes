import os
import argparse
import requests
import subprocess
import time
from tqdm import tqdm  # Visual progress bar
from core import config 
from core.usage_tracker import check_usage

LANGUAGE_PRIORITY = ["en", "es-la", "es", "pt-br", "pt", "fr", "ja", "ko"]

def get_manga_id(title):
    """Fetches the MangaDex ID and official title."""
    url = "https://api.mangadex.org/manga"
    params = {"title": title, "limit": 1}
    r = requests.get(url, params=params)
    if r.status_code == 200 and r.json()["data"]:
        data = r.json()["data"][0]
        official_title = list(data["attributes"]["title"].values())[0]
        return data["id"], official_title
    return None, None

def get_chapter_list(manga_id, start, end):
    """Fetches unique chapter numbers available in priority languages."""
    url = f"https://api.mangadex.org/manga/{manga_id}/feed"
    params = {
        "translatedLanguage[]": LANGUAGE_PRIORITY,
        "order[chapter]": "asc",
        "limit": 500
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return []

    chapters = []
    for item in r.json()["data"]:
        try:
            num_str = item["attributes"]["chapter"]
            if num_str is None: continue
            num = float(num_str)
            if start <= num <= end:
                chapters.append(num)
        except (TypeError, ValueError):
            continue
            
    return sorted(list(set(chapters)))

def main():
    parser = argparse.ArgumentParser(description="Comic-CliffNotes Bulk Processor")
    parser.add_argument("-t", "--title", required=True, help="Manga title")
    parser.add_argument("-s", "--start", type=float, required=True, help="Start chapter")
    parser.add_argument("-e", "--end", type=float, required=True, help="End chapter")
    parser.add_argument("-m", "--mode", default="full", choices=["full", "extract", "summarize"])
    
    args = parser.parse_args()

    # 1. Resolve Manga Identity
    print(f"🔍 Locating '{args.title}' on MangaDex...")
    m_id, m_title = get_manga_id(args.title)
    
    if not m_id:
        print("❌ Could not find manga title.")
        return

    safe_title = config.get_safe_title(m_title)

    # 2. Get the "Queue"
    queue = get_chapter_list(m_id, args.start, args.end)
    
    if not queue:
        print(f"⚠️ No chapters found in range {args.start}-{args.end}.")
        return

    print(f"\n✅ Target: {m_title}")
    print(f"📋 Found {len(queue)} chapters to process.")
    print("="*50)

    # 3. Process the Queue with tqdm
    success_count = 0
    
    # Wrap the queue in tqdm for the visual bar
    # 'unit="ch"' adds a "ch/s" speed metric to the bar
    pbar = tqdm(queue, desc="🚀 Overall Progress", unit="ch")

    for chapter in pbar:
        # Update description to show the current active chapter
        pbar.set_description(f"📦 Processing Ch {chapter}")

        # Check AI Quota
        if args.mode in ["full", "summarize"] and not check_usage():
            pbar.write("\n🚦 Daily AI Limit Reached. Bulk run paused.")
            break

        # Run the pipeline
        cmd = [
            "python", "run_pipeline.py", 
            "-t", m_title, 
            "-c", str(chapter), 
            "-m", args.mode
        ]
        
        # We use subprocess.run with capture_output=True if you want a clean bar,
        # but here we keep it simple so you can still see the pipeline logs.
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            success_count += 1
        else:
            pbar.write(f"⚠️ Warning: Chapter {chapter} failed.")
        
        time.sleep(1)

    print("\n" + "="*50)
    print(f"🏁 BULK RUN COMPLETE")
    print(f"✅ Successfully processed: {success_count}/{len(queue)}")
    print("="*50)

if __name__ == "__main__":
    main()