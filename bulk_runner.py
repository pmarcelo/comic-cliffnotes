import os
import argparse
import requests
import subprocess
import time
from core.usage_tracker import check_usage

# Match the priority from mangadex.py so the bulk runner "sees" everything the pipeline can handle
LANGUAGE_PRIORITY = ["en", "es-la", "es", "pt-br", "pt", "fr", "ja", "ko"]

def get_manga_id(title):
    """Fetches the MangaDex ID for a given title."""
    url = "https://api.mangadex.org/manga"
    params = {"title": title, "limit": 1}
    r = requests.get(url, params=params)
    if r.status_code == 200 and r.json()["data"]:
        data = r.json()["data"][0]
        return data["id"], list(data["attributes"]["title"].values())[0]
    return None, None

def get_chapter_list(manga_id, start, end):
    """Fetches and filters unique chapter numbers available in any priority language."""
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
            
    # Remove duplicates (MangaDex returns one entry per group/language)
    return sorted(list(set(chapters)))

def main():
    parser = argparse.ArgumentParser(description="Comic-CliffNotes Bulk Processor")
    parser.add_argument("-t", "--title", required=True, help="Manga title")
    parser.add_argument("-s", "--start", type=float, required=True, help="Start chapter")
    parser.add_argument("-e", "--end", type=float, required=True, help="End chapter")
    parser.add_argument("-m", "--mode", default="full", choices=["full", "extract", "summarize"])
    
    args = parser.parse_args()

    # 1. Get Manga Identity
    print(f"🔍 Locating '{args.title}' on MangaDex...")
    m_id, m_title = get_manga_id(args.title)
    if not m_id:
        print("❌ Could not find manga title.")
        return

    # Create the safe slug to show the user where data is going
    safe_title = "".join([c for c in m_title if c.isalpha() or c.isspace()]).replace(" ", "_").lower()

    # 2. Get the "Queue"
    queue = get_chapter_list(m_id, args.start, args.end)
    
    if not queue:
        print(f"⚠️ No chapters found in the range {args.start} - {args.end} within priority languages.")
        return

    print(f"\n✅ Target: {m_title}")
    print(f"📂 Folder: ./data/.../{safe_title}/")
    print(f"📋 Found {len(queue)} chapters: {queue}")
    print("="*50)

    # 3. Process the Queue
    success_count = 0
    for chapter in queue:
        # Final safety check for AI quota (Free Tier protection)
        if args.mode in ["full", "summarize"] and not check_usage():
            print("\n🚦 Daily AI Limit Reached. Bulk run paused.")
            print(f"💡 Chapters remaining in queue: {len(queue) - success_count}")
            break

        print(f"\n📦 [BULK] STARTING CHAPTER {chapter}")
        
        # Call the orchestrator
        # chapter is passed as string to handle floats correctly (e.g., '1.0')
        cmd = ["python", "run_pipeline.py", "-t", m_title, "-c", str(chapter), "-m", args.mode]
        
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            success_count += 1
        
        # Small delay to keep the MangaDex API and Google RPM happy
        time.sleep(2)

    print("\n" + "="*50)
    print(f"🏁 BULK RUN COMPLETE")
    print(f"✅ Successfully processed: {success_count}/{len(queue)}")
    print(f"📂 Results saved in: ./data/.../{safe_title}/")
    print("="*50)

if __name__ == "__main__":
    main()