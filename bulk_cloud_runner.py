import os
import argparse
import zipfile
import shutil
from pathlib import Path
from core import config
from core.utils import file_io, network # Ensure network.py exists for GDrive
from run_pipeline import run_chapter_pipeline

def find_chapter_folders(base_dir: str):
    """
    Dives into the 60/1360/62209/ structure to find folders with images.
    """
    chapter_map = {}
    print("🔍 Scanning for chapter folders...")
    
    for root, dirs, files in os.walk(base_dir):
        # A 'Chapter Folder' is one that contains the files '0', '1', etc.
        # or standard image extensions.
        has_images = any(f.isdigit() for f in files) or \
                     any(f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) for f in files)
        
        if has_images and not dirs: # It's a leaf folder
            folder_path = Path(root)
            ch_id = folder_path.name # e.g., '62209'
            
            chapter_map[ch_id] = {
                "uuid": ch_id,
                "local_dir": str(folder_path),
                "lang": "unknown",
                "title": f"Chapter {ch_id}"
            }
            print(f"  ✅ Found Chapter ID: {ch_id}")

    return chapter_map

def main():
    parser = argparse.ArgumentParser(description="Bulk Cloud Manga Processor")
    parser.add_argument("-t", "--title", required=True, help="Manga Title")
    parser.add_argument("-u", "--url", required=True, help="Google Drive Link")
    args = parser.parse_args()

    # 1. Setup Staging
    staging_dir = config.TEMP_DIR / "cloud_staging"
    file_io.cleanup_directory(staging_dir) # Uses the fix we just added
    
    archive_path = config.RAW_ARCHIVES_DIR / "master_archive.zip"

    # 2. Download from GDrive
    print(f"📥 Downloading archive for '{args.title}'...")
    # This handles the Google Drive 'view' link conversion automatically
    success = network.download_gdrive(args.url, str(archive_path))
    
    if not success:
        print("❌ Download failed. Check your link permissions.")
        return

    # 3. Extract
    print("📦 Extracting archive...")
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        zip_ref.extractall(staging_dir)

    # 4. Map Chapters
    chapter_map = find_chapter_folders(staging_dir)
    
    if not chapter_map:
        print("❌ No valid chapter folders found in the ZIP structure.")
        return

    # 5. Build Local Metadata
    slug = file_io.get_safe_title(args.title)
    metadata = {
        "manga_id": "local_cloud_import",
        "manga_title": args.title,
        "chapter_map": chapter_map
    }
    
    meta_path = config.ARTIFACTS_DIR / slug / "metadata.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    file_io.save_json(meta_path, metadata)

    print(f"🚀 Metadata ready. Starting pipeline for {len(chapter_map)} chapters.")
    print("-" * 50)

    # 6. Process
    for ch_id in sorted(chapter_map.keys()):
        print(f"\n🎬 Processing Chapter: {ch_id}")
        run_chapter_pipeline(title=args.title, chapter_str=ch_id, mode="full")

if __name__ == "__main__":
    main()