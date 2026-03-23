import argparse
import time
from tqdm import tqdm 
from core import config, helpers

# Failsafe in case usage_tracker is missing or causing silent errors
try:
    from core.usage_tracker import check_usage
except ImportError:
    print("⚠️ Could not import usage_tracker. Defaulting to True.")
    def check_usage(): return True

def main():
    parser = argparse.ArgumentParser(description="Comic-CliffNotes Bulk Processor")
    parser.add_argument("-t", "--title", required=True)
    parser.add_argument("-s", "--start", type=float, required=True)
    parser.add_argument("-e", "--end", type=float, required=True)
    parser.add_argument("-m", "--mode", default="full", choices=["full", "extract", "summarize"])
    args = parser.parse_args()

    print(f"🔍 Locating '{args.title}' on MangaDex...")
    m_id, m_title = helpers.fetch_manga_id_and_title(args.title)
    
    if not m_id:
        print("❌ Could not find manga title.")
        return

    full_map = helpers.fetch_chapter_map(m_id)
    queue = sorted([ch for ch in full_map.keys() if args.start <= ch <= args.end])
    
    if not queue:
        print(f"⚠️ No chapters found in range {args.start}-{args.end}.")
        return

    print(f"\n✅ Target: {m_title}")
    print(f"📋 Found {len(queue)} chapters to process.")
    print("="*50)

    success_count = 0
    pbar = tqdm(queue, desc="🚀 Overall Progress", unit="ch")
    
    # --- START BULK TIMER ---
    bulk_start_time = time.perf_counter()

    for chapter in pbar:
        pbar.set_description(f"📦 Processing Ch {chapter}")

        if args.mode in ["full", "summarize"] and not check_usage():
            pbar.write("\n🚦 Daily AI Limit Reached. Bulk run paused.")
            break

        cmd = ["python", "run_pipeline.py", "-t", m_title, "-c", str(chapter), "-m", args.mode]
        
        if helpers.run_command(cmd):
            success_count += 1
        else:
            pbar.write(f"⚠️ Warning: Chapter {chapter} failed.")
        
        time.sleep(1)

    # --- END BULK TIMER & CALCULATE METRICS ---
    bulk_total_time = time.perf_counter() - bulk_start_time
    mins, secs = divmod(bulk_total_time, 60)
    avg_time = bulk_total_time / len(queue) if queue else 0

    print("\n" + "🏆" + "="*48 + "🏆")
    print(f"🏁 BULK RUN FULLY COMPLETE: {m_title}")
    print(f"✅ Chapters Processed: {success_count} / {len(queue)}")
    print(f"⏱️  Total Run Time:   {int(mins)}m {secs:.2f}s")
    print(f"📊 Average Speed:    {avg_time:.2f}s per chapter")
    print("🏆" + "="*48 + "🏆\n")

if __name__ == "__main__":
    main()