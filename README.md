# 📚 Comic CliffNotes

> **Never reread 50 chapters just to remember what happened.**
> An automated, spoiler-free translation and recap engine for manga and manhwa.

---

## 💡 The "Waterfall" Pipeline
Comic CliffNotes uses a resilient extraction pipeline. If English chapters are unavailable, the engine automatically **"waterfalls"** through alternative languages (Spanish, Portuguese, French, or Japanese) to extract raw data. 

The **Gemini 2.5 Flash** AI then translates and synthesizes this data into professional English summaries.

---

## 📂 Project Structure
Organized for scalability and data separation:
```text
.
├── core/                # The "Brains" (Logic)
│   ├── mangadex.py      # API interaction & Waterfall logic
│   ├── ocr_engine.py    # Image processing (Tesseract/Manga-OCR)
│   ├── ai_agent.py      # Gemini 2.5 Flash (Translation & Synthesis)
│   └── usage_tracker.py # $0.00 Safety Guardrail
├── data/                # The "State" (Storage)
│   ├── metadata/        # Series maps & chapter IDs
│   ├── artifacts/       # Raw OCR text (JSON)
│   └── summaries/       # Final English Recaps (JSON)
├── run_pipeline.py      # The Orchestrator
└── requirements.txt     
```

---

## 🚀 Usage

The pipeline is managed via `run_pipeline.py`. It is **idempotent**, meaning it will skip work that has already been completed unless forced.

### Basic Command
```bash
python run_pipeline.py -t "Omniscient Reader" -c 1
```

### Pipeline Modes (`-m`)
You can decouple data ingestion from AI synthesis to manage your API quota:

| Mode | Action | Use Case |
| :--- | :--- | :--- |
| `full` | Metadata → OCR → AI | Standard run (Default). |
| `extract` | Metadata → OCR | Use when Wi-Fi is fast but AI quota is low. |
| `summarize` | AI Only | Use to process "pre-extracted" artifacts. |

**Example (Extract only):**
```bash
python run_pipeline.py -t "Omniscient Reader" -c 1 -m extract
```

### Force Refresh (`-f`)
To re-run a chapter and overwrite existing files (e.g., after updating the AI prompt):
```bash
python run_pipeline.py -t "Omniscient Reader" -c 1 -f
```

### Bulk Processing
Process a range of chapters automatically. The runner fetches the actual chapter list from MangaDex to ensure accuracy.
```bash
python bulk_runner.py -t "Title" -s [start] -e [end] -m [mode]

---

## 🛡️ Budget & Safety Guardrails
This project is designed to run on the **Google AI Free Tier**.
* **Usage Tracker:** Every successful AI run is logged in `data/usage_log.json`.
* **Kill Switch:** The pipeline will automatically halt the AI step if you exceed your daily safety limit (Default: 200 chapters).
* **Spend Cap:** Recommended to set a $1.00 safety cap in Google Cloud Console as a "belt and suspenders" measure.

---

## 🚀 Roadmap
- [x] Multi-engine OCR router (Tesseract + Manga-OCR).
- [x] Idempotent "Smart" pipeline logic.
- [x] Gemini 2.5 Flash integration with 2026 SDK.
- [x] Decoupled `extract` vs `summarize` modes.
- [ ] **Bulk Processing:** Support for `--range 1-10`.
- [ ] **Context Memory:** Allow AI to read previous summaries for better continuity.
- [ ] **Rails Integration:** Build the frontend dashboard to display summaries.
```