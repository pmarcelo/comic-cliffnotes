import argparse
import time
from tqdm import tqdm
from core import config
from core.utils import file_io
from core.extractors import mangadex_api
from run_pipeline import run_chapter_pipeline

def main():
    parser = argparse.ArgumentParser(description="Bulk MangaDex OCR & Summary Pipeline")
    parser.add_argument("-t", "--title", required=True, help="Manga Title")
    parser.add_argument("-s", "--start", type=float, required=True, help="Start chapter")
    parser.add_argument("-e", "--end", type=float, required=True, help="End chapter")
    parser.add_argument("-m", "--mode", choices=["full", "extract", "summarize"], default="full")
    parser.add_argument("-f", "--force", action="store_true", help="Force re-run existing chapters")
    args = parser.parse_args()

    print(f"🔍 Fetching Master Metadata for '{args.title}'...")
    manga_id, official_title = mangadex_api.fetch_manga_id_and_title(args.title)
    if not manga_id:
        print("❌ Could not find Manga on MangaDex.")
        return

    print("🗺️ Mapping available chapters...")
    chapter_map = mangadex_api.fetch_chapter_map(manga_id)
    
    queue = [ch for ch in sorted(chapter_map.keys()) if args.start <= ch <= args.end]
    
    if not queue:
        print("⚠️ No chapters found in that range on MangaDex.")
        return

    print(f"\n🚀 Ready to process {len(queue)} chapters: {queue[0]} -> {queue[-1]}")
    time.sleep(2)

    success_count = 0
    pbar = tqdm(queue, desc="Overall Progress", unit="ch")
    
    for ch in pbar:
        ch_str = str(ch)
        if ch_str.endswith(".0"): ch_str = ch_str[:-2]
            
        pbar.set_description(f"Processing Ch {ch_str}")
        success = run_chapter_pipeline(title=official_title, chapter_str=ch_str, mode=args.mode, force=args.force)
        
        if success: success_count += 1
        else: pbar.write(f"⚠️ Chapter {ch_str} skipped or failed.")
            
    print(f"\n🏁 BULK RUN COMPLETE! Processed {success_count}/{len(queue)} chapters successfully.")

if __name__ == "__main__":
    main()