# De-hype Financial News (Monorepo)

Stack: Next.js 14 (App Router, TypeScript, Tailwind) + FastAPI (Python 3.11) + httpx + BeautifulSoup4 + newspaper3k fallback + yfinance + pandas + python-dotenv + uvicorn + pytest + zod + recharts.

## Structure

- `frontend/` Next.js UI
- `backend/` FastAPI API

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000

## Notes

- If an article blocks scraping (403/401/429 or paywall hints), the API responds with:
  - `{"error": {"code": "FETCH_BLOCKED", "message": "...", "hint": "Paste text instead."}}`
  The UI automatically switches to the “Paste text” tab.
- Market context uses `yfinance`. If it fails, market fields are returned as null/empty series and the UI shows a small notice.

## Testing

```bash
cd backend
source .venv/bin/activate
pytest -q
```
