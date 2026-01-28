from __future__ import annotations

from typing import Any

import httpx

from ..settings import get_settings


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _safe_get(d: dict[str, Any], *keys: str) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def fetch_daily_series_1mo(ticker: str) -> list[dict]:
    """Fetch ~1 month of daily close prices from Alpha Vantage.

    Returns a list of {date, close} sorted ascending by date.

    Notes:
    - Uses TIME_SERIES_DAILY_ADJUSTED which is widely available.
    - Alpha Vantage has rate limits; we rely on the caller's caching.
    """

    settings = get_settings()
    api_key = settings.alpha_vantage_api_key
    if not api_key:
        return []

    # Alpha Vantage prefers tickers like 'BRK.B' (dot), but accepts many.
    params = {
        # Use the non-premium endpoint to work with standard/free keys.
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "outputsize": "compact",
        "apikey": api_key,
    }

    try:
        with httpx.Client(timeout=settings.http_timeout_seconds, headers={"User-Agent": settings.user_agent}) as client:
            resp = client.get("https://www.alphavantage.co/query", params=params)
            resp.raise_for_status()
            payload = resp.json()

        # Handle throttling or errors.
        if not isinstance(payload, dict):
            return []
        if "Note" in payload or "Error Message" in payload or "Information" in payload:
            return []

        ts = _safe_get(payload, "Time Series (Daily)")
        if not isinstance(ts, dict) or not ts:
            return []

        # Collect closes; Alpha uses strings.
        points: list[tuple[str, float]] = []
        for date_str, row in ts.items():
            if not isinstance(row, dict):
                continue

            close_s = row.get("4. close")
            close = _to_float(close_s)
            if close is None:
                continue
            points.append((date_str, close))

        points.sort(key=lambda x: x[0])
        # Keep last ~32 trading days for "previous month".
        points = points[-32:]

        return [{"date": d, "close": c} for d, c in points]
    except Exception:
        return []


def fetch_daily_ohlc_1y(ticker: str) -> list[dict]:
    """Fetch up to ~1 year of daily OHLCV from Alpha Vantage.

    Returns a list of {date, open, high, low, close, volume} sorted ascending.

    This is used as a fallback when yfinance is rate-limited.
    """

    settings = get_settings()
    api_key = settings.alpha_vantage_api_key
    if not api_key:
        return []

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        # compact is ~100 trading days; let callers compute 52w-ish metrics when possible.
        # Users with a premium key can change this to "full" in settings later if desired.
        "outputsize": "compact",
        "apikey": api_key,
    }

    try:
        with httpx.Client(timeout=settings.http_timeout_seconds, headers={"User-Agent": settings.user_agent}) as client:
            resp = client.get("https://www.alphavantage.co/query", params=params)
            resp.raise_for_status()
            payload = resp.json()

        if not isinstance(payload, dict):
            return []
        if "Note" in payload or "Error Message" in payload or "Information" in payload:
            return []

        ts = _safe_get(payload, "Time Series (Daily)")
        if not isinstance(ts, dict) or not ts:
            return []

        points: list[dict] = []
        for date_str, row in ts.items():
            if not isinstance(row, dict):
                continue

            o = _to_float(row.get("1. open"))
            h = _to_float(row.get("2. high"))
            l = _to_float(row.get("3. low"))
            c = _to_float(row.get("4. close"))
            v = _to_float(row.get("5. volume"))
            if c is None:
                continue

            points.append(
                {
                    "date": date_str,
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": v,
                }
            )

        points.sort(key=lambda x: x["date"])
        return points
    except Exception:
        return []


def fetch_daily_series_compact(ticker: str) -> list[dict]:
    """Alias for fetching a compact daily close-only series.

    Kept for readability at call sites where we're fetching broad market proxies
    (SPY, sector ETFs) and only need close-to-close returns.
    """

    return fetch_daily_series_1mo(ticker)
