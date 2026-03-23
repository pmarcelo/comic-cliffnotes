# 📚 Comic CliffNotes

> **Never reread 50 chapters just to remember what happened.** > An automated, spoiler-free recap engine for manga and manhwa readers.

## 🛑 The Problem
In the webcomic community, "stacking chapters" is standard practice. Readers pause a series for months to let chapters build up, but by the time they return, they've forgotten the plot points, side characters, and power-scaling rules. Standard wikis are riddled with spoilers, and reading full chapter summaries takes too long.

## 💡 The Solution
**Comic CliffNotes** allows users to input their current chapter and generate a highly accurate, customized recap of *exactly* what they missed—without spoiling future events. 

### Core Features
* **Custom Range Recaps:** Select a specific chapter range (e.g., Chapters 30-45) and get a synthesized summary of just those chapters.
* **Spoiler-Free Guarantee:** The AI only has access to the text up to the chapter the user requests. No "knowledge bleed" from future arcs.
* **Dynamic Character Tracker (Planned):** Search for a character and see their status, powers, and allegiances *as of the current chapter*.

---

## ⚙️ How It Works: The Ephemeral OCR Pipeline

Processing thousands of webtoon panels through an AI Vision model is financially and legally unviable. Instead, this project uses an **Ephemeral OCR Pipeline**:

1. **Fetch:** A background worker temporarily downloads the chapter images from a source API (e.g., MangaDex) to a `/tmp` directory.
2. **Slice & Process:** The long vertical strips are sliced into digestible blocks. An OCR engine (like Tesseract) scans the panels and extracts raw text from the speech bubbles.
3. **Cleanse:** A script scrubs the raw OCR data, removing fragmented sound effects and stitching dialogue back together.
4. **Summarize:** The clean text file is sent to an LLM via API to generate a structured, factual summary.
5. **Destroy:** The raw images are immediately permanently deleted from the server. Only the generated text summary is saved to the database.

---

## 🛠️ Proposed Tech Stack
* **Backend Framework:** Ruby on Rails (MVC architecture for managing series metadata and background jobs)
* **Background Processing:** Sidekiq / Redis (for queuing the ephemeral downloads)
* **Text Extraction:** Tesseract OCR / manga-ocr
* **AI Standardization Layer:** Gemini / OpenAI API (for turning raw OCR into readable summaries)
* **Database:** PostgreSQL

---

## 🚀 Roadmap
- [ ] Initialize the backend application and database schema (Series, Chapters, Summaries).
- [ ] Build a prototype script to download a single chapter via MangaDex API.
- [ ] Implement the Image Slicer and OCR extraction script.
- [ ] Write the prompt engineering logic to pass OCR text to the LLM.
- [ ] Build the user-facing API/Frontend to request custom range summaries.

---

## 📝 Disclaimer
This project does not host, distribute, or store copyrighted images. Image processing is done entirely in memory/temporary storage for the sole purpose of text extraction and analysis, after which the files are immediately destroyed.
