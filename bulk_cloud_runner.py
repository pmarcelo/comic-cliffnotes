import os
import re
import argparse
import time
from pathlib import Path
from tqdm import tqdm

from core import config
from core.utils import file_io, network
from run_pipeline import run_chapter_pipeline

try:
    from core.usage_tracker import check_usage
except ImportError:
    def check_usage(): return True

def find_chapter_folders(base_dir: str) -> dict:
    chapter_map = {}
    valid_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    
    for root, dirs, files in os.walk(base_dir):
        images = [f for f in files if Path(f).suffix.lower() in valid_exts]
        if images:
            folder_name = Path(root).name
            match = re.search(r'(?:ch|chapter|ep)?\.?\s*(\d+(?:\.\d+)?)', folder_name, re.IGNORECASE)
            if not match:
                match = re.search(r'(\d+(?:\.\d+)?)', folder_name)
            if match:
                ch_num = float(match.group(1))
                chapter_map[ch_num] = root
    return chapter_map

def main():
    parser = argparse.ArgumentParser(description="Bulk Cloud Archive Processor")
    parser.add_argument("-t", "--title", required=True, help="Manga Title")
    parser.add_argument("-u", "--url", required=True, help="Google Drive or Direct Zip URL")
    parser.add_argument("-l", "--lang", default="en", help="Language code")
    parser.add_argument("-m", "--mode", default="full", choices=["full", "extract", "summarize"])
    args = parser.parse_args()

    slug = file_io.get_safe_title(args.title)
    staging_dir = config.DATA_DIR / "raw_archives" / f"{slug}_staging"
    master_zip = staging_dir / "master_upload.zip"
    
    file_io.cleanup_directory(staging_dir)
    file_io.ensure_directory(staging_dir)

    print("\n" + "="*50)
    print(f"☁️ BULK CLOUD IMPORT: {args.title}")
    print("="*50)

    if "drive.google.com" in args.url:
        success = network.download_gdrive(args.url, str(master_zip))
    else:
        success = network.download_direct_file(args.url, str(master_zip))
        
    if not success:
        print("❌ Failed to download the master archive.")
        return

    print("📦 Extracting master archive...")
    if not file_io.extract_archive(str(master_zip), str(staging_dir)): return
    os.remove(master_zip)

    print("🔍 Scanning extracted files for chapters...")
    chapter_folders = find_chapter_folders(str(staging_dir))
    
    if not chapter_folders:
        print("❌ Could not find any valid image folders.")
        return

    queue = sorted(list(chapter_folders.keys()))
    print(f"📋 Found {len(queue)} chapters: {queue}")
    time.sleep(2)
    
    success_count = 0
    pbar = tqdm(queue, desc="🚀 Overall Progress", unit="ch")
    bulk_start_time = time.perf_counter()

    for chapter in pbar:
        ch_str = str(chapter)
        if ch_str.endswith(".0"): ch_str = ch_str[:-2]
            
        pbar.set_description(f"📦 Processing Ch {ch_str}")

        if args.mode in ["full", "summarize"] and not check_usage():
            pbar.write("\n🚦 Daily AI Limit Reached. Bulk run paused.")
            break

        paths = file_io.get_paths(args.title, ch_str)
        metadata = {
            "manga_title": args.title,
            "manga_id": "bulk_cloud_import",
            "target_chapter": chapter,
            "chapter_map": {
                ch_str: {"lang": args.lang, "uuid": "local_import", "local_dir": chapter_folders[chapter]}
            }
        }
        file_io.save_json(metadata, paths["metadata"])

        success = run_chapter_pipeline(title=args.title, chapter_str=ch_str, mode=args.mode, force=False, url=None)
        if success: success_count += 1
        else: pbar.write(f"⚠️ Warning: Chapter {ch_str} failed.")

    file_io.cleanup_directory(staging_dir)
    
    bulk_total_time = time.perf_counter() - bulk_start_time
    mins, secs = divmod(bulk_total_time, 60)
    print("\n" + "🏆" + "="*48 + "🏆")
    print(f"🏁 BULK CLOUD RUN COMPLETE: {args.title}")
    print(f"✅ Chapters Processed: {success_count} / {len(queue)}")
    print(f"⏱️  Total Run Time:   {int(mins)}m {secs:.2f}s")
    print("🏆" + "="*48 + "🏆\n")

if __name__ == "__main__":
    main()