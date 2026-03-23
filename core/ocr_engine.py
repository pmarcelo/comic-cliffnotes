import time
import argparse
import requests
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

from core import config, helpers

# --- OCR Engines ---
import pytesseract
try:
    from manga_ocr import MangaOcr
    mocr = MangaOcr() 
except ImportError:
    mocr = None

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

TESSERACT_MAP = {
    "en": "eng", "pt-br": "por", "pt": "por",
    "es-la": "spa", "es": "spa", "fr": "fra",
    "it": "ita", "deu": "deu", "ja": "jpn"
}

MAX_DOWNLOAD_WORKERS = 10  
MAX_OCR_WORKERS = 4        

def download_chapter_images(uuid: str, tmp_dir: str):
    logger.info(f"Routing MangaDex UUID: {uuid}")
    try:
        response = requests.get(f"{config.MANGADEX_API_URL}/at-home/server/{uuid}")
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error(f"MangaDex API error: {e}")
        return False
        
    base_url, chapter_hash = data['baseUrl'], data['chapter']['hash']
    filenames = data['chapter']['data']
    
    helpers.ensure_directory(tmp_dir)
    session = requests.Session()
    
    with ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS) as executor:
        tasks = []
        for filename in filenames:
            url = f"{base_url}/data/{chapter_hash}/{filename}"
            path = Path(tmp_dir) / filename
            tasks.append(executor.submit(helpers.download_image, session, url, path))
        
        for _ in tqdm(tasks, desc="⬇️ Downloading", unit="img"): pass
            
    return True

def ocr_worker(img_path, lang, installed_langs):
    tess_code = TESSERACT_MAP.get(lang, 'eng')
    actual_lang = tess_code if tess_code in installed_langs else 'eng'
    try:
        text = pytesseract.image_to_string(str(img_path), lang=actual_lang, config=r'--psm 6')
        return " ".join(text.split())
    except: return ""

def extract_text_from_chapter(metadata_path: str, target_chapter: str):
    start_total = time.perf_counter()
    
    meta = helpers.load_json(metadata_path)
    if not meta:
        logger.error("Metadata not found.")
        return None, {}
        
    chapter_data = meta["chapter_map"].get(str(target_chapter))
    if not chapter_data:
        logger.error(f"Chapter {target_chapter} not found in metadata.")
        return None, {}

    lang, uuid = chapter_data["lang"], chapter_data["uuid"]
    tmp_dir = Path(f"./tmp/{uuid}")
    installed_langs = helpers.get_tesseract_langs()
    
    # 1. Download
    start_dl = time.perf_counter()
    if not download_chapter_images(uuid, str(tmp_dir)): return None, {}
    dl_time = time.perf_counter() - start_dl

    # 2. OCR
    image_files = sorted([f for f in tmp_dir.iterdir() if f.is_file()])
    start_ocr = time.perf_counter()
    
    if lang == "ja" and mocr:
        extracted = [mocr(img) for img in tqdm(image_files, desc="📖 Manga-OCR")]
    else:
        with ThreadPoolExecutor(max_workers=MAX_OCR_WORKERS) as ex:
            results = list(tqdm(ex.map(lambda p: ocr_worker(p, lang, installed_langs), image_files), 
                                total=len(image_files), desc=f"📖 Tesseract ({lang})"))
            extracted = [r for r in results if r]

    ocr_time = time.perf_counter() - start_ocr
    helpers.cleanup_directory(tmp_dir) 
    
    metrics = {
        "download_time": round(dl_time, 2),
        "ocr_time": round(ocr_time, 2),
        "total_time": round(time.perf_counter() - start_total, 2),
        "pages": len(image_files)
    }
    return "\n\n".join(extracted), metrics

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--metadata", required=True)
    parser.add_argument("-c", "--chapter", required=True)
    args = parser.parse_args()

    raw_text, metrics = extract_text_from_chapter(args.metadata, args.chapter)
    
    if raw_text:
        meta = helpers.load_json(args.metadata)
        paths = helpers.get_paths(meta["manga_title"], args.chapter)
        
        artifact = {
            "manga_title": meta["manga_title"],
            "chapter_number": args.chapter,
            "source_language": meta["chapter_map"][args.chapter]["lang"],
            "raw_text": raw_text,
            "metrics": metrics
        }
        
        helpers.save_json(artifact, paths["artifact"])
        print(f"✅ Chapter {args.chapter} OCR complete. Total time: {metrics['total_time']}s")