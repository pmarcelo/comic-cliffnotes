# 🗺️ Comic Cliffnotes - Pipeline Roadmap

## 📊 1. Telemetry & Audit Logging (Performance Metrics)
- [ ] Create a `run_logs/` directory to store historical execution data.
- [ ] Build a logger that generates a `run_YYYYMMDD_HHMMSS.json` at the end of each execution.
- [ ] **Track Global Metrics:** Capture `manga_title` and `total_chapters_processed`.
- [ ] **Track Tier 1 (Ingest):** Log download speed and extraction time.
- [ ] **Track Tier 2 (OCR):** Log total images processed, average time per page, and GPU VRAM spikes.
- [ ] **Track Tier 3 (AI):** Log total API requests made, success/fail rate, average response latency, and token consumption.

## 🛑 2. The "Fail Fast" Circuit Breaker (API Limits)
- [ ] Update `ai_agent.py` to explicitly catch the `429 RESOURCE_EXHAUSTED` status code.
- [ ] Create a custom `RateLimitExhaustedError` instead of returning `None`.
- [ ] Update the Tier 3 loop to catch this new error and gracefully halt the AI processing.
- [ ] Ensure the manifest state saves properly before the script safely exits to prevent data loss.

## ⏱️ 3. Smart Rate Limiting (Bolstering the Throttle)
- [ ] Remove the hardcoded `time.sleep(8)` that blindly waits *after* a response.
- [ ] Implement a dynamic request throttler (Token Bucket or Timestamp Checker).
- [ ] Record the exact timestamp when a request is fired.
- [ ] Before firing the *next* request, calculate the exact millisecond difference to guarantee a safe, perfectly optimized 15 Requests Per Minute.

## 🤖 4. Full Automation (The 'Drive Daemon')
- [ ] Write a lightweight wrapper script (`watcher.py`).
- [ ] Set up a background polling daemon (via Windows Task Scheduler or a python infinite loop with a 15-minute sleep).
- [ ] Configure the daemon to query the target Google Drive folder for new `.zip` or `.cbz` files.
- [ ] Add logic to cross-reference found files with the `metadata.json` master lists.
- [ ] Automatically trigger `processor.py` for any new, unprocessed archives.

## 🗄️ 5. State Management: Checksum-Validated Ledger Sync (CVLS)
- [ ] **Ledger Expansion:** Update `metadata.json` schema to include an `ingested_archives` list.
- [ ] **Fingerprinting:** Implement MD5 checksum tracking using Google Drive's native `md5Checksum` field.
- [ ] **Delta Logic:** Build a "Comparison Engine" in `watcher.py` that identifies the delta between Drive files and the local ledger.
- [ ] **Partial Ingest Support:** Modify `processor.py` to allow appending new chapters to an existing title without wiping existing AI summaries.
- [ ] **Stability Check:** Implement a 5-minute "Cool Down" timer for newly detected files to prevent processing partial uploads.
- [ ] **(Future Exploration):** Evaluate migrating the JSON ledger to a local SQLite DB for faster lookups once the library exceeds 1,000 chapters.
