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
    "it": "ita", "deu": "deu"
}

# Optimization Settings
MAX_DOWNLOAD_WORKERS = 10  
MAX_OCR_WORKERS = 4        

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
    """Downloads images and extracts text while measuring performance."""
    start_total = time.perf_counter()
    
    if not os.path.exists(metadata_path): return None, {}

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
        
    chapter_data = metadata["chapter_map"].get(str(target_chapter))
    if not chapter_data: return None, {}

    lang, uuid = chapter_data["lang"], chapter_data["uuid"]
    tmp_dir = f"./tmp/{uuid}"
    installed_langs = get_installed_tess_langs()
    
    # --- DOWNLOAD PHASE ---
    start_download = time.perf_counter()
    if not download_chapter_images(uuid, tmp_dir): return None, {}
    download_duration = time.perf_counter() - start_download

    # --- OCR PHASE ---
    print(f"📖 Scanning pages (Language: {lang})...")
    start_ocr = time.perf_counter()
    image_files = sorted([f for f in Path(tmp_dir).iterdir() if f.is_file()])
    extracted_text = []

    if lang == "ja" and mocr:
        for img in image_files:
            extracted_text.append(mocr(img))
    else:
        with ThreadPoolExecutor(max_workers=MAX_OCR_WORKERS) as executor:
            future_to_img = {executor.submit(ocr_worker, img, lang, installed_langs): img for img in image_files}
            for future in as_completed(future_to_img):
                text = future.result()
                if text: extracted_text.append(text)

    ocr_duration = time.perf_counter() - start_ocr
    full_text = " ".join(extracted_text)
    
    # Cleanup
    if os.path.exists(tmp_dir): shutil.rmtree(tmp_dir)
    
    total_duration = time.perf_counter() - start_total
    
    # Compile Performance Metrics
    metrics = {
        "download_time": round(download_duration, 2),
        "ocr_time": round(ocr_duration, 2),
        "total_extraction_time": round(total_duration, 2),
        "pages_processed": len(image_files)
    }
        
    return full_text, metrics

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--metadata", required=True)
    parser.add_argument("-c", "--chapter", required=True)
    args = parser.parse_args()

    # 1. Perform Extraction with Metrics
    raw_script, metrics = extract_text_from_chapter(args.metadata, args.chapter)
    
    if raw_script:
        with open(args.metadata, 'r') as f: meta = json.load(f)
        
        # 2. Build Structured Artifact with Metrics
        artifact = {
            "manga_title": meta["manga_title"],
            "chapter_number": args.chapter,
            "raw_text": raw_script,
            "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "performance_metrics": metrics
        }
        
        # 3. Save to Disk
        paths = config.get_paths(meta["manga_title"], args.chapter)
        with open(paths["artifact"], "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
            
        print("-" * 50)
        print(f"✅ Extraction Complete!")
        print(f"⏱️  Performance: DL {metrics['download_time']}s | OCR {metrics['ocr_time']}s | Total {metrics['total_extraction_time']}s")
        print(f"💾 Artifact: {paths['artifact']}")