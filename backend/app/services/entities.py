from __future__ import annotations

import re

from .sp500 import load_sp500, resolve_sp500_ticker


_EXCHANGE_TAG_RE = re.compile(r"\b(?:NASDAQ|NYSE|AMEX)\s*:\s*([A-Z]{1,5}(?:-[A-Z])?)\b")
_DOLLAR_RE = re.compile(r"\$([A-Z]{1,5}(?:-[A-Z])?)\b")
_BARE_TICKER_RE = re.compile(r"\b([A-Z]{1,5}(?:-[A-Z])?)\b")

_STOP_TICKERS = {
    "CEO",
    "CFO",
    "EPS",
    "ETF",
    "SEC",
    "FED",
    "FOMC",
    "USD",
    "EUR",
    "GDP",
    "CPI",
    "AI",
    "IPO",
    "ADR",
    "Q1",
    "Q2",
    "Q3",
    "Q4",
    "FY",
    "YOY",
    "YTD",
    "EBITDA",
}

# Lightweight abbreviation/company alias map for common financial names.
# This enables recognition when an article mentions an abbreviation without explicit ticker formatting.
_ALIAS_TO_TICKER: dict[str, str] = {
    "BP": "BP",  # BP p.l.c. (NYSE)
    "BRITISH PETROLEUM": "BP",
    "ALPHABET": "GOOGL",
    "GOOGLE": "GOOGL",
    "BERKSHIRE": "BRK-B",
    "BERKSHIRE HATHAWAY": "BRK-B",
    # AI orgs (private) -> public proxies (used only for market charts)
    # OpenAI has no ticker; map to closest public exposure.
    "OPENAI": "MSFT",
    "CHATGPT": "MSFT",
    # Anthropic / Claude have no tickers; major partner/exposure is Amazon.
    "ANTHROPIC": "AMZN",
    "CLAUDE": "AMZN",
    # Cursor (Anysphere) is private; map to a broad dev-tools proxy.
    "CURSOR": "MSFT",
}

_ALIAS_TOKEN_RE = re.compile(r"\b([A-Z]{2,5})\b")


def extract_tickers(text: str) -> list[str]:
    candidates: list[str] = []
    candidates += _EXCHANGE_TAG_RE.findall(text)
    candidates += _DOLLAR_RE.findall(text)

    # Only consider bare tickers if we have some stronger financial context.
    has_market_context = bool(re.search(r"\b(?:stock|shares|ticker|NASDAQ|NYSE|earnings|EPS|revenue|profits?|guidance|forecast)\b", text, re.I))
    if has_market_context:
        candidates += _BARE_TICKER_RE.findall(text)

    out: list[str] = []
    seen = set()
    for t in candidates:
        t = t.upper()
        if t in _STOP_TICKERS:
            continue
        if len(t) == 1 and t in {"A", "I"}:
            continue
        if not re.match(r"^[A-Z]{1,5}(?:-[A-Z])?$", t):
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)

    return out


def infer_ticker_aliases(text: str) -> dict[str, str]:
    """Return mapping of abbreviations/names found in text to their resolved tickers."""
    aliases: dict[str, str] = {}

    # Exact phrase matches for multi-word aliases.
    upper = text.upper()
    for alias, ticker in _ALIAS_TO_TICKER.items():
        if " " in alias and alias in upper:
            aliases[alias.title()] = ticker

    # Token-level abbreviations (e.g., BP)
    for m in _ALIAS_TOKEN_RE.finditer(text):
        tok = m.group(1).upper()
        if tok in _ALIAS_TO_TICKER:
            aliases[tok] = _ALIAS_TO_TICKER[tok]

    return aliases


_COMPANY_SUFFIX = r"(?:Inc\.|Incorporated|Corp\.|Corporation|Ltd\.|Limited|PLC|Co\.|Company|Group|Holdings)"
_COMPANY_RE = re.compile(rf"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){{0,3}})\s+{_COMPANY_SUFFIX}\b")

_COMPANY_LIST_LINE_RE = re.compile(
    r"(?im)^(?:including|includes?|such as|namely|led by)\s+([A-Z][^\n]{0,120})$"
)


def _extract_company_name_list(text: str) -> list[str]:
    """Extract company-like names from simple lists like '... including X, Y and Z'.

    This is intentionally conservative: it only looks at short lines and then
    pulls out capitalized spans up to ~4 tokens.
    """
    out: list[str] = []

    # Common formatting in news blurbs: one company per line after "including".
    lines = [ln.strip() for ln in text.splitlines()]
    for ln in lines:
        if not ln:
            continue

        # If the line contains multiple names separated by commas/and, split it.
        m = _COMPANY_LIST_LINE_RE.match(ln)
        rhs = m.group(1) if m else ln

        parts = re.split(r"\s*(?:,|\band\b|\&|\u2022)\s*", rhs, flags=re.I)
        for p in parts:
            p = p.strip(" .;:()[]{}\"'\t")
            if not p:
                continue

            # Normalize common constructions like "Google parent Alphabet" -> "Alphabet"
            p = re.sub(r"\bparent\b\s+", "", p, flags=re.I)
            p = re.sub(r"\bparent\s+company\b\s+", "", p, flags=re.I)

            # If we have something like "Google Alphabet" or "Google parent Alphabet",
            # prefer the trailing capitalized span.
            tail = re.search(r"([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\s*$", p)
            if tail:
                p = tail.group(1)

            # Pull a capitalized name span (1-4 tokens).
            nm = re.match(r"^([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,3})$", p)
            if not nm:
                continue
            name = nm.group(1).strip()
            if name not in out:
                out.append(name)

    return out


def _sp500_companies_found_in_text(text: str) -> list[str]:
    """Find S&P 500 securities mentioned in the text by substring matching.

    Only runs on a reduced set of names derived from the local dataset.
    """
    upper = text.upper()
    found: list[str] = []

    # Prefer longer names first to reduce partial matches.
    candidates = sorted((c.security for c in load_sp500()), key=len, reverse=True)
    for name in candidates:
        key = name.upper()

        # Avoid super-generic short names.
        if len(key) < 4:
            continue

        if key in upper:
            found.append(name)

        # Also try common stripped variants.
        stripped = re.sub(r"\s*\(.*?\)\s*", "", key).strip()
        if stripped and stripped != key and stripped in upper:
            found.append(re.sub(r"\s*\(.*?\)\s*", "", name).strip())

    # De-dupe while keeping order.
    out: list[str] = []
    seen = set()
    for n in found:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def extract_companies(text: str, tickers: list[str]) -> list[str]:
    companies: list[str] = []
    # Suffix-based extraction
    for m in _COMPANY_RE.finditer(text):
        name = m.group(0).strip()
        if name not in companies:
            companies.append(name)

    # List-style extraction (common in short market wrap blurbs)
    for n in _extract_company_name_list(text):
        if n not in companies:
            companies.append(n)

    # S&P 500 dictionary matching (catches cases like "Nvidia" without "Inc.")
    for n in _sp500_companies_found_in_text(text):
        if n not in companies:
            companies.append(n)

    # Near-ticker heuristic: "Apple (AAPL)" or "Apple, ticker AAPL"
    for t in tickers:
        near = re.findall(rf"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){{0,3}})\s*\(\s*{re.escape(t)}\s*\)", text)
        for n in near:
            n = n.strip()
            if n and n not in companies:
                companies.append(n)

    return companies


def infer_company_tickers(companies: list[str], ticker_aliases: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in companies:
        u = c.upper()
        for alias, ticker in _ALIAS_TO_TICKER.items():
            if alias in u:
                out[c] = ticker
                break

        if c not in out:
            # Try direct dataset resolution first.
            resolved = resolve_sp500_ticker(c)
            if resolved:
                out[c] = resolved

        if c not in out:
            # Retry with a few cheap normalizations to improve hit rate for
            # short mentions like "Apple" / "Amazon".
            simplified = re.sub(r"\b(Inc\.|Incorporated|Corp\.|Corporation|Ltd\.|Limited|PLC|Co\.|Company|Group|Holdings)\b", "", c, flags=re.I)
            simplified = re.sub(r"\s+", " ", simplified).strip(" ,.")
            if simplified and simplified != c:
                resolved = resolve_sp500_ticker(simplified)
                if resolved:
                    out[c] = resolved

        if c not in out:
            # Final fallback: substring match on the local dataset.
            # This keeps us offline and helps with cases like "Berkshire Hathaway".
            key = simplified.lower() if 'simplified' in locals() and simplified else c.lower()
            key = key.strip()
            if key:
                for comp in load_sp500():
                    if key in comp.security.lower():
                        out[c] = comp.ticker
                        break

    # If we only saw an abbreviation (e.g., "BP"), treat it as a company name too.
    for alias, ticker in ticker_aliases.items():
        if alias.isupper() and alias not in out:
            out[alias] = ticker

    return out


def choose_primary_ticker(tickers: list[str]) -> str | None:
    if not tickers:
        return None
    return tickers[0]
