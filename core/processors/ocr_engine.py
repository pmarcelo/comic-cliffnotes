import easyocr
import re
import numpy as np
from PIL import Image, UnidentifiedImageError
from pathlib import Path
from core import config 

_reader = None

def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(['en'], gpu=config.USE_GPU)
    return _reader

def extract_text_from_images(image_dir: Path) -> str:
    """
    Takes a directory, filters out hidden files, and returns a single string of OCR text.
    """
    if not image_dir.exists():
        return ""

    # 1. Grab everything that is a file AND NOT a hidden/system file
    # This ignores .DS_Store, .nomedia, .thumbnails, etc.
    all_files = [
        f for f in image_dir.iterdir() 
        if f.is_file() and not f.name.startswith('.')
    ]
    
    # 2. Robust Sorting: Try to extract numbers for proper reading order
    def get_sort_key(path):
        nums = re.findall(r'\d+', path.stem)
        return int(nums[0]) if nums else path.name

    try:
        image_files = sorted(all_files, key=get_sort_key)
    except Exception:
        image_files = sorted(all_files)

    if not image_files:
        print(f" ⚠️ No valid image files found in {image_dir}")
        return ""


    reader = get_reader()
    full_text = []
    blacklist = [r"asurascans", r"discord", r"gg/", r"credits", r"scanlation"]

    for img_path in image_files:
        try:
            # Pillow is smart enough to detect format even without extensions
            with Image.open(img_path) as img:
                # Downsize for speed (Your LANCZOS logic)
                w, h = img.size
                img = img.resize((w // 2, h // 2), Image.Resampling.LANCZOS)
                img_np = np.array(img.convert("RGB"))
                
                results = reader.readtext(img_np, paragraph=True)
                
                page_blocks = []
                for (_, text) in results:
                    clean_line = text.strip()
                    if any(re.search(p, clean_line, re.IGNORECASE) for p in blacklist):
                        continue
                    page_blocks.append(clean_line)

                if page_blocks:
                    full_text.append(" ".join(page_blocks))
                    
        except (UnidentifiedImageError, PermissionError):
            # Skip files that aren't actually images or are locked
            continue
        except Exception as e:
            print(f"  ❌ Error on {img_path.name}: {e}")
            
    return "\n\n".join(full_text)