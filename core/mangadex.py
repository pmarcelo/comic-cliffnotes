import json
import requests
import time
import argparse
from core import config  # Import central Single Source of Truth

BASE_API_URL = "https://api.mangadex.org"
# The order of fallback priority for the Waterfall logic
LANGUAGE_PRIORITY = ["en", "es-la", "es", "pt-br", "pt", "fr", "ja", "ko"]

def search_manga_by_title(title: str):
    """Searches for a manga by title and returns its UUID and official title."""
    print(f"🔍 Searching for manga: '{title}'...")
    response = requests.get(f"{BASE_API_URL}/manga", params={"title": title, "limit": 1})
    
    if response.status_code != 200 or not response.json().get("data"):
        print("❌ Manga not found. Check the spelling!")
        return None, None
        
    data = response.json()["data"][0]
    manga_id = data["id"]
    # Primary title from attributes
    manga_title = list(data["attributes"]["title"].values())[0]
    
    print(f"✅ Found: {manga_title} (ID: {manga_id})")
    return manga_id, manga_title

def build_chapter_map(manga_id: str, manga_title: str, target_chapter: float):
    """Fetches chapters, applies waterfall logic, and builds the metadata map."""
    print(f"📚 Fetching feeds and applying language waterfall for Chapter {target_chapter}...")
    
    all_chapters = []
    offset = 0
    limit = 500
    
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
        time.sleep(0.3)

    raw_map = {}
    
    for ch in all_chapters:
        ch_num_str = ch["attributes"]["chapter"]
        lang = ch["attributes"]["translatedLanguage"]
        
        if ch_num_str is None: continue
            
        try:
            ch_num = float(ch_num_str)
        except ValueError: continue
            
        # We only care about mapping the specific chapter we are targeting
        if ch_num != target_chapter: continue
            
        ch_key = str(ch_num)
        
        # Waterfall Logic
        if ch_key in raw_map:
            current_best_lang = raw_map[ch_key]["lang"]
            if LANGUAGE_PRIORITY.index(lang) < LANGUAGE_PRIORITY.index(current_best_lang):
                raw_map[ch_key] = {
                    "lang": lang, 
                    "uuid": ch["id"],
                    "pages": ch["attributes"]["data"],
                    "hash": ch["attributes"]["hash"]
                }
        else:
            raw_map[ch_key] = {
                "lang": lang, 
                "uuid": ch["id"],
                "pages": ch["attributes"]["data"],
                "hash": ch["attributes"]["hash"]
            }

    # Final metadata construction
    metadata = {
        "manga_title": manga_title,
        "manga_id": manga_id,
        "target_chapter": target_chapter,
        "language_priority": LANGUAGE_PRIORITY,
        "chapter_map": raw_map
    }
    
    return metadata

def save_metadata(metadata: dict, chapter_num: float):
    """Saves the metadata map using paths from centralized config."""
    # Get standardized paths from config
    paths = config.get_paths(metadata["manga_title"], str(chapter_num))
    file_path = paths["metadata"]
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Metadata successfully saved to: {file_path}")
    return file_path

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MangaDex Metadata Generator")
    parser.add_argument("-t", "--title", type=str, required=True, help="Title of the manga")
    parser.add_argument("-c", "--chapter", type=float, required=True, help="Target chapter number")
    
    args = parser.parse_args()

    m_id, m_title = search_manga_by_title(args.title)
    
    if m_id:
        # Generate the mapped metadata
        metadata = build_chapter_map(m_id, m_title, args.chapter)
        
        if not metadata["chapter_map"]:
            print(f"❌ Could not find Chapter {args.chapter} in any priority language.")
        else:
            # Save it to disk using the organized structure from config
            save_metadata(metadata, args.chapter)
            
            found_lang = metadata["chapter_map"][str(args.chapter)]["lang"]
            print(f"\n📊 SUMMARY FOR {m_title}:")
            print(f"   - Target Chapter: {args.chapter}")
            print(f"   - Mapped Language: {found_lang}")
            print(f"   - Workflow: Metadata ready for OCR.\n")