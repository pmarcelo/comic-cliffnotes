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
    # Get the primary title (usually the first one in the dictionary)
    manga_title = list(data["attributes"]["title"].values())[0]
    
    print(f"✅ Found: {manga_title} (ID: {manga_id})")
    return manga_id, manga_title

def build_chapter_map(manga_id: str, manga_title: str, target_chapter: float):
    """Fetches chapters, applies the language waterfall, and builds the metadata map."""
    print(f"📚 Fetching feeds and applying language waterfall up to Chapter {target_chapter}...")
    
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
        
        if ch_num_str is None:
            continue
            
        try:
            ch_num = float(ch_num_str)
        except ValueError:
            continue
            
        if ch_num > target_chapter:
            continue
            
        ch_key = str(ch_num)
        
        # Waterfall Logic: Only replace if the new language has a higher priority (lower index)
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

    missing_chapters = []
    for i in range(1, int(target_chapter) + 1):
        expected_key = f"{float(i)}"
        if expected_key not in raw_map:
            missing_chapters.append(float(i))

    metadata = {
        "manga_title": manga_title,
        "manga_id": manga_id,
        "target_chapter": target_chapter,
        "language_priority": LANGUAGE_PRIORITY,
        "chapter_map": dict(sorted(raw_map.items(), key=lambda item: float(item[0]))),
        "missing_chapters": missing_chapters
    }
    
    return metadata

def save_metadata(metadata: dict, chapter_num: float):
    """Saves the metadata map to a title-specific subfolder."""
    # 1. Standardized Safe Title Slug
    raw_title = metadata["manga_title"]
    safe_title = "".join([c for c in raw_title if c.isalpha() or c.isspace()]).replace(" ", "_").lower()
    
    # 2. Create the directory: data/metadata/[series_title]/
    output_dir = os.path.join("./data/metadata", safe_title)
    os.makedirs(output_dir, exist_ok=True) 
    
    # 3. Create the chapter-specific filename
    file_path = os.path.join(output_dir, f"ch{chapter_num}_metadata.json")
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Metadata successfully saved to: {file_path}")
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
        
        # Save it to disk in the organized structure
        save_metadata(metadata, args.chapter)
        
        # Final Summary Print
        found_count = len(metadata["chapter_map"])
        missing_count = len(metadata["missing_chapters"])
        print(f"\n📊 SUMMARY FOR {m_title}:")
        print(f"   - Found Chapters: {found_count}")
        print(f"   - Missing Chapters: {missing_count}")
        print(f"   - Workflow: Ready for OCR/Summarization.\n")