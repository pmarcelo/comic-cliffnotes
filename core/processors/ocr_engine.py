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
    Takes a directory, filters for valid images (ignoring .part and hidden files),
    and returns a single string of OCR text.
    """
    if not image_dir.exists():
        return ""

    # 1. 🛡️ Strict Filtering: Only grab finished images
    # This ignores .DS_Store AND incomplete .part files
    valid_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    
    image_files = [
        f for f in image_dir.iterdir() 
        if f.is_file() 
        and not f.name.startswith('.') 
        and f.suffix.lower() in valid_extensions
    ]
    
    if not image_files:
        print(f"No valid (finished) image files found in {image_dir}")
        return ""

    # 2. Robust Sorting
    def get_sort_key(path):
        nums = re.findall(r'\d+', path.stem)
        return int(nums[0]) if nums else path.name

    try:
        image_files = sorted(image_files, key=get_sort_key)
    except Exception:
        image_files = sorted(image_files)

    reader = get_reader()
    full_text = []
    # Added "weebcentral" to your blacklist just in case they have watermarks
    blacklist = [r"asurascans", r"discord", r"gg/", r"credits", r"scanlation", r"weebcentral"]

    for img_path in image_files:
        try:
            # 3. Process image with Pillow
            with Image.open(img_path) as img:
                # LANCZOS Downsize for speed/OCR efficiency
                w, h = img.size
                img = img.resize((w // 2, h // 2), Image.Resampling.LANCZOS)
                img_np = np.array(img.convert("RGB"))
                
                # Paragraph=True helps group dialogue bubbles together
                results = reader.readtext(img_np, paragraph=True)
                
                page_blocks = []
                for (_, text) in results:
                    clean_line = text.strip()
                    if any(re.search(p, clean_line, re.IGNORECASE) for p in blacklist):
                        continue
                    page_blocks.append(clean_line)

                if page_blocks:
                    # Join page text and add to the chapter list
                    full_text.append(" ".join(page_blocks))
                    
        except (UnidentifiedImageError, PermissionError) as e:
            # Skip corrupted or locked files
            print(f" Skipping unreadable file {img_path.name}")
            continue
        except Exception as e:
            print(f" Critical Error on {img_path.name}: {e}")
            
    return "\n\n".join(full_text)