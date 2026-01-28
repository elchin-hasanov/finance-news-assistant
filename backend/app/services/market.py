from __future__ import annotations

from dataclasses import dataclass
import time

import pandas as pd
import numpy as np
import yfinance as yf


from .alpha_vantage import fetch_daily_ohlc_1y, fetch_daily_series_1mo, fetch_daily_series_compact


# In-memory cache to reduce yfinance rate-limits in dev and repeated analyses.
# Keyed by normalized ticker. Values expire after TTL seconds.
_CACHE_TTL_SECONDS = 60 * 60 * 24  # 24 hours for production stability
_cache: dict[str, tuple[float, "MarketResult"]] = {}

# Cache for ticker info (sector, industry, etc.)
_INFO_CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # 1 week
_info_cache: dict[str, tuple[float, dict]] = {}

# In practice, `yf.Ticker(...).info` is the most fragile call (often blocked / slow).
# Use it only when explicitly needed.
_DEFAULT_USE_YF_INFO = False

# Cache for benchmark series (ETFs used for SPY/sector/industry) to avoid repeated downloads.
_BENCH_CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 hours
_bench_cache: dict[str, tuple[float, float | None]] = {}


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


def _bench_cache_get(key: str) -> float | None:
    now = time.time()
    hit = _bench_cache.get(key)
    if not hit:
        return None
    ts, val = hit
    if now - ts > _BENCH_CACHE_TTL_SECONDS:
        _bench_cache.pop(key, None)
        return None
    return val


def _bench_cache_set(key: str, val: float | None) -> None:
    _bench_cache[key] = (time.time(), val)


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
            except Exception as e:
                # Don't hammer Yahoo; fail fast and let upstream fallbacks take over.
                # yfinance raises YFRateLimitError in some versions; in others we just get a message.
                msg = str(e).lower()
                if (
                    "yfratelimiterror" in msg
                    or "rate limit" in msg
                    or "ratelimit" in msg
                    or "too many requests" in msg
                    or "too many request" in msg
                    or "http 429" in msg
                ):
                    return pd.DataFrame()
                time.sleep(0.5)
                continue

    return last_df if last_df is not None else pd.DataFrame()


def _df_from_alpha_vantage_ohlc(points: list[dict]) -> pd.DataFrame:
    """Convert Alpha Vantage OHLC list into a yfinance-like DataFrame."""
    if not points:
        return pd.DataFrame()

    try:
        df = pd.DataFrame(points)
        if df.empty:
            return pd.DataFrame()

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).set_index("date").sort_index()

        # Alpha Vantage keys are already lowercase (open/high/low/close/volume)
        # from our parser; convert to yfinance-style capitalized columns.
        mapping = {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
        for src, dst in mapping.items():
            if src in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")

        # Only keep canonical columns.
        keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
        out = df[keep].copy()
        out = out.dropna(subset=["Close"])
        return out
    except Exception:
        return pd.DataFrame()


def _coerce_ohlcv_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize an OHLCV dataframe so computations are stable.

    Ensures:
    - Datetime index
    - Sorted index
    - No rows without Close
    """
    try:
        if df is None or df.empty:
            return pd.DataFrame()
        out = df.copy()

        # yfinance can return a MultiIndex columns frame (e.g., columns like ('Close','XLK')).
        # Flatten it to the standard single-level columns we expect.
        if isinstance(out.columns, pd.MultiIndex):
            # Prefer the first level (Open/High/Low/Close/Volume/etc.).
            out.columns = [str(c[0]) for c in out.columns]
        if not isinstance(out.index, pd.DatetimeIndex):
            out.index = pd.to_datetime(out.index, errors="coerce")
        out = out.dropna(subset=["Close"]).sort_index()
        return out
    except Exception:
        return pd.DataFrame()


def _winsorize_series(s: pd.Series, lo_q: float = 0.01, hi_q: float = 0.99) -> pd.Series:
    """Clip extreme outliers which frequently appear in scraped/free market data.

    This prevents a single erroneous spike from ruining 52w calculations.
    """
    try:
        s = s.dropna()
        if s.empty:
            return s
        lo = s.quantile(lo_q)
        hi = s.quantile(hi_q)
        if pd.isna(lo) or pd.isna(hi) or lo <= 0 or hi <= 0 or lo >= hi:
            return s
        return s.clip(lower=float(lo), upper=float(hi))
    except Exception:
        return s


@dataclass
class MarketResult:
    price_series: list[dict]
    day_move_pct: float | None
    vol_20d: float | None
    move_zscore: float | None
    # Enhanced metrics
    data_source: str | None = None
    last_close_date: str | None = None
    price_series_days: int | None = None
    current_price: float | None = None
    week_52_high: float | None = None
    week_52_low: float | None = None
    pct_from_52w_high: float | None = None
    pct_from_52w_low: float | None = None
    market_cap: float | None = None
    sector: str | None = None
    industry: str | None = None
    beta: float | None = None
    pe_ratio: float | None = None
    sector_performance_today: float | None = None
    sp500_performance_today: float | None = None
    relative_strength: float | None = None
    industry_benchmark: str | None = None
    industry_performance_today: float | None = None
    relative_strength_vs_industry: float | None = None
    peer_group_label: str | None = None
    peer_group_size: int | None = None
    peer_avg_move_today: float | None = None
    relative_strength_vs_peers: float | None = None
    rsi_14d: float | None = None
    ma_50d: float | None = None
    ma_200d: float | None = None
    unusual_volume: bool = False
    near_52w_high: bool = False
    volatility_regime: str | None = None
    average_volume_20d: float | None = None
    current_volume: float | None = None


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


_BAD_PROFILE_VALUES = {
    "inc",
    "inc.",
    "incorporated",
    "corp",
    "corp.",
    "corporation",
    "ltd",
    "ltd.",
    "limited",
    "plc",
    "co",
    "co.",
    "company",
    "group",
    "holdings",
    "holding",
}


def _clean_profile_str(s: str | None) -> str | None:
    """Normalize/validate free-text profile fields like sector/industry.

    Some upstream extraction paths can accidentally pass corp suffixes (e.g. "Inc.")
    which then breaks our sector→ETF mapping.
    """
    if not s:
        return None
    v = str(s).strip()
    if not v:
        return None
    if v.lower() in _BAD_PROFILE_VALUES:
        return None
    # Single short token is almost never a valid sector/industry.
    if len(v.split()) == 1 and len(v) <= 4:
        return None
    return v


def _get_ticker_info(ticker: str, *, allow_network_profile: bool = _DEFAULT_USE_YF_INFO) -> dict:
    """Fetch and cache ticker info (sector, industry, market cap, etc.)

    Notes:
    - `yfinance.Ticker(...).info` is frequently rate limited or returns partial data.
    - For production stability, we default to *not* calling it, and instead rely on
      chart-based metrics + benchmark ETFs which are much more reliable.
    """
    now = time.time()
    hit = _info_cache.get(ticker)
    if hit:
        ts, val = hit
        if now - ts <= _INFO_CACHE_TTL_SECONDS:
            return val

    if not allow_network_profile:
        return {}

    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info or {}
        _info_cache[ticker] = (now, info)
        return info
    except Exception:
        return {}


def _calculate_rsi(prices: pd.Series, period: int = 14) -> float | None:
    """Calculate Relative Strength Index"""
    try:
        if len(prices) < period + 1:
            return None
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return _safe_float(rsi.iloc[-1])
    except Exception:
        return None


def _fetch_sp500_performance() -> float | None:
    """Fetch S&P 500 daily performance"""
    cached = _bench_cache_get("SPY")
    if cached is not None:
        return cached
    try:
        spy = yf.download("SPY", period="5d", interval="1d", auto_adjust=True, progress=False, threads=False)
        if spy is not None and not spy.empty and "Close" in spy.columns and len(spy) >= 2:
            pct_change = ((spy["Close"].iloc[-1] - spy["Close"].iloc[-2]) / spy["Close"].iloc[-2]) * 100
            val = _safe_float(pct_change)
            _bench_cache_set("SPY", val)
            return val
    except Exception:
        # Fall through to Alpha Vantage.
        pass

    # Alpha Vantage fallback (close-only)
    series = fetch_daily_series_compact("SPY")
    if len(series) >= 2:
        prev = series[-2].get("close")
        cur = series[-1].get("close")
        if prev and cur:
            val = _safe_float(((float(cur) - float(prev)) / float(prev)) * 100)
            _bench_cache_set("SPY", val)
            return val
    return None


def _fetch_sector_performance(sector: str | None) -> float | None:
    """Fetch sector ETF performance as proxy for sector movement"""
    if not sector:
        return None
    
    # Map sectors to their representative ETFs.
    # Note: sector naming differs by data source; we normalize common variants.
    sector_etfs = {
        "Technology": "XLK",
        "Health Care": "XLV",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Financial Services": "XLF",
        "Consumer Cyclical": "XLY",
        "Consumer Defensive": "XLP",
        "Consumer Discretionary": "XLY",
        "Consumer Staples": "XLP",
        "Industrials": "XLI",
        "Energy": "XLE",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Basic Materials": "XLB",
        "Materials": "XLB",
        "Communication Services": "XLC",
        "Communication": "XLC",
    }
    
    etf = sector_etfs.get(sector)
    if not etf:
        return None

    cached = _bench_cache_get(etf)
    if cached is not None:
        return cached
    
    try:
        data = _download_with_fallbacks(etf)
        data = _coerce_ohlcv_df(data)
        if data is not None and not data.empty and "Close" in data.columns and len(data) >= 2:
            pct_change = ((data["Close"].iloc[-1] - data["Close"].iloc[-2]) / data["Close"].iloc[-2]) * 100
            val = _safe_float(pct_change)
            _bench_cache_set(etf, val)
            return val
    except Exception:
        # Fall through to Alpha Vantage.
        pass

    # Alpha Vantage fallback (close-only)
    series = fetch_daily_series_compact(etf)
    if len(series) >= 2:
        prev = series[-2].get("close")
        cur = series[-1].get("close")
        if prev and cur:
            val = _safe_float(((float(cur) - float(prev)) / float(prev)) * 100)
            _bench_cache_set(etf, val)
            return val
    return None


def _industry_benchmark_etf(industry: str | None, sector: str | None) -> tuple[str | None, str | None]:
    """Best-effort mapping from (industry, sector) -> (benchmark label, ETF ticker).

    This stays conservative: prefer high-liquidity, common industry ETFs.
    Returns (label, etf) or (None, None).
    """
    if not industry and not sector:
        return (None, None)

    ind = (industry or "").lower()
    sec = (sector or "").lower()

    # Semiconductors
    if any(k in ind for k in ["semiconductor", "semi", "chip"]):
        return ("Semiconductors (SOXX)", "SOXX")

    # Consumer electronics (closest liquid proxy)
    if any(k in ind for k in ["consumer electronics", "iphone", "smartphone", "wearable"]):
        return ("Consumer Tech (VGT)", "VGT")

    # Software / cloud
    if any(k in ind for k in ["software", "application", "saas", "cloud"]):
        return ("Software (IGV)", "IGV")

    # Internet retail
    if any(k in ind for k in ["internet retail", "e-commerce", "ecommerce", "online retail"]):
        return ("Online Retail (IBUY)", "IBUY")

    # Internet / e-commerce
    if any(k in ind for k in ["internet", "e-commerce", "online retail", "digital"]):
        return ("Internet (FDN)", "FDN")

    # Cybersecurity
    if any(k in ind for k in ["cyber", "security"]):
        return ("Cybersecurity (HACK)", "HACK")

    # Biotech
    if any(k in ind for k in ["biotech", "biotechnology"]):
        return ("Biotech (IBB)", "IBB")

    # Retail (broad)
    if any(k in ind for k in ["retail"]):
        return ("Retail (XRT)", "XRT")

    # Banks
    if any(k in ind for k in ["bank", "banks"]):
        return ("Banks (KBE)", "KBE")

    # Energy exploration/production
    if any(k in ind for k in ["oil", "gas", "exploration", "drilling", "energy equipment"]):
        return ("Oil & Gas (XOP)", "XOP")

    # If we can't confidently map industry, fall back to sector-level ETF label.
    if sec:
        return (None, None)

    return (None, None)


def _fetch_etf_daily_move(etf: str | None) -> float | None:
    if not etf:
        return None
    etf = _normalize_ticker(etf)
    cached = _bench_cache_get(etf)
    if cached is not None:
        return cached

    try:
        data = yf.download(etf, period="5d", interval="1d", auto_adjust=True, progress=False, threads=False)
        if data is not None and not data.empty and "Close" in data.columns and len(data) >= 2:
            pct_change = ((data["Close"].iloc[-1] - data["Close"].iloc[-2]) / data["Close"].iloc[-2]) * 100
            val = _safe_float(pct_change)
            _bench_cache_set(etf, val)
            return val
    except Exception:
        pass

    series = fetch_daily_series_compact(etf)
    if len(series) >= 2:
        prev = series[-2].get("close")
        cur = series[-1].get("close")
        if prev and cur:
            val = _safe_float(((float(cur) - float(prev)) / float(prev)) * 100)
            _bench_cache_set(etf, val)
            return val
    return None


def _peer_benchmark_for_ticker(
    primary_ticker: str,
    sector: str | None,
    industry: str | None,
    max_peers: int = 12,
) -> tuple[str | None, int | None, float | None]:
    """Compute a best-effort peer average daily move.

    Strategy:
    - Pull a candidate universe from yfinance screener endpoints indirectly isn't available.
    - Instead: use a deterministic offline universe: S&P 500 constituents + yfinance sector/industry info.
    - Pick up to max_peers peers by descending market cap where info matches.

    Returns (label, peer_count, avg_move_today).
    """
    try:
        # Build a candidate pool from S&P 500 tickers (offline).
        from .sp500 import load_sp500

        universe = [c.ticker for c in load_sp500()]
        # Avoid huge overhead: cap scanned universe.
        universe = universe[:500]

        target_sector = (sector or "").strip().lower()
        target_industry = (industry or "").strip().lower()

        scored: list[tuple[float, str]] = []
        for t in universe:
            if t == primary_ticker:
                continue
            # Be conservative: peer selection requires profile data, which is often unavailable in production.
            # Only attempt it if info calls are enabled.
            info = _get_ticker_info(_normalize_ticker(t))
            sec = str(info.get("sector") or "").strip().lower()
            ind = str(info.get("industry") or "").strip().lower()

            # Prefer industry match; fall back to sector match.
            if target_industry and ind and ind == target_industry:
                cap = _safe_float(info.get("marketCap")) or 0.0
                scored.append((cap, t))
            elif (not target_industry or not ind) and target_sector and sec and sec == target_sector:
                cap = _safe_float(info.get("marketCap")) or 0.0
                scored.append((cap, t))

        if not scored:
            return (None, None, None)

        scored.sort(reverse=True, key=lambda x: x[0])
        peers = [t for _, t in scored[:max_peers]]
        if not peers:
            return (None, None, None)

        moves: list[float] = []
        for pt in peers:
            r = fetch_market_context(pt)
            if r.day_move_pct is not None:
                moves.append(float(r.day_move_pct))

        if not moves:
            return (None, len(peers), None)

        avg = float(np.mean(moves))
        label = "Industry peers" if target_industry else "Sector peers"
        return (label, len(peers), _safe_float(avg))
    except Exception:
        return (None, None, None)


def fetch_market_context(primary_ticker: str | None) -> MarketResult:
    if not primary_ticker:
        return MarketResult(
            price_series=[], day_move_pct=None, vol_20d=None, move_zscore=None,
            data_source=None, last_close_date=None, price_series_days=None,
            week_52_high=None, week_52_low=None, pct_from_52w_high=None, pct_from_52w_low=None,
            market_cap=None, sector=None, industry=None, beta=None, pe_ratio=None,
            sector_performance_today=None, sp500_performance_today=None, relative_strength=None,
            industry_benchmark=None, industry_performance_today=None, relative_strength_vs_industry=None,
            peer_group_label=None, peer_group_size=None, peer_avg_move_today=None, relative_strength_vs_peers=None,
            rsi_14d=None, ma_50d=None, ma_200d=None, unusual_volume=False, near_52w_high=False,
            volatility_regime=None, average_volume_20d=None, current_volume=None
        )

    t = _normalize_ticker(primary_ticker)

    cached = _cache_get(t)
    if cached is not None:
        return cached

    # Fetch ticker info for fundamentals (best-effort).
    # Default is conservative (disabled) for production stability; chart-based metrics still work.
    info = _get_ticker_info(t)
    market_cap = _safe_float(info.get("marketCap"))
    sector = _clean_profile_str(info.get("sector"))
    industry = _clean_profile_str(info.get("industry"))

    # Offline fallback: for S&P 500 names we can fill sector/industry without any network calls.
    if not sector or not industry:
        try:
            from .sp500 import lookup_sp500_profile

            sec2, ind2 = lookup_sp500_profile(t)
            sector = sector or _clean_profile_str(sec2)
            industry = industry or _clean_profile_str(ind2)
        except Exception:
            pass

    beta = _safe_float(info.get("beta"))
    pe_ratio = _safe_float(info.get("trailingPE"))

    # Use an explicit 1y daily window to make 52w/MA metrics accurate and predictable.
    df = pd.DataFrame()
    data_source: str | None = None
    try:
        df = yf.download(t, period="1y", interval="1d", auto_adjust=True, progress=False, threads=False)
        df = _coerce_ohlcv_df(df)
        if df is not None and not df.empty and "Close" in df.columns:
            data_source = "yfinance"
    except Exception:
        df = pd.DataFrame()

    # If yfinance is empty (or rate-limited), fall back to Alpha Vantage OHLC.
    if df is None or df.empty or "Close" not in df.columns:
        try:
            av_points = fetch_daily_ohlc_1y(t)
            df = _df_from_alpha_vantage_ohlc(av_points)
            df = _coerce_ohlcv_df(df)
            if df is not None and not df.empty and "Close" in df.columns:
                data_source = "alpha_vantage"
        except Exception:
            df = pd.DataFrame()

    # If still empty, return what we can (maybe Alpha Vantage close-only series).
    if df is None or df.empty or "Close" not in df.columns:
        series_av = fetch_daily_series_1mo(t)
        res = MarketResult(
            price_series=series_av,
            day_move_pct=None,
            vol_20d=None,
            move_zscore=None,
            data_source="alpha_vantage" if series_av else None,
            last_close_date=series_av[-1]["date"] if series_av else None,
            price_series_days=len(series_av) if series_av else 0,
            current_price=series_av[-1]["close"] if series_av else None,
            market_cap=market_cap,
            sector=sector,
            industry=industry,
            beta=beta,
            pe_ratio=pe_ratio,
            week_52_high=None,
            week_52_low=None,
            pct_from_52w_high=None,
            pct_from_52w_low=None,
            sector_performance_today=None,
            sp500_performance_today=None,
            relative_strength=None,
            rsi_14d=None,
            ma_50d=None,
            ma_200d=None,
            unusual_volume=False,
            near_52w_high=False,
            volatility_regime=None,
            average_volume_20d=None,
            current_volume=None,
        )
        _cache_set(t, res)
        return res

    closes_all = _winsorize_series(df["Close"].dropna())
    closes_1m = closes_all.tail(32)
    closes_stats = closes_all.tail(60)

    series = [{"date": idx.date().isoformat(), "close": float(val)} for idx, val in closes_1m.items()]
    if not series:
        series_av = fetch_daily_series_1mo(t)
        res = MarketResult(
                price_series=series_av, day_move_pct=None, vol_20d=None, move_zscore=None,
                data_source="alpha_vantage" if series_av else data_source,
                last_close_date=series_av[-1]["date"] if series_av else None,
                price_series_days=len(series_av) if series_av else 0,
                market_cap=market_cap, sector=sector, industry=industry, beta=beta, pe_ratio=pe_ratio,
                week_52_high=None, week_52_low=None, pct_from_52w_high=None, pct_from_52w_low=None,
                sector_performance_today=None, sp500_performance_today=None, relative_strength=None,
                rsi_14d=None, ma_50d=None, ma_200d=None, unusual_volume=False, near_52w_high=False,
                volatility_regime=None, average_volume_20d=None, current_volume=None
            )
        _cache_set(t, res)
        return res

    # Basic metrics
    rets = closes_stats.pct_change().dropna()
    if rets.empty:
        res = MarketResult(
                price_series=series, day_move_pct=None, vol_20d=None, move_zscore=None,
                data_source=data_source,
                last_close_date=series[-1]["date"] if series else None,
                price_series_days=len(series) if series else 0,
                market_cap=market_cap, sector=sector, industry=industry, beta=beta, pe_ratio=pe_ratio,
                week_52_high=None, week_52_low=None, pct_from_52w_high=None, pct_from_52w_low=None,
                sector_performance_today=None, sp500_performance_today=None, relative_strength=None,
                rsi_14d=None, ma_50d=None, ma_200d=None, unusual_volume=False, near_52w_high=False,
                volatility_regime=None, average_volume_20d=None, current_volume=None
            )
        _cache_set(t, res)
        return res

    # "Today" move: use latest two trading closes in the dataset.
    day_move_pct = None
    try:
        if len(closes_all) >= 2:
            prev_close = float(closes_all.iloc[-2])
            last_close = float(closes_all.iloc[-1])
            if prev_close != 0:
                day_move_pct = _safe_float(((last_close - prev_close) / prev_close) * 100.0)
    except Exception:
        day_move_pct = None

    vol_20 = rets.tail(20).std(ddof=0)
    vol_20d = _safe_float(vol_20 * 100.0)

    z = None
    if vol_20 and vol_20 > 0:
        try:
            last_ret = float(rets.iloc[-1])
            z = _safe_float(last_ret / float(vol_20))
        except Exception:
            z = None

        # 52-week high/low
    closes_252 = closes_all.tail(252)  # ~1 year of trading days
    week_52_high = _safe_float(closes_252.max()) if len(closes_252) > 0 else None
    week_52_low = _safe_float(closes_252.min()) if len(closes_252) > 0 else None
    current_price = _safe_float(closes_all.iloc[-1])
        
    pct_from_52w_high = None
    pct_from_52w_low = None
    near_52w_high = False
        
    if current_price and week_52_high:
        pct_from_52w_high = _safe_float(((current_price - week_52_high) / week_52_high) * 100)
        if pct_from_52w_high and pct_from_52w_high >= -5:  # Within 5% of 52w high
            near_52w_high = True
        
    if current_price and week_52_low:
        pct_from_52w_low = _safe_float(((current_price - week_52_low) / week_52_low) * 100)

    # Moving averages
    ma_50d = _safe_float(closes_all.tail(50).mean()) if len(closes_all) >= 50 else None
    ma_200d = _safe_float(closes_all.tail(200).mean()) if len(closes_all) >= 200 else None

    # RSI
    rsi_14d = _calculate_rsi(closes_all)

    # Volume analysis
    unusual_volume = False
    average_volume_20d = None
    current_volume = None
        
    if "Volume" in df.columns:
        volumes = df["Volume"].dropna()
        if len(volumes) >= 20:
            avg_vol = volumes.tail(20).mean()
            curr_vol = volumes.iloc[-1]
            average_volume_20d = _safe_float(avg_vol)
            current_volume = _safe_float(curr_vol)

            if avg_vol > 0 and curr_vol > avg_vol * 2:  # Volume 2x average
                unusual_volume = True

    # Volatility regime
    volatility_regime = None
    if vol_20d:
        if vol_20d < 1.0:
            volatility_regime = "low"
        elif vol_20d > 3.0:
            volatility_regime = "high"
        else:
            volatility_regime = "normal"

    # Comparative metrics
    sp500_performance_today = _fetch_sp500_performance()
    sector_performance_today = _fetch_sector_performance(sector)

    industry_label, industry_etf = _industry_benchmark_etf(industry, sector)
    industry_performance_today = _fetch_etf_daily_move(industry_etf)

    peer_group_label, peer_group_size, peer_avg_move_today = _peer_benchmark_for_ticker(
        primary_ticker=t,
        sector=sector,
        industry=industry,
        max_peers=10,
    )

    relative_strength = None
    if day_move_pct and sector_performance_today:
        relative_strength = _safe_float(day_move_pct - sector_performance_today)

    relative_strength_vs_industry = None
    if day_move_pct and industry_performance_today:
        relative_strength_vs_industry = _safe_float(day_move_pct - industry_performance_today)

    relative_strength_vs_peers = None
    if day_move_pct and peer_avg_move_today is not None:
        relative_strength_vs_peers = _safe_float(day_move_pct - peer_avg_move_today)

    res = MarketResult(
            price_series=series,
            day_move_pct=day_move_pct,
            vol_20d=vol_20d,
            move_zscore=z,
            data_source=data_source,
            last_close_date=series[-1]["date"] if series else None,
            price_series_days=len(series) if series else 0,
            current_price=current_price,
            week_52_high=week_52_high,
            week_52_low=week_52_low,
            pct_from_52w_high=pct_from_52w_high,
            pct_from_52w_low=pct_from_52w_low,
            market_cap=market_cap,
            sector=sector,
            industry=industry,
            beta=beta,
            pe_ratio=pe_ratio,
            sector_performance_today=sector_performance_today,
            sp500_performance_today=sp500_performance_today,
            relative_strength=relative_strength,
            industry_benchmark=industry_label,
            industry_performance_today=industry_performance_today,
            relative_strength_vs_industry=relative_strength_vs_industry,
            peer_group_label=peer_group_label,
            peer_group_size=peer_group_size,
            peer_avg_move_today=peer_avg_move_today,
            relative_strength_vs_peers=relative_strength_vs_peers,
            rsi_14d=rsi_14d,
            ma_50d=ma_50d,
            ma_200d=ma_200d,
            unusual_volume=unusual_volume,
            near_52w_high=near_52w_high,
            volatility_regime=volatility_regime,
            average_volume_20d=average_volume_20d,
            current_volume=current_volume
        )
    _cache_set(t, res)
    return res


def fetch_market_context_light(ticker: str | None) -> MarketResult:
    """Lightweight market context for secondary tickers.

    Intent:
    - Keep the UI able to render per-ticker charts + daily move.
    - Avoid expensive / rate-limit-prone calls for benchmarks and peer baskets.

    Returned fields:
    - price_series (1mo)
    - day_move_pct / vol_20d / move_zscore (best-effort)
    - minimal meta (data_source, last_close_date, price_series_days)

    Everything else is left as None/False.
    """
    if not ticker:
        return MarketResult(price_series=[], day_move_pct=None, vol_20d=None, move_zscore=None)

    t = _normalize_ticker(ticker)
    # NOTE: We intentionally do NOT use the main cache, because fetch_market_context()
    # caches the fully computed object. We don't want to accidentally compute heavy
    # benchmarks for many tickers and keep them around.

    # Best-effort: try yfinance for a small window only.
    df = pd.DataFrame()
    data_source: str | None = None
    try:
        df = yf.download(t, period="1mo", interval="1d", auto_adjust=True, progress=False, threads=False)
        df = _coerce_ohlcv_df(df)
        if df is not None and not df.empty and "Close" in df.columns:
            data_source = "yfinance"
    except Exception:
        df = pd.DataFrame()

    # Fall back to Alpha Vantage close-only (we already have this, and it is cheaper).
    if df is None or df.empty or "Close" not in df.columns:
        series_av = fetch_daily_series_1mo(t)
        if series_av:
            last_close_date = series_av[-1]["date"]
            series_days = len(series_av)
        else:
            last_close_date = None
            series_days = 0
        return MarketResult(
            price_series=series_av,
            day_move_pct=None,
            vol_20d=None,
            move_zscore=None,
            data_source="alpha_vantage" if series_av else None,
            last_close_date=last_close_date,
            price_series_days=series_days,
        )

    closes = df["Close"].dropna()
    closes_1m = closes.tail(32)
    closes_stats = closes.tail(60)

    series = [{"date": idx.date().isoformat(), "close": float(val)} for idx, val in closes_1m.items()]

    day_move_pct = None
    try:
        if len(closes) >= 2:
            prev_close = float(closes.iloc[-2])
            last_close = float(closes.iloc[-1])
            if prev_close != 0:
                day_move_pct = _safe_float(((last_close - prev_close) / prev_close) * 100.0)
    except Exception:
        day_move_pct = None

    vol_20d = None
    move_zscore = None
    try:
        rets = closes_stats.pct_change().dropna()
        if not rets.empty:
            vol_20 = rets.tail(20).std(ddof=0)
            vol_20d = _safe_float(vol_20 * 100.0)
            if vol_20 and vol_20 > 0:
                move_zscore = _safe_float(float(rets.iloc[-1]) / float(vol_20))
    except Exception:
        vol_20d = None
        move_zscore = None

    return MarketResult(
        price_series=series,
        day_move_pct=day_move_pct,
        vol_20d=vol_20d,
        move_zscore=move_zscore,
        data_source=data_source,
        last_close_date=series[-1]["date"] if series else None,
        price_series_days=len(series) if series else 0,
    )


def fetch_markets_context(tickers: list[str]) -> list[TickerMarketResult]:
    out: list[TickerMarketResult] = []
    seen: set[str] = set()

    for t in tickers:
        nt = _normalize_ticker(t)
        if not nt or nt in seen:
            continue

        seen.add(nt)
        # Secondary tickers get a lightweight fetch to reduce rate-limit pressure.
        r = fetch_market_context_light(nt)
        out.append(
            TickerMarketResult(
                ticker=nt,
                price_series=r.price_series,
                day_move_pct=r.day_move_pct,
                vol_20d=r.vol_20d,
                move_zscore=r.move_zscore,
                data_source=getattr(r, "data_source", None),
                last_close_date=getattr(r, "last_close_date", None),
                price_series_days=getattr(r, "price_series_days", None),
                # Keep everything else unset for secondary tickers.
                week_52_high=None,
                week_52_low=None,
                pct_from_52w_high=None,
                market_cap=None,
                sector=None,
                industry=None,
                rsi_14d=None,
                ma_50d=None,
                ma_200d=None,
                pct_from_52w_low=None,
                beta=None,
                pe_ratio=None,
        sector_performance_today=None,
        sp500_performance_today=None,
        relative_strength=None,
        industry_benchmark=None,
        industry_performance_today=None,
        relative_strength_vs_industry=None,
        peer_group_label=None,
        peer_group_size=None,
        peer_avg_move_today=None,
        relative_strength_vs_peers=None,
        unusual_volume=False,
        near_52w_high=False,
        volatility_regime=None,
        average_volume_20d=None,
        current_volume=None,
            )
        )

    return out
