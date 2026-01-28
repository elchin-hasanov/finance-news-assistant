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
    sector: str | None = None
    industry: str | None = None


_DATA_PATH = Path(__file__).resolve().parent / "data" / "sp500.csv"


def _normalize(s: str) -> str:
    s = s.strip().lower()
    # Treat punctuation as whitespace and collapse duplicates for robust matching.
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


_CORP_SUFFIXES = (
    " inc",
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
    s = normalized.strip()
    # Repeatedly strip, because some names have multiple suffix-like words.
    changed = True
    while changed:
        changed = False
        for suf in _CORP_SUFFIXES:
            if s.endswith(suf):
                s = s[: -len(suf)].rstrip()
                changed = True
    return s


# Common short-name aliases for S&P 500 companies that don't follow standard patterns.
# Maps ticker -> list of common short names used in news/articles.
_SHORT_NAME_ALIASES: dict[str, list[str]] = {
    "BA": ["boeing"],
    "JPM": ["jpmorgan", "jp morgan", "chase"],
    "META": ["meta", "facebook"],
    "DIS": ["disney"],
    "KO": ["coca cola", "coke"],
    "GS": ["goldman", "goldman sachs"],
    "MS": ["morgan stanley"],
    "WFC": ["wells fargo"],
    "BAC": ["bank of america", "bofa"],
    "CVS": ["cvs"],
    "HD": ["home depot"],
    "UNH": ["unitedhealth"],
    "CI": ["cigna"],
    "CAT": ["caterpillar"],
    "HON": ["honeywell"],
    "GE": ["ge", "general electric"],
    "LMT": ["lockheed", "lockheed martin"],
    "RTX": ["raytheon"],
    "NOC": ["northrop", "northrop grumman"],
    "GD": ["general dynamics"],
    "DE": ["john deere", "deere"],
    "UNP": ["union pacific"],
    "NEE": ["nextera"],
    "BKNG": ["booking", "priceline"],
    "ABNB": ["airbnb"],
    "UBER": ["uber"],
    "NFLX": ["netflix"],
    "PLTR": ["palantir"],
    "CRWD": ["crowdstrike"],
    "PANW": ["palo alto"],
    "CRM": ["salesforce"],
    "ORCL": ["oracle"],
    "ADBE": ["adobe"],
    "INTC": ["intel"],
    "AVGO": ["broadcom"],
    "QCOM": ["qualcomm"],
    "TXN": ["texas instruments"],
    "IBM": ["ibm"],
    "ACN": ["accenture"],
    "INTU": ["intuit", "turbotax"],
    "NOW": ["servicenow"],
    "SBUX": ["starbucks"],
    "MCD": ["mcdonalds", "mcdonald"],
    "NKE": ["nike"],
    "TGT": ["target"],
    "LOW": ["lowes", "lowe's"],
    "CMG": ["chipotle"],
    "YUM": ["yum brands", "pizza hut", "taco bell", "kfc"],
    "MAR": ["marriott"],
    "HLT": ["hilton"],
    "DAL": ["delta", "delta airlines"],
    "UAL": ["united airlines"],
    "AAL": ["american airlines"],
    "RCL": ["royal caribbean"],
    "LIN": ["linde"],
    "SHW": ["sherwin williams"],
    "NEM": ["newmont"],
    "FCX": ["freeport"],
    "COP": ["conocophillips"],
    "SLB": ["schlumberger"],
    "OXY": ["occidental"],
    "KMI": ["kinder morgan"],
    "WMB": ["williams companies"],
    "DUK": ["duke energy"],
    "SO": ["southern company"],
    "D": ["dominion"],
    "AEP": ["aep", "american electric"],
    "EXC": ["exelon"],
    "XOM": ["exxon", "exxonmobil"],
    "CVX": ["chevron"],
    "MPC": ["marathon petroleum"],
    "PSX": ["phillips 66"],
    "EOG": ["eog"],
    "PFE": ["pfizer"],
    "MRK": ["merck"],
    "ABBV": ["abbvie"],
    "JNJ": ["johnson johnson", "j j", "jnj"],
    "LLY": ["eli lilly", "lilly"],
    "BMY": ["bristol myers"],
    "AMGN": ["amgen"],
    "GILD": ["gilead"],
    "VRTX": ["vertex"],
    "REGN": ["regeneron"],
    "TMO": ["thermo fisher"],
    "DHR": ["danaher"],
    "ISRG": ["intuitive surgical"],
    "SYK": ["stryker"],
    "BSX": ["boston scientific"],
    "MDT": ["medtronic"],
    "PM": ["philip morris"],
    "MO": ["altria"],
    "PG": ["procter gamble", "p g"],
    "KR": ["kroger"],
    "COST": ["costco"],
    "WMT": ["walmart"],
    "DG": ["dollar general"],
    "DLTR": ["dollar tree"],
    "T": ["at t", "att"],
    "VZ": ["verizon"],
    "TMUS": ["t mobile", "tmobile"],
    "CMCSA": ["comcast"],
    "SCHW": ["charles schwab", "schwab"],
    "BLK": ["blackrock"],
    "AXP": ["american express", "amex"],
    "SPGI": ["s p global"],
    "ICE": ["intercontinental exchange"],
    "CME": ["cme"],
    "MCO": ["moodys", "moody"],
    "CB": ["chubb"],
    "MMC": ["marsh mclennan"],
    "AON": ["aon"],
    "TRV": ["travelers"],
    "PGR": ["progressive"],
    "ALL": ["allstate"],
    "MET": ["metlife"],
    "PRU": ["prudential"],
    "AIG": ["aig"],
    "F": ["ford"],
    "GM": ["gm", "general motors"],
    "SNPS": ["synopsys"],
    "CDNS": ["cadence"],
    "MSI": ["motorola"],
    "ADI": ["analog devices"],
    "MRVL": ["marvell"],
    "KLAC": ["kla"],
    "LRCX": ["lam research"],
    "AMAT": ["applied materials"],
    "MU": ["micron"],
    "EA": ["electronic arts", "ea sports"],
    "TTWO": ["take two", "rockstar games"],
    "PYPL": ["paypal"],
    "V": ["visa"],
    "MA": ["mastercard"],
}


def _name_variants(security_name: str, ticker: str | None = None) -> set[str]:
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

    # Add ticker-based short aliases from _SHORT_NAME_ALIASES
    if ticker:
        for alias in _SHORT_NAME_ALIASES.get(ticker.upper(), []):
            variants.add(_normalize(alias))

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

            # Backward compatible: sector/industry columns may not exist in the CSV.
            sector = (row.get("sector") or "").strip() or None
            industry = (row.get("industry") or "").strip() or None

            out.append(Sp500Company(ticker=ticker, security=security, sector=sector, industry=industry))
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
    # Try direct hit.
    direct = sp500_name_index().get(key)
    if direct:
        return direct

    # Strip corporate suffixes and retry.
    stripped = _strip_corp_suffixes(key)
    if stripped and stripped != key:
        t = sp500_name_index().get(stripped)
        if t:
            return t
    return None


@lru_cache(maxsize=1)
def sp500_alias_index() -> dict[str, str]:
    """Common offline aliases -> tickers.

    This is intentionally tiny and only covers high-frequency names where our
    minimal CSV might not include the variant users mention.
    """
    aliases: dict[str, str] = {
        "nvidia": "NVDA",
    "nvidia corp": "NVDA",
        "tesla": "TSLA",
        "apple": "AAPL",
        "microsoft": "MSFT",
        "amazon": "AMZN",
        "alphabet": "GOOGL",
        "google": "GOOGL",
        "meta": "META",
    }
    return { _normalize(k).strip(): _normalize_ticker(v) for k, v in aliases.items() }


def resolve_company_ticker_offline(company_or_alias: str) -> str | None:
    """Resolve a company mention to a ticker using local data + a small alias map."""
    t = resolve_sp500_ticker(company_or_alias)
    if t:
        return t
    key = _normalize(company_or_alias).strip()
    if not key:
        return None
    a = sp500_alias_index().get(key)
    if a:
        return a

    stripped = _strip_corp_suffixes(key).strip()
    if stripped and stripped != key:
        return sp500_alias_index().get(stripped)
    return None


@lru_cache(maxsize=1)
def sp500_ticker_index() -> dict[str, Sp500Company]:
    """Map normalized ticker -> company record."""
    return {c.ticker: c for c in load_sp500()}


def lookup_sp500_profile(ticker: str) -> tuple[str | None, str | None]:
    """Return (sector, industry) for an S&P 500 ticker using local data."""
    if not ticker:
        return (None, None)
    t = _normalize_ticker(ticker)
    c = sp500_ticker_index().get(t)
    if not c:
        return (None, None)
    return (c.sector, c.industry)
