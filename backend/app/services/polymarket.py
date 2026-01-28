from __future__ import annotations

"""Polymarket integration (best-effort).

Production considerations:
- Polymarket doesn't have a universally stable unauthenticated API surface.
- This module is intentionally designed to be safe/offline-first:
  - By default we do NOT make any network calls.
  - We provide a tiny curated mapping for common topics.

If you want live data later, we can add an optional HTTP client behind an
environment flag + caching + timeouts.
"""

from dataclasses import dataclass
import re
import time
from typing import Iterable

import httpx


@dataclass(frozen=True)
class PolymarketBet:
    title: str
    url: str | None = None
    probability: float | None = None
    category: str | None = None
    reason: str | None = None


# -----------------------------
# Live Polymarket (best-effort)
# -----------------------------

_LIVE_TTL_SECONDS = 60 * 15  # 15 minutes
_live_cache: dict[str, tuple[float, list[PolymarketBet]]] = {}


def _cache_get(key: str) -> list[PolymarketBet] | None:
    hit = _live_cache.get(key)
    if not hit:
        return None
    ts, val = hit
    if time.time() - ts > _LIVE_TTL_SECONDS:
        _live_cache.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: list[PolymarketBet]) -> None:
    _live_cache[key] = (time.time(), val)


def _build_query(text: str, tickers: Iterable[str] | None, companies: Iterable[str] | None) -> str:
    """Build a short search query for Polymarket markets."""
    # Prefer tickers/companies because they are high-signal.
    parts: list[str] = []
    for t in (tickers or []):
        t = str(t).strip().upper()
        if t and len(t) <= 6:
            parts.append(t)
    for c in (companies or []):
        c = str(c).strip()
        if c and len(c) <= 40:
            parts.append(c)

    # Add a few macro keywords if present.
    toks = _keywords(text)
    for kw in ["fed", "fomc", "cpi", "inflation", "rates", "bitcoin", "spy", "sp500", "tariffs", "china"]:
        if kw in toks:
            parts.append(kw)

    # Keep it short.
    q = " ".join(parts)
    q = re.sub(r"\s+", " ", q).strip()
    return q[:120]


def _gamma_market_url(slug: str | None) -> str | None:
    # Polymarket market URLs usually look like /market/{slug}
    if not slug:
        return None
    return f"https://polymarket.com/market/{slug}"


def _fetch_live_polymarket_bets(query: str, *, limit: int = 3) -> list[PolymarketBet]:
    """Fetch markets from Polymarket via a best-effort public endpoint.

    We keep strict timeouts and cache to avoid slowing down analysis.
    If it fails, caller should fall back to curated/offline.
    """
    q = (query or "").strip()
    if not q:
        return []

    # Cache by query only so callers can request different limits and still top-up.
    cache_key = f"q:{q.lower()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached[: max(0, int(limit))]

    # Polymarket's public data backend is commonly referred to as "Gamma".
    # Endpoints can change; this is best-effort.
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        # Pull more than we need; we'll filter + score locally.
        "limit": 50,
        "active": "true",
        "closed": "false",
        "search": q,
        "order": "volume",
        "descending": "true",
    }

    query_toks = _keywords(q)

    def is_low_signal(title: str) -> bool:
        tl = title.lower()
        # Filter out ultra-short horizon "up/down" minute markets; they dominate volume.
        if re.search(r"\b\d+\s*(?:m|min|minute|minutes)\b", tl):
            return True
        if "up or down" in tl:
            return True
        if re.search(r"\b\d{1,2}:\d{2}\b", tl):
            return True
        return False

    scored: list[tuple[float, PolymarketBet]] = []
    try:
        with httpx.Client(timeout=httpx.Timeout(2.5, connect=1.0)) as client:
            r = client.get(url, params=params, headers={"User-Agent": "finance-news-assistant/1.0"})
            r.raise_for_status()
            data = r.json()

        if not isinstance(data, list):
            return []

        for m in data:
            if not isinstance(m, dict):
                continue
            title = (m.get("question") or m.get("title") or "").strip()
            if not title:
                continue
            if is_low_signal(title):
                continue
            slug = (m.get("slug") or "").strip() or None
            category = (m.get("category") or m.get("eventCategory") or None)

            # Probability is typically stored per-outcome; some APIs offer "lastTradePrice" style.
            # We'll best-effort: if a market is binary, the YES outcome is often first.
            prob = None
            outcomes = m.get("outcomes")
            outcome_prices = m.get("outcomePrices")
            if isinstance(outcomes, list) and isinstance(outcome_prices, list) and outcomes and outcome_prices:
                try:
                    # Find YES
                    yes_idx = None
                    for i, o in enumerate(outcomes):
                        if isinstance(o, str) and o.strip().lower() in {"yes", "true"}:
                            yes_idx = i
                            break
                    if yes_idx is None:
                        yes_idx = 0
                    p = float(outcome_prices[yes_idx])
                    if 0.0 <= p <= 1.0:
                        prob = p
                except Exception:
                    prob = None

            bet = PolymarketBet(
                title=title,
                url=_gamma_market_url(slug),
                probability=prob,
                category=str(category) if category else None,
                reason=f"Matched by Polymarket search: '{q}'",
            )

            # Score: keyword overlap between query and market title.
            title_toks = _keywords(title)
            overlap = len(query_toks & title_toks)
            score = float(overlap)

            # Prefer markets that mention our tickers/companies explicitly.
            if any(tok.isupper() and tok in title for tok in q.split() if tok.isupper()):
                score += 2.5

            scored.append((score, bet))

        scored.sort(key=lambda x: x[0], reverse=True)
        bets_all = [b for score, b in scored if score > 0]
        _cache_set(cache_key, bets_all)
        return bets_all[: max(0, int(limit))]
    except Exception:
        return []


# Curated fallback list. Keep it small and high-signal.
# "probability" is None because we are not fetching live odds.
_CURATED: list[PolymarketBet] = [
    PolymarketBet(
        title="Will the Fed cut rates at the next FOMC meeting?",
        url="https://polymarket.com/",
        category="Macro / Rates",
        reason="Article mentions Fed, yield, inflation, CPI, or rate cuts.",
    ),
    PolymarketBet(
        title="Will inflation (CPI) come in higher than last month?",
        url="https://polymarket.com/",
        category="Macro / Inflation",
        reason="Article references CPI, inflation surprises, or price pressures.",
    ),
    PolymarketBet(
        title="Will the S&P 500 (SPY) finish higher this week?",
        url="https://polymarket.com/",
        category="Markets",
        reason="Article discusses broad market direction or risk-on/risk-off sentiment.",
    ),
    PolymarketBet(
        title="Will US recession be declared this year?",
        url="https://polymarket.com/",
        category="Macro",
        reason="Article mentions recession, downturn, unemployment spike.",
    ),
    PolymarketBet(
        title="Will the US impose new tariffs on China this year?",
        url="https://polymarket.com/",
        category="Geopolitics / Trade",
        reason="Article mentions tariffs, trade restrictions, export controls.",
    ),
    PolymarketBet(
        title="Will Bitcoin break a new all-time high this year?",
        url="https://polymarket.com/",
        category="Crypto",
        reason="Article mentions Bitcoin/crypto prices or ETF flows.",
    ),
    PolymarketBet(
        title="Will Nvidia (NVDA) hit a new all-time high this year?",
        url="https://polymarket.com/",
        category="Stocks",
        reason="Article is mainly about Nvidia or AI chip demand.",
    ),
    PolymarketBet(
        title="Will AI chip demand remain strong this year?",
        url="https://polymarket.com/",
        category="Technology / AI",
        reason="Article discusses AI infrastructure, chips, datacenters, or GPU demand.",
    ),
    PolymarketBet(
        title="Will US impose additional export controls on advanced AI chips this year?",
        url="https://polymarket.com/",
        category="Geopolitics / Tech",
        reason="Article references export controls, China restrictions, or semiconductor policy.",
    ),
]


def _keywords(text: str) -> set[str]:
    t = (text or "").lower()
    toks = set(re.findall(r"[a-z]{3,}", t))
    return toks


def top_relevant_bets(
    *,
    text: str,
    tickers: Iterable[str] | None = None,
    companies: Iterable[str] | None = None,
    limit: int = 3,
) -> list[PolymarketBet]:
    """Return top-N curated Polymarket markets most relevant to the article.

    This is deterministic and offline; it uses simple keyword scoring.
    """
    # 1) Try live Polymarket search first (best-effort; can be sparse).
    try:
        q = _build_query(text, tickers, companies)
        live = _fetch_live_polymarket_bets(q, limit=limit)
    except Exception:
        live = []

    # 2) Offline curated matching (used as fallback or to top up sparse live results).
    toks = _keywords(text)
    tickers_u = {str(t).upper() for t in (tickers or []) if str(t).strip()}
    companies_l = {str(c).lower() for c in (companies or []) if str(c).strip()}

    scored: list[tuple[int, PolymarketBet]] = []
    for bet in _CURATED:
        score = 0
        title_l = bet.title.lower()

        # Macro cues
        if any(k in toks for k in {"fed", "fomc", "inflation", "cpi", "rates", "yield", "cut", "hike", "pause"}):
            if "fed" in title_l or "rates" in title_l:
                score += 6
            if "cpi" in title_l or "inflation" in title_l:
                score += 5
            if "s&p" in title_l or "sp" in title_l or "spy" in title_l:
                score += 2
        if any(k in toks for k in {"recession", "downturn", "unemployment"}):
            if "recession" in title_l:
                score += 5
        if any(k in toks for k in {"tariff", "tariffs", "china", "export", "controls", "trade"}):
            if "tariff" in title_l:
                score += 5

        # Crypto cues
        if any(k in toks for k in {"bitcoin", "btc", "crypto", "ethereum", "eth"}):
            if "bitcoin" in title_l:
                score += 4

        # Company cues (keep minimal to avoid proxy logic)
        if "NVDA" in tickers_u or any("nvidia" in c for c in companies_l) or "nvidia" in toks:
            if "nvidia" in title_l:
                score += 4

        # AI / semiconductor cues
        if any(k in toks for k in {"ai", "chip", "chips", "gpu", "gpus", "semiconductor", "datacenter", "data", "infrastructure"}):
            if any(k in title_l for k in ["ai", "chip", "chips", "gpu", "gpus", "semiconductor", "export controls"]):
                score += 3

        if score > 0:
            scored.append((score, bet))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = [b for _, b in scored[: max(0, int(limit))]]

    # If live has enough, prefer it.
    if live and len(live) >= max(1, int(limit)):
        return live[: max(0, int(limit))]

    # If we got some live results but not enough, top up with curated without duplicates.
    if live:
        seen_titles = {b.title.strip().lower() for b in live}
        topped = live[:]
        for b in out:
            if len(topped) >= max(0, int(limit)):
                break
            if b.title.strip().lower() in seen_titles:
                continue
            topped.append(b)
        if len(topped) < max(0, int(limit)):
            # Ensure we always return something useful.
            for b in [_CURATED[0], _CURATED[1], _CURATED[2], _CURATED[3], _CURATED[4]]:
                if len(topped) >= max(0, int(limit)):
                    break
                if b.title.strip().lower() in {x.title.strip().lower() for x in topped}:
                    continue
                topped.append(b)
        return topped[: max(0, int(limit))]

    # If nothing matched, return generic macro bets as a safe fallback.
    if not out:
        out = [
            _CURATED[0],
            _CURATED[2],
            _CURATED[1],
        ][: max(0, int(limit))]

    return out
