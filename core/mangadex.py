import os
import json
import requests
import time
import argparse

BASE_API_URL = "https://api.mangadex.org"
# The exact order of our fallback priority
LANGUAGE_PRIORITY = ["en", "es-la", "es", "pt-br", "pt", "fr", "ja", "ko"]

def search_manga_by_title(title: str):
    """Searches for a manga by title and returns its UUID."""
    print(f"🔍 Searching for manga: '{title}'...")
    response = requests.get(f"{BASE_API_URL}/manga", params={"title": title, "limit": 1})
    
    if response.status_code != 200 or not response.json().get("data"):
        print("❌ Manga not found. Check the spelling!")
        return None, None
        
    data = response.json()["data"][0]
    manga_id = data["id"]
    manga_title = list(data["attributes"]["title"].values())[0]
    
    print(f"✅ Found: {manga_title} (ID: {manga_id})")
    return manga_id, manga_title

def build_chapter_map(manga_id: str, manga_title: str, target_chapter: float):
    """Fetches chapters, applies the language waterfall, and builds the metadata map."""
    print(f"📚 Fetching feeds and applying language waterfall up to Chapter {target_chapter}...")
    
    all_chapters = []
    offset = 0
    limit = 500
    
    # 1. Paginate through the API to get all relevant chapters
    while True:
        params = {
            "translatedLanguage[]": LANGUAGE_PRIORITY,
            "order[chapter]": "asc",
            "limit": limit,
            "offset": offset
        }
        
        response = requests.get(f"{BASE_API_URL}/manga/{manga_id}/feed", params=params)
        if response.status_code != 200:
            print(f"❌ Failed to fetch chapter feed at offset {offset}.")
            break
            
        data = response.json().get("data", [])
        if not data:
            break
            
        all_chapters.extend(data)
        if len(data) < limit:
            break
            
        offset += limit
        time.sleep(0.3) # Be polite to the API

    # 2. Build the Waterfall Dictionary
    raw_map = {}
    
    for ch in all_chapters:
        ch_num_str = ch["attributes"]["chapter"]
        lang = ch["attributes"]["translatedLanguage"]
        
        if ch_num_str is None:
            continue
            
        try:
            ch_num = float(ch_num_str)
        except ValueError:
            continue
            
        if ch_num > target_chapter:
            continue
            
        # Format the chapter key nicely (e.g., "1.0", "1.5")
        ch_key = str(ch_num)
        
        # If we already have a chapter stored for this number, check if this new one is a better language
        if ch_key in raw_map:
            current_best_lang = raw_map[ch_key]["lang"]
            # Compare index in our priority list (lower index = higher priority)
            if LANGUAGE_PRIORITY.index(lang) < LANGUAGE_PRIORITY.index(current_best_lang):
                raw_map[ch_key] = {"lang": lang, "uuid": ch["id"]}
        else:
            raw_map[ch_key] = {"lang": lang, "uuid": ch["id"]}

    # 3. Check for missing chapters
    missing_chapters = []
    # Create a list of expected whole numbers (e.g., 1.0, 2.0, 3.0) up to the target
    for i in range(1, int(target_chapter) + 1):
        expected_key = f"{float(i)}"
        if expected_key not in raw_map:
            missing_chapters.append(float(i))

    # 4. Construct the final JSON structure
    metadata = {
        "manga_title": manga_title,
        "manga_id": manga_id,
        "target_chapter": target_chapter,
        "language_priority": LANGUAGE_PRIORITY,
        "chapter_map": dict(sorted(raw_map.items(), key=lambda item: float(item[0]))),
        "missing_chapters": missing_chapters
    }
    
    return metadata

def save_metadata(metadata: dict):
    """Saves the generated metadata map to a JSON file."""
    os.makedirs("./data/metadata", exist_ok=True) 
    
    # Create a safe filename (e.g., "tmp/omniscient_readers_viewpoint_metadata.json")
    safe_title = "".join([c for c in metadata["manga_title"] if c.isalpha() or c.isspace()]).replace(" ", "_").lower()
    file_path = f"./data/metadata/{safe_title}_metadata.json"
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        
    print(f"\n💾 Metadata successfully saved to: {file_path}")
    return file_path


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MangaDex Downloader & Metadata Generator")
    parser.add_argument("-t", "--title", type=str, required=True, help="Title of the manga")
    parser.add_argument("-c", "--chapter", type=float, required=True, help="Target chapter number")
    
    args = parser.parse_args()

    m_id, m_title = search_manga_by_title(args.title)
    
    if m_id:
        # Generate the mapped metadata
        metadata = build_chapter_map(m_id, m_title, args.chapter)
        
        # Save it to disk
        save_metadata(metadata)
        
        # Print a quick summary to the console
        found_count = len(metadata["chapter_map"])
        missing_count = len(metadata["missing_chapters"])
        print(f"📊 Summary: Found {found_count} chapters. Missing {missing_count} chapters.")