# 📚 Comic CliffNotes

> **Never reread 50 chapters just to remember what happened.**
> An automated, spoiler-free recap engine for manga and manhwa, built for the modern AI ecosystem.

---

## ⚡ The "Portable" OCR Pipeline
Comic CliffNotes uses a custom-tuned, hardware-agnostic extraction engine built on **EasyOCR**. It is designed to run efficiently on both cloud CPUs (like GitHub Codespaces) and local NVIDIA GPUs without changing a single line of code.

* **Hardware-Aware Execution:** Automatically detects the `USE_GPU` toggle in your `.env` file to seamlessly switch between CUDA-accelerated processing and CPU mode.
* **Accuracy-First Image Processing:** Prioritizes raw pixel data to prevent AI "hallucinations," while downscaling images by 50% to triple CPU processing speeds.
* **Narrative Grouping:** Utilizes spatial logic (`paragraph=True`) to group scattered speech bubbles into cohesive paragraphs.
* **Intelligent Noise Scrubbing:** A Regex-powered blacklist strips out scanlator credits and website URLs *before* it reaches the AI.

---

## 🧠 Dual-Engine AI Synthesis
The pipeline features a dynamic routing system that allows you to swap between cloud and local AI models on the fly.

* **Cloud Engine (Gemini 3.1 Flash):** The default engine. Fast, highly capable, and requires zero local VRAM. 
* **Local Engine (Llama 3.1 via Ollama):** The off-grid option. Utilizes an 8-Billion parameter narrative model running entirely on your local GPU. 
* **VRAM Protection (Lazy Loading):** The pipeline is specifically architected for standard 8GB GPUs. EasyOCR is lazy-loaded so PyTorch does not hoard VRAM during the summary phase.

---

## 📂 Project Structure
```text
.
├── .env                 # 🛑 Hardware Toggles, API Keys, & DB URL (Git Ignored)
├── alembic/             # 🗄️ Database migration scripts and environment
├── core/                # The "Brains" (Logic)
│   ├── database.py      # 🔗 SQLAlchemy engine and Session logic
│   ├── models.py        # 🏛️ DB Schema (Manga, Chapter, Summary tables)
│   ├── config.py        # 🎯 Smart Config (Loads .env)
│   ├── extractors/      # Google Drive ingestion logic
│   ├── processors/      # EasyOCR extraction & Image Pre-processing
│   └── intelligence/    # Dual AI Agents (Gemini Cloud & Local Ollama)
├── data/                # The "Workplace" (Storage)
│   ├── extracted_images/# Temporary workspace for Tier 1
│   └── raw_archives/    # Downloaded ZIP files
├── alembic.ini          # Database migration configuration
├── processor.py         # The Main Orchestrator
└── requirements.txt     # Clean, OS-Agnostic Dependencies
```

---

## 🚀 Setup & Usage

### 1. Environment Setup
Clone the repository and create an isolated Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
# .\venv\Scripts\activate # Windows
```

Create a `.env` file in the root directory:
```bash
# Hardware Toggle
USE_GPU=True

# API Keys
GEMINI_API_KEY=your_key_here

# Database Connection (PostgreSQL)
DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@localhost:5432/manga_tracker"
```

### 2. Database Initialization
The pipeline uses **PostgreSQL** to track series metadata, chapters, and extraction progress.

1.  **Create the Database:**
    ```bash
    # Connect to postgres and run:
    CREATE DATABASE manga_tracker;
    ```
2.  **Run Migrations:**
    Use Alembic to build the tables based on the latest schema:
    ```bash
    alembic upgrade head
    ```

### 3. Running the Pipeline
The `processor.py` orchestrator uses targeted flags to manage workflow and memory.

**OCR Extraction (Tier 1 & 2):**
```bash
python processor.py -t "Series Title" -u "GDrive_URL" --extract
```

**AI Summarization (Tier 3 - Local Llama):**
```bash
python processor.py -t "Series Title" --summarize --local-ai
```

**AI Summarization (Tier 3 - Gemini Cloud):**
```bash
python processor.py -t "Series Title" --summarize
```

---

## 🏗️ Data Architecture: Full-Stack Ready
The project has transitioned from flat-file storage to a relational schema to support a future web interface.

* **Database (PostgreSQL):** Utilizes `JSONB` columns for flexible AI narrative data.
* **ORM (SQLAlchemy):** Ensures type-safety and easy querying for the Python worker.
* **Future Backend:** Structured to plug directly into a **Ruby on Rails** API.
* **Future Frontend:** A **React** dashboard will consume the DB records to display recaps visually.

---

## 🚀 Master Roadmap (Updated)

- [x] **Database Migration:** Replaced `manifest.json` with PostgreSQL and SQLAlchemy.
- [x] **Schema Versioning:** Implemented Alembic for robust database migrations.
- [ ] **API Layer:** Build Ruby on Rails controllers to serve chapter data as JSON.
- [ ] **Web UI:** Develop React frontend for browsing "CliffNotes" by series and chapter.
- [ ] **Service Account Auth:** Update `cloud_drive.py` for non-public GDrive folder access.