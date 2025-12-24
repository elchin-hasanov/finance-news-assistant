# De-hype Financial News (Monorepo)

**De-hype Financial News** is a full-stack app that turns noisy market headlines into a structured, factual brief. Paste a **news URL** (or the article **text**) to extract claims, identify companies, measure hype language, and view a **1‑month stock chart + % change** for companies that can be resolved to public tickers.

This repo is designed to be both a practical tool and a clean engineering showcase: deterministic outputs where possible, defensive scraping, typed API models, and reproducible tests.

---

## ✨ What it does

- **URL or text input**
  - URL mode fetches HTML with realistic headers and robust error handling.
  - Text mode bypasses paywalls and anti-bot pages.
- **Article body extraction (anti-boilerplate)**
  - Prefers **JSON-LD `articleBody`** when available.
  - Falls back to `<article>` paragraphs and paragraph-density heuristics.
  - Filters nav/footer/menu style boilerplate.
- **Entities & companies**
  - Extracts likely companies from the text.
  - Resolves company → ticker using an **offline S&P500 CSV dataset** plus normalization.
  - Supports additional aliases/abbreviations (e.g., “Amazon” → `AMZN`).
  - Private AI org mentions like **OpenAI / Anthropic / Claude / Cursor** are mapped to **public proxies** for market charts (see “Market data”).
- **Claim extraction**
  - Pulls short factual claims with supporting sentences and captured numeric values.
- **Hype score**
  - Detects hype/marketing language and outputs a simple 0–100 score.
- **Facts-only rewrite**
  - Produces a concise rewrite focused on factual statements.

---

## 🧰 Tech stack

### Frontend (`frontend/`)
- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS**
- **Zod** (input validation)
- **Recharts** (time-series chart)

### Backend (`backend/`)
- **FastAPI** (Python)
- **Pydantic** models for a typed API contract
- **httpx** for fetching pages
- **BeautifulSoup4** for extraction
- **newspaper3k** fallback strategy
- **yfinance** (primary market data source)
- **Alpha Vantage** fallback (optional; via API key)
- **pandas** utilities where needed
- **python-dotenv** for local env
- **uvicorn** server
- **pytest** test suite

---

## 📁 Repository structure

- `frontend/`  Next.js UI
- `backend/`  FastAPI API

---

## 🔌 API contract (backend)

Base URL: `http://localhost:8000`

### `GET /health`
Returns:

```json
{ "ok": true }
```

### `POST /analyze`
Request body (`AnalyzeRequest`):

```json
{ "url": "https://example.com/article" }
```

or

```json
{ "text": "<paste article text>" }
```

Response (`AnalyzeResponse`) includes:
- `source`: URL metadata (best-effort)
- `content`: `raw_text` and `extracted_text`
- `entities`: detected companies/tickers + inferred mappings
- `claims`: extracted claims with evidence sentences
- `hype`: score + word counts
- `facts_only_summary`: deterministic rewrite
- `market` + `markets`: time series and basic movement metrics (when available)

Error format (`ErrorEnvelope`):

```json
{ "error": { "code": "...", "message": "...", "hint": "..." } }
```

---

## 📈 Market data behavior

Market charts show **the last ~1 month of daily closes** and **% change**.

The backend:
1. Tries **yfinance** first (with normalization + caching/retry logic).
2. Falls back to **Alpha Vantage** if `ALPHAVANTAGE_API_KEY` is provided.

Why the private-AI mappings exist:
- Companies like **OpenAI / Anthropic / Cursor** aren’t publicly traded. They don’t have tickers.
- For a consistent UX, the app maps these mentions to **public proxies** (e.g., market exposure partners) so the UI can still render a chart.

---

## 🧪 Scraping reliability notes

- If a site blocks scraping (e.g., 401/403/429 or paywall hints), the backend returns:

```json
{
  "error": {
    "code": "FETCH_BLOCKED",
    "message": "...",
    "hint": "Paste text instead."
  }
}
```

The UI is designed to fall back to the text workflow.

---

## 🚀 Run locally

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# optional (see below)
cp .env.example .env

uvicorn app.main:app --reload --port 8000
```

Environment variables (optional):

- `CORS_ORIGINS` (default: `http://localhost:3000`)
- `HTTP_TIMEOUT_SECONDS`
- `USER_AGENT`
- `ALPHAVANTAGE_API_KEY` (recommended for reliability)

### Frontend (Next.js)

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`.

---

## ✅ Tests

Backend tests (recommended before pushing changes):

```bash
cd backend
source .venv/bin/activate
pytest -q
```

---

## 🔍 Engineering highlights (for recruiters)

- **Typed API contract** via Pydantic models (`AnalyzeRequest`, `AnalyzeResponse`, `ErrorEnvelope`).
- **Defensive extraction pipeline**: JSON-LD first, paragraph fallbacks, boilerplate filtering, and regression tests.
- **Provider fallback** for market data to reduce third-party flakiness.
- **Offline S&P500 mapping** for deterministic company → ticker resolution.
- **Separation of concerns**: `services/` layer for extraction, entities, hype, claims, and market logic.

---

## 🗺️ Roadmap / ideas

- Improve company/entity precision (stopwords + lightweight NER).
- Add persistence (store analyses + caching across restarts).
- Add deployment presets (Docker + CI + Vercel/Render).

