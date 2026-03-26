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

## 🧠 AI Synthesis (Gemini 3.1 Flash)
The **Gemini 3.1 Flash** AI translates and synthesizes the raw OCR data into professional English summaries, utilizing strict JSON enforcement.

* **Dumb AI, Smart Pipeline:** The AI is strictly responsible for creative synthesis (writing the summary). The Python orchestrator handles all mathematical chapter mapping to ensure sequential integrity.
* **Strict JSON Schemas:** Summaries are forced into a rigid JSON structure (`application/json` MIME type) to guarantee zero parsing errors during database ingestion.

---

## 📂 Project Structure
```text
.
├── .env                 # 🛑 Hardware Toggles & API Keys (Git Ignored)
├── core/                # The "Brains" (Logic)
│   ├── config.py        # 🎯 Smart Config (Loads .env, sets paths/limits)
│   ├── extractors/      # Google Drive ingestion logic
│   ├── processors/      # EasyOCR extraction & Image Pre-processing
│   ├── intelligence/    # Gemini 3.1 Flash Synthesis
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
USE_GPU=False

# Your Google AI Studio Key
GEMINI_API_KEY=your_actual_key_goes_here
```

### 2. Install Base Dependencies
Install the clean, cross-platform requirements:
```bash
pip install -r requirements.txt
```

### 3. ⚡ Optional: NVIDIA GPU Acceleration (Windows PC)
If you have a local NVIDIA graphics card and want to supercharge the OCR extraction speed, install the CUDA-enabled version of PyTorch **before** running the pipeline.
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```
*(Don't forget to set `USE_GPU=True` in your `.env` file!)*

### 4. Run the Pipeline
The `processor.py` orchestrator uses command-line arguments to build your database sequentially. 

**Standard Run (New Series):**
```bash
python processor.py -t "Series Title" -u "Google_Drive_URL" -c 1
```

**Continuous Update Mode (Appending new chapters):**
If you later download Chapters 91-120, point the orchestrator to the new URL and tell it where to start counting. It will automatically merge them into your existing manifest:
```bash
python processor.py -t "Series Title" -u "New_Drive_URL" -c 91
```

**Flags:**
* `-t` / `--title`: The name of the Manga/Manhwa.
* `-u` / `--url`: The Google Drive sharing link containing the ZIP archive.
* `-c` / `--start-chapter`: The narrative integer to start mapping from (Defaults to 1).

---

## 🏗️ Data Architecture: Future-Proofing
To ensure 100% compatibility with future frontend integrations (e.g., Ruby on Rails, Next.js), we use an **Enterprise Data Schema**:

* **Strict Sequencing:** Folder hashes are chronologically sorted and mapped to sequential integers during Tier 1 ingestion.
* **Manifest Indexing:** A master `manifest.json` acts as the single source of truth, tracking extraction progress, AI completion status, and local file paths.

---

## 🛡️ Budget & Safety Guardrails
This project is designed to run efficiently on the **Google AI Free Tier**.
* **Regex Pre-Cleaning:** Strips out junk data before the AI sees it, drastically reducing token usage.
* **Rate Limit Immunity:** Local processing bottlenecks inherently protect against API rate limits by pacing requests automatically.

---

## 🚀 Roadmap
- [x] Integrate EasyOCR for robust English text extraction.
- [x] Build the "Portable Pipeline" (.env hardware toggles for CPU/GPU).
- [x] Implement Paragraph-Aware spatial grouping for better AI context.
- [x] Add Regex Blacklisting to remove scanlator watermarks.
- [x] **Continuous Update Mode:** Smart manifest merging for new chapter batches.
- [ ] **Arc Summarizer:** Standalone macro-script to generate "Story Thus Far" recaps.
- [ ] **Rails Integration:** Build the "CliffNotes Dashboard" to display recaps.