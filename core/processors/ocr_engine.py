import easyocr
import re
import numpy as np
from PIL import Image
from pathlib import Path
from core import config 

# Initialize EasyOCR using the toggle from config.py
# GPU at home, CPU in the cloud/Mac.
print(f"🚀 OCR Engine Mode -> GPU: {config.USE_GPU}")
reader = easyocr.Reader(['en'], gpu=config.USE_GPU)

def extract_text_from_chapter(image_dir_path, chapter_label):
    """
    Pure worker: Takes a path to images and returns the extracted text.
    """
    image_dir = Path(image_dir_path)
    
    if not image_dir.exists():
        print(f"  ❌ Error: Directory not found -> {image_dir}")
        return None, None

    image_files = _collect_image_files(image_dir)
    
    if not image_files:
        return "", {"page_count": 0}

    raw_text = _process_images_to_text(image_files, chapter_label)
    return raw_text, {"page_count": len(image_files)}

def _collect_image_files(image_dir: Path):
    """Sorts numeric files correctly (1, 2, 10 instead of 1, 10, 2)."""
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    files = [
        f for f in image_dir.iterdir() 
        if f.is_file() and (f.suffix.lower() in valid_exts or f.name.isdigit())
    ]
    # Handle the numeric sorting so the story stays in order
    files.sort(key=lambda x: int(x.stem) if x.stem.isdigit() else x.name)
    return files

def _process_images_to_text(image_files, chapter_label):
    """
    Balanced Performance OCR:
    - Downscales images by 50% (Speed hack for CPU).
    - Paragraph Grouping (Better for AI summaries).
    - Noise scrubbing for Scanlator credits.
    """
    print(f"📖 OCR: Chapter {chapter_label} ({len(image_files)} pages)...")
    full_text = []
    
    # Junk patterns to ignore (Scanlator credits / Discord links)
    blacklist = [r"asurascans", r"asu[at]ascans", r"discord", r"gg/", r"killer", r"ace", r"qc"]

    for i, img_path in enumerate(image_files):
        try:
            with Image.open(img_path) as img:
                # --- STEP 1: DOWNSIZING ---
                # This makes a massive difference on your Mac/CPU runs.
                w, h = img.size
                img = img.resize((w // 2, h // 2), Image.Resampling.LANCZOS)
                
                img_np = np.array(img.convert("RGB"))
                
                # --- STEP 2: GROUPED OCR ---
                # merges speech bubbles into logical text blocks
                results = reader.readtext(img_np, paragraph=True)
                
                page_blocks = []
                for (_, text) in results:
                    clean_line = text.strip()
                    
                    # --- STEP 3: NOISE SCRUBBING ---
                    if any(re.search(p, clean_line, re.IGNORECASE) for p in blacklist):
                        continue
                    
                    # Ignore coordinate noise / pure numbers
                    if len(clean_line) > 12 and re.match(r'^[\d\s\(\)\-\+]+$', clean_line):
                        continue

                    page_blocks.append(clean_line)

                if page_blocks:
                    full_text.append(" ".join(page_blocks))
            
            # Progress feedback every 15 pages
            if (i + 1) % 15 == 0 or (i + 1) == len(image_files):
                print(f"    └─ Page {i+1}/{len(image_files)} complete")
                
        except Exception as e:
            print(f"  ❌ Error on Page {i} ({img_path.name}): {e}")
            
    return "\n\n".join(full_text)