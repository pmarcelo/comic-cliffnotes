Here is the full, updated **README.md** content in Markdown format. You can copy and paste this directly into your file.

```markdown
# 📚 Comic CliffNotes

> **Never reread 50 chapters just to remember what happened.** > An automated, spoiler-free recap engine for manga and manhwa readers.

---

## 🛑 The Problem
In the webcomic community, "stacking chapters" is standard practice. Readers pause a series for months to let chapters build up, but by the time they return, they've forgotten the plot points, side characters, and power-scaling rules. Standard wikis are riddled with spoilers, and reading full chapter summaries takes too long.

## 💡 The Solution: The "Waterfall" Pipeline
**Comic CliffNotes** uses a resilient extraction pipeline that prioritizes content availability over language barriers. If English chapters are removed from trackers due to official licensing, the engine automatically **"waterfalls"** through a priority list of alternative languages (Spanish, Portuguese, French, or Japanese Raws) to extract the raw plot data for the AI to process.

---

## ⚙️ Architecture: The Ephemeral OCR Pipeline

This project uses a modular Python backend designed for speed, data privacy, and cross-language compatibility:

1.  **Metadata Mapping:** `mangadex.py` searches for a series and builds a `metadata.json` map, applying the language waterfall logic (**EN > ES > PT > FR > JA**).
2.  **Ephemeral Fetch:** `extractor.py` temporarily downloads images to a `/tmp` directory.
3.  **Intelligent Routing:** The engine detects the source language and routes the images to the optimal OCR engine:
    * **Tesseract OCR:** Optimized for Latin-alphabet languages (English, Portuguese, Spanish, French).
    * **Manga-OCR:** A specialized transformer-based AI model for high-accuracy Japanese text recognition.
4.  **Artifact Generation:** Raw text is bundled into a structured JSON "Artifact" in `api/ocr/outputs/`.
5.  **Secure Cleanup:** All raw images are immediately and permanently deleted from the server once the text is extracted.

---

## 🛠️ Installation & Setup

### 1. System Dependencies (OCR Engines)
You must have the Tesseract engine and relevant language packs installed at the OS level.

**For Linux (GitHub Codespaces / Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-por tesseract-ocr-eng tesseract-ocr-spa tesseract-ocr-fra
```

**For macOS (via Homebrew):**
```bash
brew install tesseract
brew install tesseract-lang
```

### 2. Python Environment
Install the required wrappers and AI models:
```bash
pip install -r requirements.txt
```
*Note: On the first run, the system will download the `manga-ocr` model weights (~444MB).*

---

## 🚀 Usage

The entire pipeline is orchestrated through a single runner script. Provide the manga title and the target chapter you wish to process.

```bash
python run_pipeline.py -t "Omniscient Reader" -c 1
```

### Output Files
* **`tmp/`**: Contains the `metadata.json` map for the series.
* **`api/ocr/outputs/`**: Contains the final structured JSON artifacts (e.g., `omniscientreader_ch1.0.json`) containing the raw extracted text.

---

## 📂 Project Structure
```text
.
├── api/
│   ├── mangadex/
│   │   └── mangadex.py     # API interaction & Waterfall logic
│   └── ocr/
│       ├── outputs/        # Final JSON text artifacts
│       └── extractor.py    # Image downloading & OCR routing
├── tmp/                    # Temporary storage (Auto-cleaned)
├── run_pipeline.py         # End-to-end Orchestrator
├── requirements.txt        # Python dependencies
└── README.md
```

---

## 🚀 Roadmap & Future Enhancements

- [x] Implement MangaDex API search and waterfall logic.
- [x] Build multi-engine OCR router (Tesseract + Manga-OCR).
- [x] Automate end-to-end pipeline via `run_pipeline.py`.
- [x] Integrate Gemini 2.5 Flash for translation and synthesis.

### 🛠️ Planned Improvements
* **Budget & Usage Guardrail:** Create a `usage_tracker.py` to log API calls locally. Implement a "Kill Switch" that prevents script execution if the daily free-tier limit (e.g., 50 RPD) is approached, ensuring $0 spending.
* **Bulk Processing:** Update the runner to support chapter ranges (e.g., `--range 1-10`) to automate the extraction of entire story arcs in one session.
* **Enterprise Refactoring:** Transition from a "Script-based" architecture to a formal Python Package structure. Implement logging modules, custom Exception handling, and Unit Testing for the OCR logic.
* **Context-Aware Multi-Chapter Summaries:** Develop advanced prompt engineering that allows the AI to read previous chapter summaries. This ensures the recap for Chapter 10 "remembers" what happened in Chapter 9, creating a cohesive narrative flow.

---

## 📝 Disclaimer
This project does not host, distribute, or store copyrighted images. Image processing is performed entirely in temporary storage for the sole purpose of text extraction and analysis, after which the source files are immediately destroyed.
```
