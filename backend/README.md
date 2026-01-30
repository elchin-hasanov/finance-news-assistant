# Backend (FastAPI)

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Environment

Create `backend/.env` (optional):

```bash
CORS_ORIGINS=http://localhost:3000
HTTP_TIMEOUT_SECONDS=12
USER_AGENT=Mozilla/5.0 ...

# Optional: transformer sentiment (FinBERT). Off by default to avoid OOM on small hosts.
ENABLE_TRANSFORMER_SENTIMENT=0

# Used as fallback market data source when yfinance is rate-limited
ALPHAVANTAGE_API_KEY=...
```

### Market data

We try `yfinance` first and fall back to Alpha Vantage (if the key is set) for the 1‑month price series used by the UI.

## Test

```bash
pytest -q
```
