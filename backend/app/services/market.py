from __future__ import annotations

from dataclasses import dataclass
import time

import pandas as pd
import numpy as np
import yfinance as yf

from .alpha_vantage import fetch_daily_series_1mo


# In-memory cache to reduce yfinance rate-limits in dev and repeated analyses.
# Keyed by normalized ticker. Values expire after TTL seconds.
_CACHE_TTL_SECONDS = 60 * 15
_cache: dict[str, tuple[float, "MarketResult"]] = {}


def _normalize_ticker(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    # yfinance expects BRK-B rather than BRK.B
    t = t.replace(".", "-")
    return t


def _cache_get(ticker: str) -> "MarketResult" | None:
    now = time.time()
    hit = _cache.get(ticker)
    if not hit:
        return None
    ts, val = hit
    if now - ts > _CACHE_TTL_SECONDS:
        _cache.pop(ticker, None)
        return None
    return val


def _cache_set(ticker: str, val: "MarketResult") -> None:
    _cache[ticker] = (time.time(), val)


def _download_with_fallbacks(ticker: str) -> pd.DataFrame:
    """Fetch OHLCV with retries and multiple time windows.

    yfinance can intermittently return empty frames due to rate limits or provider hiccups.
    We try progressively broader windows and retry a couple of times.
    """

    attempts: list[tuple[str, str]] = [
        ("1mo", "1d"),
        ("3mo", "1d"),
        ("6mo", "1d"),
        ("1y", "1d"),
    ]

    last_df: pd.DataFrame | None = None
    for period, interval in attempts:
        for _ in range(2):
            try:
                # A tiny delay helps avoid tight-loop rate limiting.
                time.sleep(0.25)
                df = yf.download(
                    ticker,
                    period=period,
                    interval=interval,
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
                last_df = df
                if df is not None and not df.empty and "Close" in df.columns:
                    return df
            except Exception:
                time.sleep(0.5)
                continue

    return last_df if last_df is not None else pd.DataFrame()


@dataclass
class MarketResult:
    price_series: list[dict]
    day_move_pct: float | None
    vol_20d: float | None
    move_zscore: float | None


@dataclass
class TickerMarketResult(MarketResult):
    ticker: str = ""


def _safe_float(x) -> float | None:
    try:
        if x is None:
            return None
        v = float(x)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    except Exception:
        return None


def fetch_market_context(primary_ticker: str | None) -> MarketResult:
    if not primary_ticker:
        return MarketResult(price_series=[], day_move_pct=None, vol_20d=None, move_zscore=None)

    t = _normalize_ticker(primary_ticker)
    cached = _cache_get(t)
    if cached is not None:
        return cached

    try:
        df = _download_with_fallbacks(t)
        if df is None or df.empty or "Close" not in df.columns:
            series_av = fetch_daily_series_1mo(t)
            res = MarketResult(price_series=series_av, day_move_pct=None, vol_20d=None, move_zscore=None)
            _cache_set(t, res)
            return res

        closes_all = df["Close"].dropna()
        closes_1m = closes_all.tail(32)
        closes_stats = closes_all.tail(60)

        series = [{"date": idx.date().isoformat(), "close": float(val)} for idx, val in closes_1m.items()]
        if not series:
            series_av = fetch_daily_series_1mo(t)
            res = MarketResult(price_series=series_av, day_move_pct=None, vol_20d=None, move_zscore=None)
            _cache_set(t, res)
            return res

        rets = closes_stats.pct_change().dropna()
        if rets.empty:
            res = MarketResult(price_series=series, day_move_pct=None, vol_20d=None, move_zscore=None)
            _cache_set(t, res)
            return res

        last_ret = rets.iloc[-1]
        day_move_pct = _safe_float(last_ret * 100.0)

        vol_20 = rets.tail(20).std(ddof=0)
        vol_20d = _safe_float(vol_20 * 100.0)

        z = None
        if vol_20 and vol_20 > 0:
            z = _safe_float(last_ret / vol_20)

        res = MarketResult(price_series=series, day_move_pct=day_move_pct, vol_20d=vol_20d, move_zscore=z)
        _cache_set(t, res)
        return res
    except Exception:
        series_av = fetch_daily_series_1mo(t)
        res = MarketResult(price_series=series_av, day_move_pct=None, vol_20d=None, move_zscore=None)
        _cache_set(t, res)
        return res


def fetch_markets_context(tickers: list[str]) -> list[TickerMarketResult]:
    out: list[TickerMarketResult] = []
    seen: set[str] = set()

    for t in tickers:
        nt = _normalize_ticker(t)
        if not nt or nt in seen:
            continue

        seen.add(nt)
        r = fetch_market_context(nt)
        out.append(
            TickerMarketResult(
                ticker=nt,
                price_series=r.price_series,
                day_move_pct=r.day_move_pct,
                vol_20d=r.vol_20d,
                move_zscore=r.move_zscore,
            )
        )

    return out
