from __future__ import annotations

import re

from .text_utils import split_sentences


_CLAIM_HINT_RE = re.compile(
    r"(\$\s?\d|\d\s?%|\b\d{4}\b|\b(?:million|billion|trillion)\b|\bEPS\b|\brevenue\b|\bguidance\b|\bforecast\b)",
    re.I,
)

# Patterns that indicate a SENSATIONAL claim (shocking, alarming, or attention-grabbing)
_SENSATIONAL_PATTERNS = [
    # Dramatic percentages
    r"\b(?:surge[ds]?|soar(?:s|ed|ing)?|plunge[ds]?|crash(?:es|ed|ing)?|plummet(?:s|ed|ing)?|skyrocket(?:s|ed|ing)?|tank(?:s|ed|ing)?|collapse[ds]?)\b",
    # Big numbers with emotion
    r"\b(?:record|historic|unprecedented|massive|huge|enormous|staggering|shocking|stunning|remarkable)\b",
    # Danger/risk language
    r"\b(?:warn(?:s|ed|ing)?|threat(?:en)?|risk|danger|crisis|catastroph|disaster|turmoil|chaos|panic)\b",
    # Superlatives
    r"\b(?:biggest|largest|worst|best|highest|lowest|most|least|first|last)\s+(?:ever|in\s+\d+\s+years?|since\s+\d{4})\b",
    # Extreme movement
    r"\b(?:double[ds]?|triple[ds]?|halve[ds]?|wipe[ds]?\s+out)\b",
    # Uncertainty/speculation
    r"\b(?:could|may|might)\s+(?:crash|collapse|surge|soar|plunge|double|triple)\b",
    # Big percentage moves
    r"\b(?:\d{2,})\s*%",  # 10%+ moves
    # Financial distress
    r"\b(?:bankrupt|insolvent|default|layoff|cut\s+\d|fire[ds]?\s+\d|eliminat)\b",
    # Hype language
    r"\b(?:game[-\s]?changer|revolutionary|disrupt|transform|breakthrough)\b",
]

_SENSATIONAL_RE = re.compile("|".join(_SENSATIONAL_PATTERNS), re.I)

# Patterns that indicate boring/factual content (not sensational)
_BORING_PATTERNS = [
    r"^\s*(?:the\s+)?company\s+(?:reported|announced|said|stated)\s+(?:that\s+)?(?:its\s+)?(?:Q\d|quarterly|annual)",
    r"^\s*(?:according\s+to|based\s+on|as\s+of|for\s+the\s+(?:quarter|year))",
    r"^\s*(?:revenue|earnings|net\s+income|EPS)\s+(?:was|were|came\s+in\s+at)",
    r"^\s*shares\s+(?:are\s+)?(?:trading|traded)\s+at",
]

_BORING_RE = re.compile("|".join(_BORING_PATTERNS), re.I)

_NUMBER_RE = re.compile(
    r"(?P<prefix>\$)?(?P<num>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<suffix>%|[MBT]|million|billion|trillion)?",
    re.I,
)

# Maximum claim length (characters)
MAX_CLAIM_LENGTH = 200


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


def _score_sensationalism(sentence: str) -> float:
    """Score how sensational a sentence is (0-10 scale)."""
    score = 0.0
    
    # Check for sensational patterns
    sensational_matches = _SENSATIONAL_RE.findall(sentence)
    score += len(sensational_matches) * 2.0
    
    # Check for large percentage moves (10%+ gets bonus)
    pct_matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", sentence)
    for pct in pct_matches:
        try:
            val = float(pct)
            if val >= 50:
                score += 3.0
            elif val >= 20:
                score += 2.0
            elif val >= 10:
                score += 1.0
        except:
            pass
    
    # Check for large dollar amounts (billions get bonus)
    if re.search(r"\$\s*\d+(?:\.\d+)?\s*(?:billion|trillion|B|T)\b", sentence, re.I):
        score += 1.5
    
    # Penalty for boring/factual patterns
    if _BORING_RE.search(sentence):
        score -= 2.0
    
    # Bonus for exclamation marks or dramatic punctuation
    if "!" in sentence:
        score += 0.5
    
    # Bonus for quotes (often contain dramatic statements)
    if '"' in sentence or "'" in sentence:
        score += 0.5
    
    return max(0, score)


def _truncate_claim(text: str, max_len: int = MAX_CLAIM_LENGTH) -> str:
    """Truncate a claim to max length, trying to break at sentence boundaries."""
    if len(text) <= max_len:
        return text
    
    # Try to find a good break point
    truncated = text[:max_len]
    
    # Look for last sentence-ending punctuation
    for end_char in ['. ', '! ', '? ']:
        last_idx = truncated.rfind(end_char)
        if last_idx > max_len // 2:
            return truncated[:last_idx + 1].strip()
    
    # Fall back to last comma or space
    for break_char in [', ', ' ']:
        last_idx = truncated.rfind(break_char)
        if last_idx > max_len // 2:
            return truncated[:last_idx].strip() + '...'
    
    return truncated.strip() + '...'


def extract_claims(text: str, limit: int = 10) -> list[dict]:
    sentences = split_sentences(text)
    scored_claims: list[tuple[float, dict]] = []

    for s in sentences:
        if not _CLAIM_HINT_RE.search(s):
            continue
        
        # Skip very short or very long sentences
        if len(s) < 30 or len(s) > 500:
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
        
        # Score the sensationalism of this claim
        sensational_score = _score_sensationalism(s)
        
        # Truncate if too long
        claim_text = _truncate_claim(s)

        scored_claims.append(
            (sensational_score, {
                "claim": claim_text,
                "numbers": nums,
                "evidence_sentence": s,
                "sensational_score": sensational_score,
            })
        )

    # Sort by sensationalism score (highest first)
    scored_claims.sort(key=lambda x: x[0], reverse=True)
    
    # Return top claims
    return [claim for _, claim in scored_claims[:limit]]
