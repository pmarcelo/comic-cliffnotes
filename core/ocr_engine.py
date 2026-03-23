import os
import json
import shutil
import requests
import time
import argparse
from pathlib import Path

# --- OCR Engines ---
import pytesseract
try:
    from manga_ocr import MangaOcr
    # Initialize the Japanese AI model (loads into memory)
    mocr = MangaOcr() 
except ImportError:
    mocr = None
    print("⚠️ manga-ocr not installed. Japanese extraction will be skipped.")

# --- Configuration ---
# Maps MangaDex language codes to Tesseract's 3-letter codes
TESSERACT_MAP = {
    "en": "eng",
    "pt-br": "por",
    "pt": "por",
    "es-la": "spa",
    "es": "spa",
    "fr": "fra",
    "it": "ita",
    "de": "deu"
}

def get_installed_tess_langs():
    """Checks the system to see what Tesseract packs are actually installed."""
    try:
        return pytesseract.get_languages(config='')
    except Exception as e:
        print(f"⚠️ Could not verify installed Tesseract languages: {e}")
        return []

def download_chapter_images(uuid: str, tmp_dir: str):
    """Downloads images from MangaDex At-Home server."""
    print(f"📡 Requesting image routing for UUID: {uuid}...")
    
    response = requests.get(f"https://api.mangadex.org/at-home/server/{uuid}")
    if response.status_code != 200:
        print("❌ Failed to get routing data from MangaDex.")
        return False
        
    data = response.json()
    base_url = data['baseUrl']
    chapter_hash = data['chapter']['hash']
    filenames = data['chapter']['data']

    os.makedirs(tmp_dir, exist_ok=True)
    print(f"⬇️ Downloading {len(filenames)} pages to {tmp_dir}...")
    
    for filename in filenames:
        img_url = f"{base_url}/data/{chapter_hash}/{filename}"
        img_path = os.path.join(tmp_dir, filename)
        
        try:
            img_res = requests.get(img_url)
            with open(img_path, 'wb') as f:
                f.write(img_res.content)
            time.sleep(0.3) 
        except Exception as e:
            print(f"⚠️ Failed to download {filename}: {e}")
            
    return True

def extract_text_from_chapter(metadata_path: str, target_chapter: str):
    """The main pipeline: Download -> Dynamic OCR Routing -> Cleanup -> Return Text."""
    
    if not os.path.exists(metadata_path):
        print(f"❌ Metadata file not found: {metadata_path}")
        return None

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
        
    # The new metadata structure stores the target chapter info at the top level
    # We double-check the chapter matches for safety
    if str(metadata.get("target_chapter")) != str(target_chapter):
        print(f"⚠️ Warning: Metadata target ({metadata.get('target_chapter')}) mismatch with args ({target_chapter}).")

    # In our new ch-specific metadata, we use the specific chapter info
    chapter_key = str(target_chapter)
    chapter_data = metadata["chapter_map"].get(chapter_key)
    
    if not chapter_data:
        print(f"❌ Chapter {target_chapter} not found in the provided metadata map.")
        return None

    lang = chapter_data["lang"]
    uuid = chapter_data["uuid"]
    tmp_dir = f"./tmp/{uuid}"
    installed_langs = get_installed_tess_langs()
    
    print(f"\n🚀 Starting Extraction Pipeline for Chapter {target_chapter}")
    print(f"🌍 Detected Language: {lang}")
    
    # 2. Download Images
    if not download_chapter_images(uuid, tmp_dir):
        return None

    # 3. OCR Processing
    print(f"📖 Scanning pages...")
    image_files = sorted([f for f in Path(tmp_dir).iterdir() if f.is_file()])
    extracted_text = []
    
    for img_path in image_files:
        text = ""
        try:
            if lang == "ja" and mocr:
                text = mocr(img_path)
            elif lang in TESSERACT_MAP:
                tess_code = TESSERACT_MAP[lang]
                if tess_code in installed_langs:
                    text = pytesseract.image_to_string(str(img_path), lang=tess_code)
                else:
                    text = pytesseract.image_to_string(str(img_path), lang='eng')
            else:
                text = pytesseract.image_to_string(str(img_path), lang='eng')

            if text.strip():
                clean_text = " ".join(text.split())
                extracted_text.append(clean_text)
                
        except Exception as e:
            print(f"⚠️ OCR failed on {img_path.name}: {e}")

    full_text = " ".join(extracted_text)
    
    # 4. Cleanup
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
        print(f"🗑️ Deleted temporary images from {tmp_dir}")
        
    return full_text

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCR Extractor for Comic-CliffNotes")
    parser.add_argument("-m", "--metadata", type=str, required=True, help="Path to the metadata JSON")
    parser.add_argument("-c", "--chapter", type=str, required=True, help="Chapter number (e.g. 1.0)")
    
    args = parser.parse_args()

    raw_script = extract_text_from_chapter(args.metadata, args.chapter)
    
    if raw_script:
        with open(args.metadata, 'r') as f:
            meta = json.load(f)

        # Build Structured Artifact
        artifact = {
            "manga_title": meta["manga_title"],
            "manga_id": meta["manga_id"],
            "chapter_number": args.chapter,
            "source_language": meta["chapter_map"][args.chapter]["lang"],
            "raw_text": raw_script,
            "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # --- NEW ORGANIZED FOLDER LOGIC ---
        # 1. Standardized Title Slug
        raw_title = meta["manga_title"]
        safe_title = "".join([c for c in raw_title if c.isalpha() or c.isspace()]).replace(" ", "_").lower()
        
        # 2. Create nested directory: data/artifacts/[series_title]/
        output_dir = os.path.join("./data/artifacts", safe_title)
        os.makedirs(output_dir, exist_ok=True)
        
        # 3. Create standardized filename: ch1.0_artifact.json
        filename = f"ch{args.chapter}_artifact.json"
        file_path = os.path.join(output_dir, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
            
        print("-" * 50)
        print(f"✅ Extraction Complete!")
        print(f"💾 Structured Artifact saved to: {file_path}")