import os
import time
from pathlib import Path
from PIL import Image
from manga_ocr import MangaOcr
from core import config
from core.utils import file_io

# Initialize the OCR Engine once
mocr = MangaOcr()

def extract_text_from_chapter(metadata_path: str, chapter_number: str):
    """
    Extracts text from images using MangaOCR.
    Handles both MangaDex (extensions) and Tachimanga/Tachidesk (naked files).
    """
    start_time = time.perf_counter()
    meta = file_io.load_json(metadata_path)
    
    # --- 1. SMART LOOKUP (Fixes the 'NoneType' error) ---
    # We look for a numerical match because "2" should find "2.0"
    chapter_data = None
    target_val = float(chapter_number)
    
    for key, data in meta["chapter_map"].items():
        try:
            if float(key) == target_val:
                chapter_data = data
                break
        except (ValueError, TypeError):
            continue

    if not chapter_data:
        print(f"❌ Error: Chapter {chapter_number} not found in metadata.")
        return None, None

    lang = chapter_data.get("lang", "en")
    
    # --- 2. LOCATE IMAGES ---
    # If it's a local import (Tachimanga), use the local_dir. Otherwise, check temp_dir.
    if "local_dir" in chapter_data:
        image_dir = Path(chapter_data["local_dir"])
    else:
        # MangaDex flow: images are usually in data/temp/<manga_id>/<chapter_id>
        image_dir = config.TEMP_DIR / meta["manga_id"] / chapter_data["uuid"]

    if not image_dir.exists():
        print(f"❌ Image directory not found: {image_dir}")
        return None, None

    # --- 3. GATHER FILES (Fixes the 'Naked File' issue) ---
    # We accept .jpg, .png, .webp OR files that are just digits (0, 1, 2...)
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    image_files = []
    
    for f in image_dir.iterdir():
        if f.is_file():
            if f.suffix.lower() in valid_exts or f.name.isdigit():
                image_files.append(f)

    # Sort files numerically (0, 1, 2...) instead of alphabetically (0, 1, 10, 11...)
    image_files.sort(key=lambda x: int(x.name) if x.name.isdigit() else x.name)

    if not image_files:
        print(f"⚠️ No images found in {image_dir}")
        return None, None

    # --- 4. OCR PROCESSING ---
    print(f"📖 Processing {len(image_files)} pages for Chapter {chapter_number}...")
    full_text = []
    
    for img_path in image_files:
        try:
            # MangaOCR handles the opening/loading
            text = mocr(str(img_path))
            if text.strip():
                full_text.append(text.strip())
        except Exception as e:
            print(f"⚠️ Failed to OCR page {img_path.name}: {e}")

    total_time = time.perf_counter() - start_time
    metrics = {
        "page_count": len(image_files),
        "total_time": round(total_time, 2),
        "seconds_per_page": round(total_time / len(image_files), 2) if image_files else 0
    }

    return "\n\n".join(full_text), metrics