import os
from pathlib import Path
from core import config
from core.utils import file_io, network
import shutil


def fetch_and_unpack(title: str, url: str) -> Path:
    """
    Downloads the archive and unpacks it into a standard 'sync_ingest' folder.
    """
    slug = file_io.get_safe_title(title)
    archive_dir = config.DATA_DIR / "raw_archives"
    # We use a static name here because the 'Chapter' logic lives in the DB, not the folder name
    extract_dir = config.DATA_DIR / "extracted_images" / slug / "sync_ingest"
    zip_path = archive_dir / f"{slug}_ingest.zip"

    file_io.ensure_directory(archive_dir)
    
    # If the folder exists and isn't empty, we assume a resume/debug state
    if extract_dir.exists() and any(extract_dir.iterdir()):
        print(f"📍 Using existing files in {extract_dir}")
        return extract_dir

    print(f"🔗 Fetching archive from Google Drive...")
    if not network.download_gdrive(url, str(zip_path)):
        raise ConnectionError("Failed to download from Google Drive.")

    print("📦 Extracting to workspace...")
    if not file_io.extract_archive(str(zip_path), str(extract_dir)):
        raise IOError("Failed to unpack ZIP archive.")

    if zip_path.exists():
        os.remove(zip_path)

    print(f"✅ Ready for Sync: {extract_dir}")
    return extract_dir

def scan_for_chapter_folders(extract_dir: Path):
    """
    Recursively finds folders containing manga pages. 
    Handles deep nesting and extensionless files (e.g., '0', '1', '2').
    """
    valid_folders = []
    image_exts = {'.jpg', '.jpeg', '.png', '.webp'}
    
    for root, _, files in os.walk(extract_dir):
        if "__MACOSX" in root: 
            continue

        # A folder is a "Chapter Folder" if it contains:
        # 1. Standard image extensions (.jpg, .png, etc.)
        # 2. OR purely numeric filenames (Tachimanga's extensionless format)
        has_content = any(
            Path(f).suffix.lower() in image_exts or f.isdigit() 
            for f in files
        )

        if has_content:
            valid_folders.append(Path(root))
            
    # Sort numerically based on the full path parts to ensure 
    # Chapter 2 doesn't come after Chapter 10.
    valid_folders.sort(key=lambda x: [int(c) if c.isdigit() else c for c in x.parts])
    
    print(f"🔍 Found {len(valid_folders)} valid chapter folders.")
    return valid_folders

def organize_into_chapters(base_extract_dir: Path, start_chapter: int):
    """
    Finds messy nested folders and moves their content into 
    clean /chapter_number/ folders.
    """
    # 1. Find the messy folders using our 'smart' scanner
    messy_folders = scan_for_chapter_folders(base_extract_dir)
    
    final_paths = []
    current_num = start_chapter
    
    # The parent directory of 'sync_ingest' (e.g., .../extracted_images/test/)
    series_dir = base_extract_dir.parent 

    for folder in messy_folders:
        # Create the clean target path: .../test/1/
        target_path = series_dir / str(current_num)
        
        # Ensure the clean folder exists
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Move all files from the messy deep folder to the clean shallow folder
        for file in folder.iterdir():
            if file.is_file():
                shutil.move(str(file), str(target_path / file.name))
        
        print(f"📦 Organized: {folder.name} -> {target_path}")
        final_paths.append(target_path)
        current_num += 1
        
    # 2. Cleanup: Delete the empty 'sync_ingest' tree after moving everything out
    shutil.rmtree(base_extract_dir)
    
    return final_paths