# 🗺️ Comic Cliffnotes - Master Roadmap

## 📊 1. Telemetry & Audit Logging
- [ ] Create `run_logs/` directory for historical JSON metrics.
- [ ] Log **Tier 1 (Ingest):** Download speed and extraction time.
- [ ] Log **Tier 2 (OCR):** Images processed, avg time per page, and GPU VRAM spikes.
- [ ] Log **Tier 3 (AI):** API success rate, response latency, and token consumption.

## 🛑 2. "Fail Fast" Circuit Breaker
- [ ] Update `ai_agent.py` to catch `429 RESOURCE_EXHAUSTED` specifically.
- [ ] Raise a custom `RateLimitExhaustedError` to halt the loop immediately.
- [ ] Ensure the manifest saves the current state before the script exits.

## ⏱️ 3. Smart Rate Limiting
- [ ] Replace `sleep(8)` with a dynamic timestamp-based throttler.
- [ ] Calculate the exact millisecond delay needed to hit 15 RPM perfectly.

## 🔐 4. Identity & Permissions (The Robot Upgrade)
- [ ] Create a Google Cloud Service Account and download the JSON key.
- [ ] Share the target GDrive folder with the Service Account email as 'Editor'.
- [ ] Migrate `cloud_drive.py` from public `gdown` links to authenticated API calls.

## 🗄️ 5. State Management: The Hybrid Ledger
- [ ] **Ledger Expansion:** Add `ingested_archives` (ID + MD5) to `metadata.json`.
- [ ] **Stability Check:** Implement 5-minute cooldown for new files.
- [ ] **Archive Move:** Build the `move_file_to_processed` logic to clean the inbound folder.

## 🤖 6. The Watcher Daemon
- [ ] Write `watcher.py` as an infinite loop polling script.
- [ ] Implement cross-referencing logic between Drive and the local Ledger.
- [ ] (Optional) Set up Windows Task Scheduler to trigger the watcher on boot.
