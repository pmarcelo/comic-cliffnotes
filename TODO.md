# 🗺️ Comic Cliffnotes - Master Roadmap

## 📊 1. Telemetry & Audit Logging (The Paper Trail)
- [ ] Create `run_logs/` directory for historical JSON metrics.
- [ ] **Ingest Metrics:** Track download speed and archive extraction time.
- [ ] **OCR Metrics:** Track total images, average time per page, and GPU VRAM spikes.
- [ ] **AI Metrics:** Track API success rate, response latency, and token consumption.

## 🛑 2. "Fail Fast" Circuit Breaker (✅ COMPLETED)
- [x] Update `ai_agent.py` to catch `429 RESOURCE_EXHAUSTED` errors.
- [x] Implement logic to halt Tier 3 immediately to prevent infinite loops.
- [x] Ensure the manifest saves the current "Resume Point" before the script exits.

## ⏱️ 3. Smart Rate Limiting (The Throttle)
- [ ] Replace hardcoded `sleep(10)` with a dynamic timestamp-based throttler.
- [ ] Calculate the exact millisecond delay needed to hit specific RPMs perfectly.

## 🔐 4. Identity & Permissions (The Robot Upgrade)
- [ ] Create a Google Cloud Service Account and download the JSON key.
- [ ] Share the target GDrive folder with the Service Account email as 'Editor'.
- [ ] Refactor `cloud_drive.py` to use authenticated API calls instead of public links.

## 🗄️ 5. State Management: The Hybrid Ledger (CVLS)
- [ ] **Ledger Expansion:** Add `ingested_archives` (ID + MD5) to `metadata.json`.
- [ ] **Fingerprinting:** Use MD5 checksums to prevent processing the same data twice.
- [ ] **Stability Check:** Implement 5-minute cooldown for new files to ensure upload completion.
- [ ] **Archive Move:** Build logic to move finished zips from `/inbound` to `/processed`.

## 🖥️ 6. Mission Control GUI (Streamlit Dashboard)
- [ ] **Systems Header:** Indicators for GPU (CUDA) status, API health, and Drive connection.
- [ ] **Queue Manager:** Table of detected zips in Drive with a manual "Process Now" override.
- [ ] **Pipeline Visualizer:** Real-time progress bars for OCR and AI stages.
- [ ] **Live Preview:** A scrolling window showing the latest AI summaries as they generate.
- [ ] **Manual Knobs:** Sliders to adjust API delay and toggles to run specific Tiers (e.g., "OCR Only").
- [ ] **Emergency Stop:** A "Big Red Button" to safely kill the process and save state.

## 🤖 7. The Watcher Daemon (Background Logic)
- [ ] Write `watcher.py` as a non-blocking loop that powers the GUI's "Auto-Scan" feature.
- [ ] Implement the "Self-Healing" pattern (Global Try-Except) to prevent network glitches from killing the app.

## 🧠 8. Dual-Engine AI Routing & Hardware Optimization (✅ COMPLETED)
- [x] **Local Agent:** Created `local_agent.py` to interface natively with the Ollama JSON API.
- [x] **Pipeline Router:** Updated `tier_3_ai` to dynamically switch between Gemini Cloud and the Local LLM.
- [x] **CLI Control:** Added `--extract`, `--summarize`, and `--local-ai` flags for granular pipeline control.
- [x] **VRAM Protection:** Wrapped EasyOCR in a lazy-loading function to prevent PyTorch from hoarding the 8GB GPU memory during AI summary shifts.
- [x] **Infrastructure Setup:** Installed Ollama and selected `llama3.1` (8B) as the optimal narrative engine.

## 🗄️ 9. Database Migration & Web Architecture Prep (The Next Step)
- [ ] **PostgreSQL Setup:** Install and configure a local PostgreSQL database to replace flat `.txt` and `.json` file storage.
- [ ] **Schema Design:** Map out tables for `Manga`, `Chapters`, and utilize `JSONB` columns for the structured AI narrative data.
- [ ] **ETL Refactor:** Update the Python worker pipeline to `INSERT` records directly into the database instead of saving files to the hard drive.
- [ ] **Full-Stack Foundation:** Structure the database to smoothly plug into a Ruby on Rails backend API, preparing the data to be consumed and displayed by a React frontend.