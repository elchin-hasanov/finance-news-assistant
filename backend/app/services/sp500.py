from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Sp500Company:
    ticker: str
    security: str


_DATA_PATH = Path(__file__).resolve().parent / "data" / "sp500.csv"


def _normalize(s: str) -> str:
    s = s.strip().lower()
    # Drop punctuation and collapse whitespace for robust matching.
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


_CORP_SUFFIXES = (
    " inc",
    " inc ",
    " incorporated",
    " corp",
    " corporation",
    " ltd",
    " limited",
    " plc",
    " co",
    " company",
    " group",
    " holdings",
    " holding",
)


def _strip_corp_suffixes(normalized: str) -> str:
    s = normalized
    # Repeatedly strip, because some names have multiple suffix-like words.
    changed = True
    while changed:
        changed = False
        for suf in _CORP_SUFFIXES:
            if s.endswith(suf):
                s = s[: -len(suf)].rstrip()
                changed = True
    return s


def _name_variants(security_name: str) -> set[str]:
    """Generate normalized lookup variants for a security name.

    Goal: map user mentions like "Amazon" or "Amazon.com" to "Amazon.com, Inc.".
    This stays fully offline and deterministic.
    """
    raw = security_name.strip()
    variants: set[str] = set()

    def add(v: str) -> None:
        n = _normalize(v)
        if n:
            variants.add(n)

    add(raw)
    # Remove parentheses content: "Alphabet Inc. (Class A)" -> "Alphabet Inc."
    add(re.sub(r"\s*\(.*?\)\s*", "", raw).strip())

    # Simpler separators: "Amazon.com, Inc." -> "Amazon.com Inc"
    add(raw.replace(",", " "))
    add(raw.replace(",", " ").replace(".", " "))

    # Domain-like normalization: "amazon.com" -> "amazon"
    base = re.sub(r"\b\.com\b", "", _normalize(raw)).strip()
    if base:
        variants.add(base)

    # Strip corporate suffixes: "amazon com inc" -> "amazon com" and "amazon"
    stripped = _strip_corp_suffixes(_normalize(raw))
    if stripped:
        variants.add(stripped)
        variants.add(_strip_corp_suffixes(re.sub(r"\bcom\b", "", stripped).strip()))

    # One-token short-name alias for very common pattern "Xxx.com".
    m = re.match(r"^([a-z0-9]+)\s+com\b", stripped)
    if m:
        variants.add(m.group(1))

    # Drop trailing class words.
    for v in list(variants):
        v2 = re.sub(r"\bclass\s+[a-z]\b", "", v).strip()
        if v2:
            variants.add(v2)

    # Final cleanup.
    variants = {re.sub(r"\s+", " ", v).strip() for v in variants if v.strip()}
    return variants


def _normalize_ticker(ticker: str) -> str:
    # Wikipedia uses BRK.B / BF.B, yfinance usually expects BRK-B.
    return ticker.strip().upper().replace(".", "-")


@lru_cache(maxsize=1)
def load_sp500() -> list[Sp500Company]:
    if not _DATA_PATH.exists():
        raise RuntimeError(f"Missing S&P 500 dataset at {_DATA_PATH}")

    out: list[Sp500Company] = []
    with _DATA_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = _normalize_ticker(row["ticker"])
            security = row["security"].strip()
            out.append(Sp500Company(ticker=ticker, security=security))
    return out


@lru_cache(maxsize=1)
def sp500_name_index() -> dict[str, str]:
    """Map normalized company names to tickers."""
    idx: dict[str, str] = {}
    for c in load_sp500():
        for key in _name_variants(c.security):
            # First writer wins; prefer the first occurrence in csv order.
            idx.setdefault(key, c.ticker)

    return idx


def resolve_sp500_ticker(company_or_alias: str) -> str | None:
    key = _normalize(company_or_alias)
    if not key:
        return None
    return sp500_name_index().get(key)
