import os
import argparse
import requests
import subprocess
import time
from core import config  # Central Single Source of Truth
from core.usage_tracker import check_usage

# We keep this here as it is MangaDex specific, 
# but we ensure it matches the priority in mangadex.py
LANGUAGE_PRIORITY = ["en", "es-la", "es", "pt-br", "pt", "fr", "ja", "ko"]

def get_manga_id(title):
    """Fetches the MangaDex ID and official title for a given search query."""
    url = "https://api.mangadex.org/manga"
    params = {"title": title, "limit": 1}
    r = requests.get(url, params=params)
    if r.status_code == 200 and r.json()["data"]:
        data = r.json()["data"][0]
        official_title = list(data["attributes"]["title"].values())[0]
        return data["id"], official_title
    return None, None

def get_chapter_list(manga_id, start, end):
    """Fetches and filters unique chapter numbers available in priority languages."""
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
            
    # Remove duplicates (MangaDex returns one entry per scanlation group/language)
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

    # Use central config to get the standardized safe title (slug)
    safe_title = config.get_safe_title(m_title)

    # 2. Get the "Queue"
    queue = get_chapter_list(m_id, args.start, args.end)
    
    if not queue:
        print(f"⚠️ No chapters found in the range {args.start} - {args.end} within priority languages.")
        return

    print(f"\n✅ Target: {m_title}")
    print(f"📂 Storage: {config.DATA_DIR}/.../{safe_title}/")
    print(f"📋 Found {len(queue)} chapters to process: {queue}")
    print("="*50)

    # 3. Process the Queue
    success_count = 0
    for chapter in queue:
        # Check AI Quota before launching a full/summarize chapter task
        if args.mode in ["full", "summarize"] and not check_usage():
            print("\n🚦 Daily AI Limit Reached. Bulk run paused.")
            print(f"💡 Chapters remaining: {len(queue) - success_count}")
            break

        print(f"\n📦 [BULK] STARTING CHAPTER {chapter}")
        
        # Call the orchestrator using the official title to maintain folder consistency
        cmd = [
            "python", "run_pipeline.py", 
            "-t", m_title, 
            "-c", str(chapter), 
            "-m", args.mode
        ]
        
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            success_count += 1
        
        # Politeness delay for API and AI Rate Limits
        time.sleep(2)

    print("\n" + "="*50)
    print(f"🏁 BULK RUN COMPLETE")
    print(f"✅ Successfully processed: {success_count}/{len(queue)}")
    print(f"📂 Data saved to subfolders under: {safe_title}")
    print("="*50)

if __name__ == "__main__":
    main()