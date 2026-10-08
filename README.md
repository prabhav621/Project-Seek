# ⚡ Project Seek: The Personal Strategic Operating System

> **A Late-Binding Knowledge Engine & Executive Sparring Partner powered by Multi-Cloud LLMs.**  
> Transforming passive bookmarks into dense, actionable strategic primitives called **Neutral Bricks**.

---

## 📌 The Problem: The "Bookmark Cemetery"

Founders, builders, and knowledge workers save hundreds of high-signal essays, technical breakdowns, and videos. 

Yet, **95% of saved bookmarks are never re-read**, and the 5% that are get lost in unstructured notes. Existing "Second Brains" (Notion, Obsidian, Readwise) act as passive digital hoarding vaults—they store text, but they don't challenge your thinking, synthesize your worldview, or push back on your assumptions.

**Project Seek** inverts this paradigm. It is an autonomous, opinionated **Personal Strategic Operating System** built on Telegram that transforms every link or document you consume into operational intelligence.

---

## 🏗️ Core Architecture: The ELT Paradigm

Traditional knowledge systems use **ETL** (extract, transform with an opinionated prompt at ingestion, and load). If your prompt is flawed or your goal shifts, your data is permanently distorted.

Project Seek uses **ELT (Late-Binding Lenses)**:

```
                  ┌──────────────────────────────────────────────┐
                  │            OMNIVORE INGESTION                │
                  │  (Web Scrapes, Playlists, PDFs, Documents)   │
                  └──────────────────────┬───────────────────────┘
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │            NEUTRAL BRICK SYNTHESIS           │
                  │   Ruthlessly strips rhetorical fluff into:   │
                  │   • Core Thesis • Mechanics • Pointers       │
                  └──────────────────────┬───────────────────────┘
                                         ▼
                          ┌──────────────────────────────┐
                          │   PGVECTOR KNOWLEDGE VAULT   │
                          │   (500+ Embedded Bricks)     │
                          └──────────────┬───────────────┘
                                         ▼
      ┌──────────────────────────────────┴──────────────────────────────────┐
      ▼                                  ▼                                  ▼
┌───────────────┐              ┌──────────────────┐               ┌──────────────────┐
│ LATE-BINDING  │              │   ASK-THE-BRICK  │               │  THE LIBRARIAN   │
│ SOVEREIGN     │              │    CONTEXTUAL    │               │   REVERSE-RAG    │
│ LENSES        │              │     SPARRING     │               │   SYNTHESIS      │
│ (1-Tap Buttons)              │ (Swipe-to-Reply) │               │ (Unreplied Text) │
└───────────────┘              └──────────────────┘               └──────────────────┘
```

1. **Neutral Bricks (Objective Storage):**
   When content is ingested, the engine strips introductory filler, analogies, and rhetorical build-up. It extracts an immutable, objective schema:
   * **Core Thesis:** 1–2 dense sentences capturing the non-obvious insight.
   * **Key Mechanics:** How and why it functions under the hood.
   * **Critical Pointers:** Actionable, tactical rules of engagement.

2. **Late-Binding Sovereign Lenses:**
   Instead of permanently coloring the brick during ingestion, analytical models are bound **on demand** via Telegram inline buttons:
   * 🏗️ **Architect:** System design, technical debt, failure points, scalability.
   * 📈 **Growth:** Viral loops, distribution advantages, unit economics, CAC.
   * 🛡️ **Red Team:** Fatal flaws, counter-strategies, competitive threats.
   * ✅ **Validator:** Market demand, willingness to pay, customer traction.
   * ⚛️ **First Principles:** Foundational physics, core mechanics, baseline truths.

3. **Contextual Sparring (Ask-the-Brick):**
   Swipe right on any Brick or Daily Forge item to debate it. The system routes your conversation into the `PRO` reasoning tier, adopting the voice of a sharp CPO co-founder.

4. **The Librarian (Reverse-RAG):**
   Send any unreplied thought or question to query your entire vault. The Librarian performs vector similarity search across your indexed Bricks and synthesizes a direct, cross-domain answer.

5. **The Daily Forge:**
   Delivered every morning at 8:00 AM IST:
   * **2 Quick Katas:** High-leverage tactical problems to stress-test your thinking.
   * **3 Curated Neutral Bricks:** Interleaved via entropy and interest drift with 1-tap Lens buttons.
   * **The Philosopher's Stone:** Lean aphorism (quote + author).
   * **"The Contrarian Says...":** Counter-intuitive strategic provocation.

---

## 🧠 Sovereign 3-Tier Multi-Cloud Router

Project Seek operates on a zero-downtime, tiered model cascade that prevents quota exhaustion, handles transient network drops, and ensures you never get trapped by single-provider rate limits:

| Tier | Primary Workloads | Cascade Sequence | Timeout |
| :--- | :--- | :--- | :--- |
| **`PRO`** | Lenses, Librarian Reverse-RAG, Contextual Sparring, Aphorisms | NVIDIA NIM (`Nemotron 550B`) $\rightarrow$ OpenRouter Free Sweeper ($\ge$70B) $\rightarrow$ DeepSeek R1 / Claude Sonnet 4.5 $\rightarrow$ Cloudflare Workers AI (`Llama 3.3 70B FP8`) | 25s–45s |
| **`FLASH`** | Fast User Chat, Quick Katas, /strategize URL Ingestion | Google Gemini (`3.5 Flash Lite`, 500 RPD) $\rightarrow$ Gemini (`3.1 Flash Lite`) $\rightarrow$ OpenRouter Free Flash ($\le$70B) $\rightarrow$ Cloudflare (`Llama 3.1 8B`) | 45s–60s |
| **`LITE`** | Bulk Ingestion, Embeddings, Domain Tagging, Transcript Summaries | Gemini Flash Lite Bulk Slots $\rightarrow$ OpenRouter Free Lite Sweeper $\rightarrow$ Cloudflare Workers AI (`8B Plain-Text`) | 30s–60s |

* **Zero-Spike Safety:** Built-in HTTP 402 circuit breakers immediately detect credit exhaustion and fall back to local/edge models.
* **Resilient Parsing:** Replaced fragile JSON structures with labeled plain-text streaming to eliminate provider-level tokenizer crashes.

---

## 🛠️ Tech Stack

* **Language:** Python 3.12+ (AsyncIO native)
* **Delivery:** `python-telegram-bot` with custom Inline Keyboard routers
* **Orchestration & LLM Cascades:** `litellm` + custom dynamic provider sweepers
* **Database & Vector Search:** PostgreSQL with `pgvector` / SQLite `aiosqlite`
* **Scraping & Ingestion:** `r.jina.ai`, `crawl4ai`, `yt-dlp`, PyPDF2
* **Scheduling:** `APScheduler` (Asia/Kolkata timezone)

---

## 🚀 Quickstart

### 1. Clone & Configure
```bash
git clone https://github.com/prabhav621/Project-Seek.git
cd Project-Seek
cp .env.example .env
```

Edit `.env` with your API keys:
* `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`
* `DATABASE_URL` (PostgreSQL with pgvector or SQLite)
* `GEMINI_API_KEY` (Free tier from Google AI Studio)
* Optional multi-cloud keys: `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `CLOUDFLARE_API_KEY`

### 2. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Initialize Database Migrations
```bash
alembic upgrade head
```

### 4. Start the Engine
```bash
# Launch interactive bot in tmux or terminal
python src/delivery/telegram_bot.py
```

---

## 📱 How to Interact in Telegram

* **Ingest a Link:** Send any article, blog post, or YouTube link directly into the chat.
* **Instant Brick:** Type `/strategize https://example.com/essay` for real-time fluff-stripping.
* **Ask the Librarian:** Send any raw question (*"What do my notes say about distribution vs product?"*).
* **Spar with a Brick:** Reply to any message to drill down or challenge assumptions.
* **Apply a Lens:** Tap any button (`[Architect]`, `[Growth]`, `[Red Team]`, etc.) below a Brick, or use `/lens`.
* **Lock Active Sprint Focus:** `/focus Landing our first 5 pilot contracts` (maps all queries to this sprint goal for 15 minutes).
* **Reset Focus:** `/unfocus`.

---

## 📄 License

MIT License. Built for sovereign builders who believe their accumulated knowledge should actively work for them.
