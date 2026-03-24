import time
import requests
import logging
from core import config
from core.utils import file_io

logger = logging.getLogger(__name__)

def resolve_title(manga_data: dict) -> str:
    attrs = manga_data.get("attributes", {})
    titles = attrs.get("title", {})
    alt_titles = attrs.get("altTitles", [])
    if "en" in titles: return titles["en"]
    for alt in alt_titles:
        if "en" in alt: return alt["en"]
    return list(titles.values())[0] if titles else "Unknown Title"

def fetch_manga_id_and_title(title: str):
    params = {"title": title, "limit": 1}
    res = requests.get(f"{config.MANGADEX_API_URL}/manga", params=params)
    if res.status_code == 200 and res.json().get("data"):
        data = res.json()["data"][0]
        return data["id"], resolve_title(data)
    return None, None

def fetch_chapter_map(manga_id: str):
    all_chapters = []
    offset = 0
    limit = 500
    while True:
        params = {
            "translatedLanguage[]": config.LANGUAGE_PRIORITY,
            "order[chapter]": "asc",
            "limit": limit,
            "offset": offset
        }
        res = requests.get(f"{config.MANGADEX_API_URL}/manga/{manga_id}/feed", params=params)
        if res.status_code != 200: break
        data = res.json().get("data", [])
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
        try: ch_num = float(ch_num_str)
        except ValueError: continue
        
        if ch_num in raw_map:
            current_best_lang = raw_map[ch_num]["lang"]
            if config.LANGUAGE_PRIORITY.index(lang) < config.LANGUAGE_PRIORITY.index(current_best_lang):
                raw_map[ch_num] = {"lang": lang, "uuid": ch["id"]}
        else:
            raw_map[ch_num] = {"lang": lang, "uuid": ch["id"]}
    return raw_map

def build_metadata(manga_id: str, title: str, target_chapter: float):
    print(f"📚 Fetching feeds for Chapter {target_chapter}...")
    full_map = fetch_chapter_map(manga_id)
    if target_chapter not in full_map: return {}
    return {
        "manga_title": title,
        "manga_id": manga_id,
        "target_chapter": target_chapter,
        "chapter_map": {str(target_chapter): full_map[target_chapter]}
    }