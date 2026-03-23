import os
import json
import shutil
import requests
import subprocess
import logging
import time
import pytesseract
from pathlib import Path
from core import config

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- STRING & PATH HELPERS ---
def get_safe_title(title: str) -> str:
    return "".join([c for c in title if c.isalpha() or c.isspace()]).replace(" ", "_").lower()

def get_paths(title: str, chapter: str):
    slug = get_safe_title(title)
    paths = {
        "metadata": config.METADATA_BASE / slug / f"ch{chapter}_metadata.json",
        "artifact": config.ARTIFACT_BASE / slug / f"ch{chapter}_artifact.json",
        "summary": config.SUMMARY_BASE / slug / f"ch{chapter}_summary.json",
        "manifest": config.SUMMARY_BASE / slug / "manifest.json",
        "title_dir": config.SUMMARY_BASE / slug
    }
    paths["metadata"].parent.mkdir(parents=True, exist_ok=True)
    paths["artifact"].parent.mkdir(parents=True, exist_ok=True)
    paths["summary"].parent.mkdir(parents=True, exist_ok=True)
    return paths

# --- IO HELPERS ---
def ensure_directory(path: str or Path):
    Path(path).mkdir(parents=True, exist_ok=True)

def cleanup_directory(path: str or Path):
    if os.path.exists(path):
        shutil.rmtree(path)

def load_json(path: str or Path):
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data: dict, path: str or Path):
    ensure_directory(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- EXECUTION HELPERS ---
def run_command(command: list) -> bool:
    """Utility to run a terminal command and stream output."""
    logger.info(f"🛠️ Executing: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end="")
    process.wait()
    return process.returncode == 0

# --- MANGADEX API HELPERS ---
def resolve_title(manga_data: dict) -> str:
    attrs = manga_data.get("attributes", {})
    titles = attrs.get("title", {})
    alt_titles = attrs.get("altTitles", [])

    if "en" in titles: return titles["en"]
    for alt in alt_titles:
        if "en" in alt: return alt["en"]
    return list(titles.values())[0] if titles else "Unknown Title"

def fetch_manga_id_and_title(title: str):
    """Consolidated logic to find a manga ID and resolve its official title."""
    params = {"title": title, "limit": 1}
    res = requests.get(f"{config.MANGADEX_API_URL}/manga", params=params)
    
    if res.status_code == 200 and res.json().get("data"):
        data = res.json()["data"][0]
        return data["id"], resolve_title(data)
    return None, None

def fetch_chapter_map(manga_id: str):
    """Fetches all chapters and resolves the best UUID based on language priority."""
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
        
        try:
            ch_num = float(ch_num_str)
        except ValueError: continue
            
        # Waterfall priority logic
        if ch_num in raw_map:
            current_best_lang = raw_map[ch_num]["lang"]
            if config.LANGUAGE_PRIORITY.index(lang) < config.LANGUAGE_PRIORITY.index(current_best_lang):
                raw_map[ch_num] = {"lang": lang, "uuid": ch["id"]}
        else:
            raw_map[ch_num] = {"lang": lang, "uuid": ch["id"]}

    return raw_map

# --- OCR HELPERS ---
def get_tesseract_langs():
    try: return pytesseract.get_languages(config='')
    except Exception: return []

def download_image(session, url, path, retries=3):
    for i in range(retries):
        try:
            res = session.get(url, timeout=15)
            if res.status_code == 200:
                with open(path, 'wb') as f: f.write(res.content)
                return True
        except Exception:
            if i == retries - 1: return False
    return False