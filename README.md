# 📚 Comic CliffNotes

> **Never reread 50 chapters just to remember what happened.**
> An automated, spoiler-free recap engine for manga and manhwa, built for the 2026 AI ecosystem.

---

## 💡 The "Waterfall" Pipeline
Comic CliffNotes uses a resilient, high-concurrency extraction pipeline. If English chapters are unavailable, the engine automatically **"waterfalls"** through alternative languages (Spanish, Portuguese, French, or Japanese) to extract raw data. 

The **Gemini 2.5 Flash** AI then translates and synthesizes this data into professional English summaries, maintaining **Narrative Continuity** by referencing previous chapter context.

---

## ⚡ High-Performance OCR
The extraction engine is optimized for speed and resource management:
* **Parallel Ingestion:** Downloads up to 10 pages simultaneously via `ThreadPoolExecutor`, reducing I/O wait times by ~70%.
* **Multi-Core OCR:** Tesseract processes are distributed across available CPU cores for Latin-based languages.
* **Intelligent Branching:** Heavy AI models (Manga-OCR for Japanese) run sequentially to protect system RAM, while lightweight engines run in parallel.

---

## 📂 Project Structure
```text
.
├── core/                # The "Brains" (Logic)
│   ├── config.py        # 🎯 Single Source of Truth (Paths, Slugs, Secrets)
│   ├── mangadex.py      # API interaction & Waterfall logic
│   ├── ocr_engine.py    # High-concurrency extraction engine
│   ├── ai_agent.py      # Gemini 2.5 Flash (Synthesis & Narrative Memory)
│   └── usage_tracker.py # $0.00 Safety Guardrail
├── data/                # The "State" (Storage)
│   ├── metadata/        # Title-slugged chapter maps
│   ├── artifacts/       # Title-slugged raw OCR text
│   └── summaries/       # Title-slugged recaps + manifest.json
├── run_pipeline.py      # The Orchestrator
├── bulk_runner.py       # The High-Volume Worker (with tqdm progress)
└── requirements.txt     
```

---

## 🏗️ Data Architecture: Future-Proofing
To ensure 100% compatibility with future frontend integrations (e.g., Ruby on Rails), we use an **Enterprise Data Schema**:

* **Recursive Context:** Chapters are summarized with "Narrative Memory." The AI reads the *previous* summary to maintain character and plot continuity.
* **Nearest Neighbor Failsafe:** If a chapter is missing (e.g., Chapter 3 fails), the engine "reaches back" to the most recent available summary to bridge the story gap.
* **Manifest Indexing:** A `manifest.json` provides a high-speed index for all available summaries, timestamps, and schema versions.

---

## 🚀 Usage

### 1. Bulk Processing (The "Data Factory")
Process a range of chapters with a visual progress bar and automatic ETA.
```bash
python bulk_runner.py -t "Omniscient Reader" -s 1 -e 10
```

### 2. Pipeline Modes (`-m`)
| Mode | Action | Use Case |
| :--- | :--- | :--- |
| `full` | Metadata → OCR → AI | Standard end-to-end run (Default). |
| `extract` | Metadata → OCR | Ingest data without using AI quota. |
| `summarize` | AI Only | Process pre-extracted artifacts into summaries. |

---

## 🛡️ Budget & Safety Guardrails
This project is designed to run entirely on the **Google AI Free Tier**.
* **Usage Tracker:** Successes are logged in `data/usage_log.json`.
* **Kill Switch:** The pipeline halts the AI phase if the daily limit is reached.
* **Git Integrity:** `.gitignore` pre-configured to exclude `__pycache__`, system secrets, and temporary image blobs.

---

## 🚀 Roadmap
- [x] Multi-engine OCR router (Tesseract + Manga-OCR).
- [x] High-concurrency parallel extraction (OCR/Downloads).
- [x] Centralized `config.py` Single Source of Truth.
- [x] **Recursive Context Memory:** Narrative continuity across chapters.
- [x] **Bulk Processing:** Range support with `tqdm` progress tracking.
- [ ] **Rails Integration:** Build the "CliffNotes Dashboard" to display recaps.
