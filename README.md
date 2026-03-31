# 📚 Comic CliffNotes

> **Never reread 50 chapters just to remember what happened.**
> An automated, spoiler-free recap engine for manga and manhwa, built for the modern AI ecosystem.

---

## ⚡ The "Portable" OCR Pipeline
Comic CliffNotes uses a custom-tuned, hardware-agnostic extraction engine built on **EasyOCR**. It is designed to run efficiently on both cloud CPUs (like GitHub Codespaces) and local NVIDIA GPUs without changing a single line of code.

* **Hardware-Aware Execution:** Automatically detects the `USE_GPU` toggle in your `.env` file to seamlessly switch between CUDA-accelerated processing and CPU mode.
* **Accuracy-First Image Processing:** Prioritizes raw pixel data to prevent AI "hallucinations" (e.g., misreading chapter numbers or character names), while downscaling images by 50% to triple CPU processing speeds.
* **Narrative Grouping:** Utilizes spatial logic (`paragraph=True`) to group scattered speech bubbles into cohesive paragraphs, providing the AI with actual narrative flow rather than fragmented words.
* **Intelligent Noise Scrubbing:** A Regex-powered blacklist automatically strips out scanlator credits, website URLs, and coordinate noise *before* it reaches the AI.

---

## 🧠 Dual-Engine AI Synthesis
The pipeline features a dynamic routing system that allows you to swap between cloud and local AI models on the fly, depending on your hardware limits and API quotas.

* **Cloud Engine (Gemini 3.1 Flash):** The default engine. Fast, highly capable, and requires zero local VRAM. Paced via smart rate-limiting to stay within free-tier API quotas.
* **Local Engine (Llama 3.1 via Ollama):** The off-grid option. Utilizes an 8-Billion parameter narrative model running entirely on your local GPU. 
* **VRAM Protection (Lazy Loading):** The pipeline is specifically architected for standard 8GB GPUs. EasyOCR is lazy-loaded so PyTorch does not hoard VRAM, allowing the pipeline to dedicate 100% of the graphics card to the Llama 3.1 model during the summary phase.

---

## 📂 Project Structure
```text
.
├── .env                 # 🛑 Hardware Toggles & API Keys (Git Ignored)
├── core/                # The "Brains" (Logic)
│   ├── config.py        # 🎯 Smart Config (Loads .env, sets paths/limits)
│   ├── extractors/      # Google Drive ingestion logic
│   ├── processors/      # EasyOCR extraction & Image Pre-processing
│   ├── intelligence/    # Dual AI Agents (Gemini Cloud & Local Ollama)
│   └── utils/           # JSON and file handlers
├── data/                # The "State" (Storage)
│   ├── artifacts/       # Master manifest.json and Title-slugged metadata
│   ├── extracted_images/# Temporary workspace for Tier 1
│   ├── raw_archives/    # Downloaded ZIP files
│   └── summaries/       # Final AI .json outputs
├── processor.py         # The Main Orchestrator
└── requirements.txt     # Clean, OS-Agnostic Dependencies
```

---

## 🚀 Setup & Usage

### 1. Environment Setup
Clone the repository and create an isolated Python virtual environment:
```bash
python -m venv venv

# Activate the environment:
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux (or Codespaces):
source venv/bin/activate
```

Create a `.env` file in the root directory:
```bash
# Hardware Toggle: Set to False for Cloud/CPU, True for Local NVIDIA GPU
USE_GPU=True

# Your Google AI Studio Key
GEMINI_API_KEY=your_actual_key_goes_here
```

### 2. Install Base Dependencies
Install the clean, cross-platform requirements:
```bash
pip install -r requirements.txt
```
*Optional: If you have a local NVIDIA GPU, install the CUDA-enabled version of PyTorch to supercharge OCR speeds:*
`pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121`

### 3. Install Local AI Infrastructure (Optional)
To run the AI pipeline completely offline and free:
1. Install [Ollama](https://ollama.com/).
2. Open a terminal and pull the narrative model: `ollama pull llama3.1`

*(Note: For an AI coding assistant inside VS Code, install the `Continue.dev` extension and pull `ollama run qwen2.5-coder:7b`).*

---

## 🛠️ Running the Pipeline
The `processor.py` orchestrator uses targeted command-line flags to manage GPU memory effectively.

**The "Night Shift" (GPU Heavy):** Downloads the archive and runs EasyOCR. Stops before the AI phase.
```bash
python processor.py -t "Series Title" -u "Google_Drive_URL" -c 1 --extract
```

**The "Day Shift" (Local AI):** Reads the extracted text and generates summaries locally using Llama 3.1. Bypasses PyTorch to dedicate 100% of VRAM to the LLM.
```bash
python processor.py -t "Series Title" --summarize --local-ai
```

**Cloud AI Mode:**
Run the summary phase using the Gemini API instead of the local GPU.
```bash
python processor.py -t "Series Title" --summarize
```

**Flags:**
* `-t` / `--title`: The name of the Manga/Manhwa.
* `-u` / `--url`: The Google Drive sharing link containing the ZIP archive.
* `-c` / `--start-chapter`: The narrative integer to start mapping from (Defaults to 1).
* `--extract`: Run Tiers 1 & 2 (Ingest and OCR) only.
* `--summarize`: Run Tiers 3 & 4 (AI and Cleanup) only.
* `--local-ai`: Route summaries to the local Ollama server instead of Gemini.

---

## 🏗️ Data Architecture: Future Web Stack
The project is transitioning from flat-file storage to an Enterprise Data Schema to support a full-stack web application.

* **Current State (CVLS):** A master `manifest.json` acts as the single source of truth, tracking extraction progress and file paths.
* **Target Architecture:** * **Database:** PostgreSQL utilizing `JSONB` columns for structured AI narrative data.
  * **Backend API:** Ruby on Rails to seamlessly model the Manga/Chapter relationships and serve robust JSON endpoints.
  * **Frontend:** A React web application to fetch, filter, and render the chapter summaries and key moments in a clean UI.

---

## 🚀 Master Roadmap

### 📊 1. Telemetry & Audit Logging (The Paper Trail)
- [ ] Create `run_logs/` directory for historical JSON metrics.
- [ ] **Ingest Metrics:** Track download speed and archive extraction time.
- [ ] **OCR Metrics:** Track total images, average time per page, and GPU VRAM spikes.
- [ ] **AI Metrics:** Track API success rate, response latency, and token consumption.

### 🛑 2. "Fail Fast" Circuit Breaker (✅ COMPLETED)
- [x] Update `ai_agent.py` to catch `429 RESOURCE_EXHAUSTED` errors.
- [x] Implement logic to halt Tier 3 immediately to prevent infinite loops.
- [x] Ensure the manifest saves the current "Resume Point" before the script exits.

### ⏱️ 3. Smart Rate Limiting (The Throttle)
- [ ] Replace hardcoded `sleep(10)` with a dynamic timestamp-based throttler.
- [ ] Calculate the exact millisecond delay needed to hit specific RPMs perfectly.

### 🔐 4. Identity & Permissions (The Robot Upgrade)
- [ ] Create a Google Cloud Service Account and download the JSON key.
- [ ] Share the target GDrive folder with the Service Account email as 'Editor'.
- [ ] Refactor `cloud_drive.py` to use authenticated API calls instead of public links.

### 🗄️ 5. State Management: The Hybrid Ledger (CVLS)
- [ ] **Ledger Expansion:** Add `ingested_archives` (ID + MD5) to `metadata.json`.
- [ ] **Fingerprinting:** Use MD5 checksums to prevent processing the same data twice.
- [ ] **Stability Check:** Implement 5-minute cooldown for new files to ensure upload completion.
- [ ] **Archive Move:** Build logic to move finished zips from `/inbound` to `/processed`.

### 🖥️ 6. Mission Control GUI (Streamlit Dashboard)
- [ ] **Systems Header:** Indicators for GPU (CUDA) status, API health, and Drive connection.
- [ ] **Queue Manager:** Table of detected zips in Drive with a manual "Process Now" override.
- [ ] **Pipeline Visualizer:** Real-time progress bars for OCR and AI stages.
- [ ] **Live Preview:** A scrolling window showing the latest AI summaries as they generate.
- [ ] **Manual Knobs:** Sliders to adjust API delay and toggles to run specific Tiers.
- [ ] **Emergency Stop:** A "Big Red Button" to safely kill the process and save state.

### 🤖 7. The Watcher Daemon (Background Logic)
- [ ] Write `watcher.py` as a non-blocking loop that powers the GUI's "Auto-Scan" feature.
- [ ] Implement the "Self-Healing" pattern (Global Try-Except) to prevent network glitches from killing the app.

### 🧠 8. Dual-Engine AI Routing & Hardware Optimization (✅ COMPLETED)
- [x] **Local Agent:** Created `local_agent.py` to interface natively with the Ollama JSON API.
- [x] **Pipeline Router:** Updated `tier_3_ai` to dynamically switch between Gemini Cloud and the Local LLM.
- [x] **CLI Control:** Added `--extract`, `--summarize`, and `--local-ai` flags for granular pipeline control.
- [x] **VRAM Protection:** Wrapped EasyOCR in a lazy-loading function to prevent PyTorch from hoarding the 8GB GPU memory during AI shifts.
- [x] **Infrastructure Setup:** Installed Ollama and selected `llama3.1` (8B) as the optimal narrative engine.

### 🗄️ 9. Database Migration & Web Architecture Prep
- [ ] **PostgreSQL Setup:** Install and configure a local PostgreSQL database to replace flat file storage.
- [ ] **Schema Design:** Map out tables for `Manga`, `Chapters`, and utilize `JSONB` columns.
- [ ] **ETL Refactor:** Update the Python worker pipeline to `INSERT` records directly into the database.
- [ ] **Full-Stack Foundation:** Structure the database to smoothly plug into a Ruby on Rails backend API and React frontend.
