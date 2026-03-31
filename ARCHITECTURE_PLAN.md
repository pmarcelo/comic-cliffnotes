I’ve drafted a comprehensive **Architecture & Deployment Strategy** for you. This document captures the "Hybrid Cloud" vision we’ve built today—where your local RTX 3060 Ti handles the heavy lifting, and the cloud handles the presentation.

Save this as `DOCS_DEPLOYMENT_PLAN.md` in your project root.

---

# 🏗️ Comic CliffNotes: Hybrid Cloud Architecture

## 🎯 The Vision
To build a high-performance, cost-zero web application where a **Local AI Worker** (NVIDIA GPU) processes data and pushes it to a **Cloud Presentation Layer** (Rails/React) for global access.

---

## 🏗️ 1. Technical Stack
| Layer | Technology | Hosting | Role |
| :--- | :--- | :--- | :--- |
| **Worker** | Python 3.x | Local PC (RTX 3060 Ti) | OCR Extraction & Llama 3.1 Summarization. |
| **Database** | PostgreSQL | **Neon.tech** | Single Source of Truth for all chapters and summaries. |
| **Backend** | Ruby on Rails (API Mode) | **Render.com** | Serves JSON data from Postgres to the Frontend. |
| **Frontend** | React.js | **Vercel** | The user interface for reading recaps. |

---

## 🛠️ 2. Step-by-Step Implementation

### Phase A: Database & Worker Sync
1. **Cloud Database Setup:** Create a project on Neon.tech and obtain the `DATABASE_URL`.
2. **Worker Integration:** Add `psycopg2` to the Python worker. Update `processor.py` to `INSERT` summaries into the cloud DB immediately after generation.
3. **Local Redundancy:** Maintain a local `data/summaries/` JSON folder as a "hard backup" in case of cloud connectivity issues.

### Phase B: Rails API Development
1. **API Initialization:** Generate a lightweight Rails API: `rails new api --api -d postgresql`.
2. **Schema Mapping:**
    - `Manga`: title, slug, cover_art_url.
    - `Chapter`: manga_id, chapter_number, raw_text, summary (JSONB).
3. **Deployment:** Push to GitHub and connect to Render.com. Add the Neon `DATABASE_URL` to Render's Environment Variables.

### Phase C: React Frontend
1. **Connection:** Point the React `fetch` calls to the Render API endpoint.
2. **PWA Support:** Enable Progressive Web App features so the site can be "installed" on mobile devices for free.

---

## 🛡️ 3. Data Persistence & Security (The "Triple-Lock")
To ensure your 10,000+ lines of data are never lost:

1. **Neon PITR (Point-in-Time Recovery):** Utilize Neon's 24-hour history to "undo" accidental data wipes.
2. **Automated Backups:** Implement a nightly local `pg_dump` via a Python script or Windows Task Scheduler:
   ```bash
   pg_dump -Fc -d "POSTGRES_URL" > backups/daily_backup.bak
   ```
3. **Local Source of Truth:** Your local `raw_ocr.txt` and `metadata.json` files are never deleted; the Cloud DB is treated as a "distribution mirror" of your local work.

---

## 🚦 4. Workflow Diagram
1. **LOCAL:** `processor.py` extracts OCR $\rightarrow$ Llama 3.1 generates JSON.
2. **PUSH:** Python script connects to **Neon Postgres** $\rightarrow$ `INSERT` new Chapter.
3. **SERVE:** **Rails API** on Render detects new record $\rightarrow$ sends to **React Frontend**.
4. **VIEW:** User opens the site on **Vercel** $\rightarrow$ reads spoiler-free summary.

---

