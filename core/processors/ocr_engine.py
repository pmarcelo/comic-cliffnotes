import time
import requests
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from core import config
from core.utils import file_io, network

import pytesseract
try:
    from manga_ocr import MangaOcr
    mocr = MangaOcr() 
except ImportError:
    mocr = None

logger = logging.getLogger(__name__)

TESSERACT_MAP = {"en": "eng", "pt-br": "por", "pt": "por", "es-la": "spa", "es": "spa", "fr": "fra", "it": "ita", "deu": "deu", "ja": "jpn"}

def download_chapter_images(uuid: str, tmp_dir: str):
    logger.info(f"Routing MangaDex UUID: {uuid}")
    try:
        response = requests.get(f"{config.MANGADEX_API_URL}/at-home/server/{uuid}")
        response.raise_for_status()
        data = response.json()
    except Exception as e: return False
        
    base_url, chapter_hash = data['baseUrl'], data['chapter']['hash']
    filenames = data['chapter']['data']
    
    file_io.ensure_directory(tmp_dir)
    session = requests.Session()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = [executor.submit(network.download_image, session, f"{base_url}/data/{chapter_hash}/{f}", Path(tmp_dir) / f) for f in filenames]
        for _ in tqdm(tasks, desc="⬇️ Downloading from MangaDex", unit="img"): pass
    return True

def extract_text_from_chapter(metadata_path: str, target_chapter: str):
    start_total = time.perf_counter()
    meta = file_io.load_json(metadata_path)
    if not meta: return None, {}
        
    chapter_data = meta["chapter_map"].get(str(target_chapter))
    lang = chapter_data["lang"]
    
    start_dl = time.perf_counter()
    if "local_dir" in chapter_data:
        image_dir = Path(chapter_data["local_dir"])
    else:
        uuid = chapter_data["uuid"]
        image_dir = Path(f"./tmp/{uuid}")
        if not download_chapter_images(uuid, str(image_dir)): return None, {}
        
    dl_time = time.perf_counter() - start_dl
    image_files = sorted([
        f for f in image_dir.iterdir() 
        if f.is_file() and (f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'} or f.name.isdigit())
    ], key=lambda x: int(x.name) if x.name.isdigit() else x.name)
    
    start_ocr = time.perf_counter()
    
    installed_langs = []
    try: installed_langs = pytesseract.get_languages(config='')
    except Exception: pass

    def ocr_worker(img_path):
        actual_lang = TESSERACT_MAP.get(lang, 'eng') if TESSERACT_MAP.get(lang, 'eng') in installed_langs else 'eng'
        try: return " ".join(pytesseract.image_to_string(str(img_path), lang=actual_lang, config=r'--psm 6').split())
        except: return ""

    if lang == "ja" and mocr:
        extracted = [mocr(img) for img in tqdm(image_files, desc="📖 Manga-OCR")]
    else:
        with ThreadPoolExecutor(max_workers=4) as ex:
            extracted = [r for r in list(tqdm(ex.map(ocr_worker, image_files), total=len(image_files), desc=f"📖 Tesseract ({lang})")) if r]

    ocr_time = time.perf_counter() - start_ocr
    if "local_dir" not in chapter_data: file_io.cleanup_directory(image_dir) 
    
    metrics = {"download_time": round(dl_time, 2), "ocr_time": round(ocr_time, 2), "total_time": round(time.perf_counter() - start_total, 2), "pages": len(image_files)}
    return "\n\n".join(extracted), metrics