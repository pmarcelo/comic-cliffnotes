# 📚 Comic CliffNotes

> **Never reread 50 chapters just to remember what happened.**
> An automated, spoiler-free recap engine for manga and manhwa, built for the modern AI ecosystem.

---

## ⚡ The "Portable" OCR Pipeline
Comic CliffNotes uses a custom-tuned, hardware-agnostic extraction engine built on **EasyOCR**. It is designed to run efficiently on both cloud CPUs (like GitHub Codespaces) and local NVIDIA GPUs without changing a single line of code.

* **Hardware-Aware Execution:** Automatically detects the `USE_GPU` toggle in your `.env` file to seamlessly switch between CUDA-accelerated processing and CPU mode.
* **Accuracy-First Image Processing:** Prioritizes raw pixel data to prevent AI "hallucinations" (e.g., misreading chapter numbers or character names), while downscaling images by 50% to triple CPU processing speeds.
* **Narrative Grouping:** Utilizes spatial logic (`paragraph=True`) to group scattered speech bubbles into cohesive paragraphs, providing the AI with actual narrative flow rather than fragmented words.
* **Intelligent Noise Scrubbing:** A Regex-powered blacklist automatically strips out scanlator credits, website URLs, and coordinate noise *before* it reaches the AI, saving tokens and improving summary quality.

---

## 🧠 AI Synthesis (Gemini 2.0 Flash)
The **Gemini 2.0 Flash** AI translates and synthesizes the raw OCR data into professional English summaries, maintaining **Narrative Continuity** by referencing previous chapter context.

* **Recursive Context:** Chapters are summarized with "Narrative Memory." The AI reads the *previous* summary to maintain character and plot continuity.
* **Strict JSON Schemas:** Summaries are output in a strict, predictable JSON format (Chapter Num, Summary, Key Moments, Characters Present) for easy database ingestion.

---

## 📂 Project Structure
```text
.
├── .env                 # 🛑 Hardware Toggles & API Keys (Git Ignored)
├── core/                # The "Brains" (Logic)
│   ├── config.py        # 🎯 Smart Config (Loads .env, sets paths/limits)
│   ├── ocr_engine.py    # EasyOCR extraction & Image Pre-processing
│   ├── ai_agent.py      # Gemini 2.0 Flash (Synthesis & Narrative Memory)
│   └── utils/
│       └── file_io.py   # JSON and file handlers
├── data/                # The "State" (Storage)
│   ├── artifacts/       # Title-slugged folders with raw_ocr.txt
│   └── summaries/       # Title-slugged folders with summary.json
├── processor.py         # The Main Orchestrator
└── requirements.txt     
```

---

## 🚀 Setup & Usage

### 1. Environment Setup
Create a `.env` file in the root directory:
```bash
# Hardware Toggle: Set to False for Cloud/CPU, True for Local NVIDIA GPU
USE_GPU=False

# Your Google AI Studio Key
GEMINI_API_KEY=your_actual_key_goes_here
```

### 2. Install Dependencies
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu  # Or /cu118 for GPU
pip install easyocr numpy pillow opencv-python-headless python-dotenv google-genai
```

### 3. Run the Pipeline
Process your local chapters through the OCR and AI engines:
```bash
python processor.py
```

---

## 🏗️ Data Architecture: Future-Proofing
To ensure 100% compatibility with future frontend integrations (e.g., Ruby on Rails, Next.js), we use an **Enterprise Data Schema**:

* **Nearest Neighbor Failsafe:** If a chapter is missing (e.g., Chapter 3 fails), the engine "reaches back" to the most recent available summary to bridge the story gap.
* **Manifest Indexing:** A `manifest.json` provides a high-speed index for all available summaries, local directories, and schema versions.

---

## 🛡️ Budget & Safety Guardrails
This project is designed to run efficiently on the **Google AI Free Tier**.
* **Regex Pre-Cleaning:** Strips out junk data before the AI sees it, drastically reducing token usage.
* **Git Integrity:** `.gitignore` pre-configured to exclude `__pycache__`, the `.env` file, and temporary image blobs.

---

## 🚀 Roadmap
- [x] Integrate EasyOCR for robust English text extraction.
- [x] Build the "Portable Pipeline" (.env hardware toggles for CPU/GPU).
- [x] Implement Paragraph-Aware spatial grouping for better AI context.
- [x] Add Regex Blacklisting to remove scanlator watermarks.
- [x] **Recursive Context Memory:** Narrative continuity across chapters.
- [ ] **Rails Integration:** Build the "CliffNotes Dashboard" to display recaps.