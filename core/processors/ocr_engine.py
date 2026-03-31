import easyocr
import re
import numpy as np
from PIL import Image
from pathlib import Path
from core.utils import file_io
from core import config  # <-- Pulls our smart hardware settings

# 🚀 FIX: Set to None initially. No memory is claimed on import!
_reader = None

def get_reader():
    """Lazy loader for EasyOCR to prevent VRAM hoarding."""
    global _reader
    if _reader is None:
        print(f"\n🚀 Booting OCR Engine Mode -> GPU: {config.USE_GPU}")
        _reader = easyocr.Reader(['en'], gpu=config.USE_GPU)
    return _reader

def extract_text_from_chapter(metadata_path, chapter_id):
    """Bridge to the main processor."""
    manifest = file_io.load_json(metadata_path)
    chapter_data = manifest.get("chapter_map", {}).get(str(chapter_id))
    
    if not chapter_data:
        return None, None

    image_dir = Path(chapter_data["local_dir"])
    image_files = _collect_image_files(image_dir)
    
    if not image_files:
        return "", {"page_count": 0}

    raw_text = _process_images_to_text(image_files, chapter_id)
    return raw_text, {"page_count": len(image_files)}

def _collect_image_files(image_dir: Path):
    """Sorts numeric files correctly (1, 2, 10 instead of 1, 10, 2)."""
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    files = [
        f for f in image_dir.iterdir() 
        if f.is_file() and (f.suffix.lower() in valid_exts or f.name.isdigit())
    ]
    files.sort(key=lambda x: int(x.name) if x.name.isdigit() else x.name)
    return files

def _process_images_to_text(image_files, chapter_id):
    """
    Balanced Performance OCR:
    - Downscales images by 50% for 3x faster processing on CPU.
    - Uses Paragraph Grouping for better AI summarization.
    - Cleans out scanlator noise via blacklist and regex.
    """
    print(f"📖 Balanced OCR: Processing {len(image_files)} pages for Ch {chapter_id}...")
    full_text = []
    
    # 🚀 FIX: Wake up the OCR engine ONLY when we actually start processing images
    reader = get_reader()
    
    # Junk patterns to ignore (Scanlator credits)
    blacklist = [r"asurascans", r"asu[at]ascans", r"discord", r"gg/", r"killer", r"ace", r"qc"]

    for i, img_path in enumerate(image_files):
        try:
            with Image.open(img_path) as img:
                # --- STEP 1: DOWNSIZING (The Speed Hack) ---
                # Reducing pixels by 75% dramatically speeds up CPU OCR.
                w, h = img.size
                img = img.resize((w // 2, h // 2), Image.Resampling.LANCZOS)
                
                # Convert to RGB and then Numpy for EasyOCR
                img_np = np.array(img.convert("RGB"))
                
                # --- STEP 2: GROUPED OCR ---
                # paragraph=True merges nearby speech bubbles into narrative blocks
                results = reader.readtext(img_np, paragraph=True)
                
                page_blocks = []
                for (_, text) in results:
                    clean_line = text.strip()
                    
                    # --- STEP 3: NOISE SCRUBBING ---
                    # Ignore scanlator credits
                    if any(re.search(p, clean_line, re.IGNORECASE) for p in blacklist):
                        continue
                    
                    # Ignore the long coordinate/page number noise
                    if len(clean_line) > 12 and re.match(r'^[\d\s\(\)\-\+]+$', clean_line):
                        continue

                    page_blocks.append(clean_line)

                if page_blocks:
                    full_text.append(" ".join(page_blocks))
            
            # Progress feedback
            if (i + 1) % 15 == 0 or (i + 1) == len(image_files):
                print(f"  ✅ Ch {chapter_id} | Page {i+1}/{len(image_files)} processed")
                
        except Exception as e:
            print(f"  ❌ Error on Page {i} ({img_path.name}): {e}")
            
    return "\n\n".join(full_text)