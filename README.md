# 📚 Comic CliffNotes

> **Never reread 50 chapters just to remember what happened.**
> An automated, spoiler-free recap engine for manga and manhwa, built for the 2026 AI ecosystem.

---

## 💡 The "Waterfall" Pipeline
Comic CliffNotes uses a resilient extraction pipeline. If English chapters are unavailable, the engine automatically **"waterfalls"** through alternative languages (Spanish, Portuguese, French, or Japanese) to extract raw data. 

The **Gemini 2.5 Flash** AI then translates and synthesizes this data into professional English summaries, organized by a centralized configuration manager.

---

## 📂 Project Structure
Organized for strict data separation and centralized logic:
```text
.
├── core/                # The "Brains" (Logic)
│   ├── config.py        # 🎯 Single Source of Truth (Paths, Slugs, Env)
│   ├── mangadex.py      # API interaction & Waterfall logic
│   ├── ocr_engine.py    # Image processing (Tesseract/Manga-OCR)
│   ├── ai_agent.py      # Gemini 2.5 Flash (Synthesis & Manifesting)
│   └── usage_tracker.py # $0.00 Safety Guardrail
├── data/                # The "State" (Storage)
│   ├── metadata/        # Title-slugged chapter maps
│   ├── artifacts/       # Title-slugged raw OCR text
│   └── summaries/       # Title-slugged recaps + manifest.json
├── run_pipeline.py      # The Orchestrator
├── bulk_runner.py       # The High-Volume Worker
└── requirements.txt     
```

---

## 🚀 Usage

The pipeline is managed via the root orchestrators. All paths and directory creations are handled automatically by the `config` module.

### 1. Single Chapter Run
```bash
python run_pipeline.py -t "Omniscient Reader's Viewpoint" -c 1
```

### 2. Bulk Processing (The "Data Factory")
Process a range of chapters. The runner resolves the official title from MangaDex and automates the entire queue.
```bash
python bulk_runner.py -t "Omniscient Reader" -s 1 -e 10
```

### 3. Pipeline Modes (`-m`)
Manage your AI quota by decoupling ingestion from synthesis:
| Mode | Action | Use Case |
| :--- | :--- | :--- |
| `full` | Metadata → OCR → AI | Standard end-to-end run (Default). |
| `extract` | Metadata → OCR | Ingest data without using AI quota. |
| `summarize` | AI Only | Process pre-extracted artifacts into summaries. |

---

## 🏗️ Data Architecture: Future-Proofing
To ensure 100% compatibility with future frontend integrations (e.g., Ruby on Rails), we use an **Enterprise Data Schema**:

* **Manifest Indexing:** Each series folder in `data/summaries/` contains a `manifest.json`. This acts as a high-speed index of all available chapters, timestamps, and schema versions.
* **The Envelope Pattern:** Summaries are wrapped in metadata (ISO timestamps, model versions, and schema IDs) to allow for easy data migrations.
* **Centralized Slugging:** All directory names are standardized via `core/config.py` to ensure consistency across the Metadata, Artifact, and Summary tiers.

---

## 🛡️ Budget & Safety Guardrails
This project is designed to run entirely on the **Google AI Free Tier**.
* **Usage Tracker:** Successes are logged in `data/usage_log.json`.
* **Kill Switch:** The pipeline halts the AI phase if the daily limit is reached.
* **Local Cleanup:** Raw images are deleted immediately after OCR; only the structured JSON artifacts remain.

---

## 🚀 Roadmap
- [x] Multi-engine OCR router (Tesseract + Manga-OCR).
- [x] Centralized `config.py` Single Source of Truth.
- [x] Bulk Processing support for chapter ranges.
- [x] Manifest Indexing for high-speed data retrieval.
- [ ] **Context Memory:** Allow AI to read `manifest.json` and previous summaries for narrative continuity.
- [ ] **Rails Integration:** Build the "CliffNotes Dashboard" to display recaps.
