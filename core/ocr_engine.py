import os
import json
import shutil
import requests
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from core import config 

# --- OCR Engines ---
import pytesseract
try:
    from manga_ocr import MangaOcr
    mocr = MangaOcr() 
except ImportError:
    mocr = None

# --- Configuration ---
TESSERACT_MAP = {
    "en": "eng", "pt-br": "por", "pt": "por",
    "es-la": "spa", "es": "spa", "fr": "fra",
    "it": "ita", "de": "deu"
}

# Optimization Settings
MAX_DOWNLOAD_WORKERS = 10  # Parallel downloads
MAX_OCR_WORKERS = 4        # Parallel Tesseract processes (Match your CPU cores)

def get_installed_tess_langs():
    try:
        return pytesseract.get_languages(config='')
    except Exception:
        return []

def download_single_image(url, path):
    """Worker function for parallel downloads."""
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            with open(path, 'wb') as f:
                f.write(res.content)
            return True
    except Exception as e:
        print(f"⚠️ Download error: {e}")
    return False

def download_chapter_images(uuid: str, tmp_dir: str):
    """Downloads images using a ThreadPool for high speed."""
    print(f"📡 Routing UUID: {uuid}...")
    response = requests.get(f"https://api.mangadex.org/at-home/server/{uuid}")
    if response.status_code != 200: return False
        
    data = response.json()
    base_url, chapter_hash = data['baseUrl'], data['chapter']['hash']
    filenames = data['chapter']['data']
    os.makedirs(tmp_dir, exist_ok=True)

    print(f"⬇️ Downloading {len(filenames)} pages (Parallel)...")
    
    tasks = []
    with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS) as executor:
        for filename in filenames:
            img_url = f"{base_url}/data/{chapter_hash}/{filename}"
            img_path = os.path.join(tmp_dir, filename)
            tasks.append(executor.submit(download_single_image, img_url, img_path))
        
        # Wait for all to complete
        for _ in as_completed(tasks): pass
            
    return True

def ocr_worker(img_path, lang, installed_langs):
    """Worker function for parallel OCR (Tesseract only)."""
    try:
        if lang in TESSERACT_MAP:
            tess_code = TESSERACT_MAP[lang]
            actual_lang = tess_code if tess_code in installed_langs else 'eng'
            text = pytesseract.image_to_string(str(img_path), lang=actual_lang)
            return " ".join(text.split())
    except Exception:
        pass
    return ""

def extract_text_from_chapter(metadata_path: str, target_chapter: str):
    if not os.path.exists(metadata_path): return None

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
        
    chapter_data = metadata["chapter_map"].get(str(target_chapter))
    if not chapter_data: return None

    lang, uuid = chapter_data["lang"], chapter_data["uuid"]
    tmp_dir = f"./tmp/{uuid}"
    installed_langs = get_installed_tess_langs()
    
    if not download_chapter_images(uuid, tmp_dir): return None

    print(f"📖 Scanning pages (Language: {lang})...")
    image_files = sorted([f for f in Path(tmp_dir).iterdir() if f.is_file()])
    extracted_text = []

    # --- PERFORMANCE BRANCHING ---
    if lang == "ja" and mocr:
        # Manga-OCR is a heavy AI model; we process it sequentially 
        # to avoid crashing memory, but it's very fast on its own.
        for img in image_files:
            extracted_text.append(mocr(img))
    else:
        # Tesseract is lightweight; run it in parallel!
        with ThreadPoolExecutor(max_workers=MAX_OCR_WORKERS) as executor:
            future_to_img = {executor.submit(ocr_worker, img, lang, installed_langs): img for img in image_files}
            for future in as_completed(future_to_img):
                text = future.result()
                if text: extracted_text.append(text)

    full_text = " ".join(extracted_text)
    if os.path.exists(tmp_dir): shutil.rmtree(tmp_dir)
        
    return full_text

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--metadata", required=True)
    parser.add_argument("-c", "--chapter", required=True)
    args = parser.parse_args()

    raw_script = extract_text_from_chapter(args.metadata, args.chapter)
    
    if raw_script:
        with open(args.metadata, 'r') as f: meta = json.load(f)
        artifact = {
            "manga_title": meta["manga_title"],
            "chapter_number": args.chapter,
            "raw_text": raw_script,
            "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        paths = config.get_paths(meta["manga_title"], args.chapter)
        with open(paths["artifact"], "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
            
        print(f"✅ Extraction Complete! (Artifact: {paths['artifact']})")