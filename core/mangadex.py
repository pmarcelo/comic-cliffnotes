import json
import requests
import time
import argparse
from core import config 

BASE_API_URL = "https://api.mangadex.org"
LANGUAGE_PRIORITY = ["en", "es-la", "es", "pt-br", "pt", "fr", "ja", "ko"]

def search_manga_by_title(title: str):
    """Searches for a manga by title and returns its UUID and official title."""
    print(f"🔍 Searching for manga: '{title}'...")
    response = requests.get(f"{BASE_API_URL}/manga", params={"title": title, "limit": 1})
    
    if response.status_code != 200 or not response.json().get("data"):
        print("❌ Manga not found.")
        return None, None
        
    data = response.json()["data"][0]
    manga_id = data["id"]
    manga_title = list(data["attributes"]["title"].values())[0]
    
    print(f"✅ Found: {manga_title} (ID: {manga_id})")
    return manga_id, manga_title

def build_chapter_map(manga_id: str, manga_title: str, target_chapter: float):
    """Fetches chapters and applies waterfall logic based on available Feed data."""
    print(f"📚 Fetching feeds for Chapter {target_chapter}...")
    
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
            break
            
        data = response.json().get("data", [])
        if not data: break
        all_chapters.extend(data)
        if len(data) < limit: break
        offset += limit
        time.sleep(0.2)

    raw_map = {}
    for ch in all_chapters:
        ch_num_str = ch["attributes"]["chapter"]
        lang = ch["attributes"]["translatedLanguage"]
        
        if ch_num_str is None: continue
        try:
            ch_num = float(ch_num_str)
        except ValueError: continue
            
        if ch_num != target_chapter: continue
            
        ch_key = str(ch_num)
        
        # Waterfall Logic: Store only the UUID and Lang
        # ocr_engine.py will use the UUID to find the actual images later
        if ch_key in raw_map:
            current_best_lang = raw_map[ch_key]["lang"]
            if LANGUAGE_PRIORITY.index(lang) < LANGUAGE_PRIORITY.index(current_best_lang):
                raw_map[ch_key] = {
                    "lang": lang, 
                    "uuid": ch["id"]
                }
        else:
            raw_map[ch_key] = {
                "lang": lang, 
                "uuid": ch["id"]
            }

    return {
        "manga_title": manga_title,
        "manga_id": manga_id,
        "target_chapter": target_chapter,
        "chapter_map": raw_map
    }

def save_metadata(metadata: dict, chapter_num: float):
    paths = config.get_paths(metadata["manga_title"], str(chapter_num))
    file_path = paths["metadata"]
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Metadata successfully saved to: {file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--title", required=True)
    parser.add_argument("-c", "--chapter", type=float, required=True)
    args = parser.parse_args()

    m_id, m_title = search_manga_by_title(args.title)
    if m_id:
        metadata = build_chapter_map(m_id, m_title, args.chapter)
        if metadata["chapter_map"]:
            save_metadata(metadata, args.chapter)
        else:
            print(f"❌ Chapter {args.chapter} not found.")