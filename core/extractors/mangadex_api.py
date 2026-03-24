import requests
import sys
from core import config

def fetch_manga_id_and_title(title: str):
    """Searches MangaDex and handles multi-language titles."""
    params = {
        "title": title,
        "limit": 10,
        "contentRating[]": config.CONTENT_RATING
    }
    
    try:
        res = requests.get(f"{config.MANGADEX_API_URL}/manga", params=params)
        res.raise_for_status()
        data = res.json().get("data", [])
    except Exception as e:
        print(f"❌ API Error: {e}")
        return None, None
    
    if not data:
        print(f"❌ No results found for '{title}'.")
        return None, None

    if len(data) > 1:
        print(f"\n🔍 Found multiple matches for '{title}':")
        print("=" * 95)
        for i, entry in enumerate(data):
            attr = entry["attributes"]
            m_id = entry["id"]
            titles = attr.get("title", {})
            m_title = titles.get("en") or titles.get("ja-ro") or list(titles.values())[0]
            m_year = attr.get("year", "N/A")
            print(f"  [{i}] {m_title[:40]:<40} ({m_year}) | ID: ({m_id})")
        print("=" * 95)
        
        choice = input(f"👉 Select 0-{len(data)-1} (q to quit): ").strip().lower()
        if choice == 'q': sys.exit(0)
        selected = data[int(choice)]
    else:
        selected = data[0]

    final_titles = selected["attributes"]["title"]
    final_title = final_titles.get("en") or final_titles.get("ja-ro") or list(final_titles.values())[0]
    return selected["id"], final_title

def fetch_chapter_map(manga_id: str):
    """
    Fetches chapters using the global language priority list.
    If a chapter exists in multiple languages, it prefers the one higher in the list.
    """
    url = f"{config.MANGADEX_API_URL}/manga/{manga_id}/feed"
    params = {
        "translatedLanguage[]": config.LANGUAGE_PRIORITY,
        "limit": 500,
        "order[chapter]": "asc",
        "contentRating[]": config.CONTENT_RATING
    }
    
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        chapters = res.json().get("data", [])
    except Exception as e:
        print(f"❌ API Error: {e}")
        return {}

    print(f"DEBUG: Found {len(chapters)} chapters across prioritized languages.")
    
    chapter_map = {}
    for ch in chapters:
        attr = ch["attributes"]
        ch_num = attr.get("chapter")
        lang = attr["translatedLanguage"]
        
        if ch_num is not None:
            try:
                num_float = float(ch_num)
                
                # Logic: If we already have this chapter, only overwrite it if 
                # this new version is higher in our LANGUAGE_PRIORITY list.
                if num_float in chapter_map:
                    current_lang = chapter_map[num_float]["lang"]
                    if config.LANGUAGE_PRIORITY.index(lang) < config.LANGUAGE_PRIORITY.index(current_lang):
                        chapter_map[num_float] = {"uuid": ch["id"], "lang": lang, "title": attr.get("title")}
                else:
                    chapter_map[num_float] = {"uuid": ch["id"], "lang": lang, "title": attr.get("title")}
            except ValueError:
                continue

    if chapter_map:
        sorted_keys = sorted(chapter_map.keys())
        print(f"DEBUG: Global Chapter Range: {sorted_keys[0]} to {sorted_keys[-1]}")
    return chapter_map

def build_metadata(manga_id: str, title: str, target_chapter: float):
    ch_map = fetch_chapter_map(manga_id)
    return {
        "manga_id": manga_id,
        "manga_title": title,
        "target_chapter": target_chapter,
        "chapter_map": {str(k): v for k, v in ch_map.items()}
    }