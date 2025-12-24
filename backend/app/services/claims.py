from __future__ import annotations

import re

from .text_utils import split_sentences


_CLAIM_HINT_RE = re.compile(
    r"(\$\s?\d|\d\s?%|\b\d{4}\b|\b(?:million|billion|trillion)\b|\bEPS\b|\brevenue\b|\bguidance\b|\bforecast\b)",
    re.I,
)

_NUMBER_RE = re.compile(
    r"(?P<prefix>\$)?(?P<num>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<suffix>%|[MBT]|million|billion|trillion)?",
    re.I,
)


def _parse_number_token(m: re.Match) -> tuple[float, str | None] | None:
    raw = m.group("num")
    if not raw:
        return None
    try:
        val = float(raw.replace(",", ""))
    except ValueError:
        return None

    prefix = m.group("prefix")
    suffix = m.group("suffix")

    unit: str | None = None
    if prefix == "$":
        unit = "$"
    if suffix:
        suf = suffix.lower()
        if suf == "%":
            unit = "%" if unit is None else unit + "%"
        elif suf in {"m", "million"}:
            unit = "million" if unit is None else unit + " million"
            if suf == "m":
                val *= 1.0
        elif suf in {"b", "billion"}:
            unit = "billion" if unit is None else unit + " billion"
            if suf == "b":
                val *= 1.0
        elif suf in {"t", "trillion"}:
            unit = "trillion" if unit is None else unit + " trillion"
            if suf == "t":
                val *= 1.0

    return val, unit


def extract_claims(text: str, limit: int = 10) -> list[dict]:
    sentences = split_sentences(text)
    claims: list[dict] = []

    for s in sentences:
        if not _CLAIM_HINT_RE.search(s):
            continue

        nums = []
        for m in _NUMBER_RE.finditer(s):
            parsed = _parse_number_token(m)
            if parsed is None:
                continue
            val, unit = parsed
            # Avoid capturing years as claim numbers unless clearly a date context
            if unit is None and 1900 <= val <= 2100 and not re.search(r"\b(?:in|since|during)\s+\d{4}\b", s, re.I):
                continue
            nums.append({"value": val, "unit": unit})

        if not nums:
            continue

        claims.append(
            {
                "claim": s,
                "numbers": nums,
                "evidence_sentence": s,
            }
        )
        if len(claims) >= limit:
            break

    return claims
