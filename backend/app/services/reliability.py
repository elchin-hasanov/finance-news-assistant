"""Article reliability scoring — v2.

Philosophy
──────────
Start from a **neutral baseline of 50** (neither reliable nor unreliable).
Add points for evidence of journalistic quality and subtract points for
red flags.  The final score is clamped to 0–100.

The design avoids the problems of v1:
  • No arbitrary multipliers — every signal has a clear ceiling and
    contributes a bounded number of points.
  • Source attribution uses broader patterns (company said, analysts at X,
    SEC filing, etc.) instead of only "according to".
  • Hedging language ("may", "could") is REWARDED (shows responsible
    reporting) unless paired with hype words (then it's speculation).
  • Balanced perspective requires genuine juxtaposition, not just the
    presence of random growth/risk words.
  • Sensational claims use claim density rather than raw count, and do
    not double-count what hype already penalises.
  • Hype and urgency are separate, clearly-bounded penalties.
"""

from __future__ import annotations

import math
import re

from .text_utils import split_sentences

# ── helpers ─────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _sentence_count(text: str) -> int:
    return max(1, len(split_sentences(text)))


# ── Signal 1: Source Attribution (0–15 pts) ─────────────────────────
# Rewards text that attributes claims to identifiable sources.

_ATTRIBUTION_PATTERNS = [
    # Classic attribution
    r"according to\b",
    r"\bsaid\b",
    r"\bstated\b",
    r"\breported\b",
    r"\btold\b",
    r"\bconfirmed\b",
    r"\bannounced\b",
    r"\bdisclosed\b",
    # Institutional / document sources
    r"\bfiling\b",
    r"\bearnings\s+(?:call|release|report)\b",
    r"\bSEC\b",
    r"\bpress\s+release\b",
    r"\bregulatory\b",
    r"\bstatement\b",
    r"\bdata\s+(?:from|shows?|suggests?|indicates?)\b",
    # Named analyst / source patterns
    r"\banalyst[s]?\b.*?\b(?:at|from|of)\b",
    r"\baccording\b",
    r"\bcited\b",
    r"\breferenc(?:ed|ing)\b",
    r"\bquoted?\b",
    # "the company said / noted / added"
    r"\bthe\s+company\s+(?:said|stated|noted|added|reported)\b",
    # Research / survey
    r"\bresearch\b",
    r"\bsurvey\b",
    r"\breport(?:ed)?\b",
]
_ATTRIBUTION_RES = [re.compile(p, re.I) for p in _ATTRIBUTION_PATTERNS]


def _score_attribution(text: str) -> float:
    """Count distinct attribution patterns found → 0–15 pts."""
    hits = sum(1 for r in _ATTRIBUTION_RES if r.search(text))
    # 1 hit=3, 2=6, 3=9, 4=12, 5+=15
    return min(15.0, hits * 3.0)


# ── Signal 2: Numerical Evidence (0–10 pts) ─────────────────────────
# Articles with concrete numbers tend to be more substantive.

_NUMBER_RE = re.compile(
    r"(?:\$\s?)?\d[\d,]*(?:\.\d+)?\s*(?:%|million|billion|trillion|M|B|T)?\b",
    re.I,
)


def _score_numerical_evidence(text: str) -> float:
    nums = _NUMBER_RE.findall(text)
    count = len(nums)
    sents = _sentence_count(text)
    density = count / sents
    # Roughly: 0.3 num/sent → 5pts, 0.6+ → 10pts
    return min(10.0, round(density * 16, 1))


# ── Signal 3: Hedging & Qualified Language (0–8 pts) ─────────────────
# Responsible journalism hedges uncertain claims.

_HEDGING_WORDS = re.compile(
    r"\b(?:may|might|could|possibly|potentially|likely|suggests?|"
    r"appears?|estimated?|approximately|roughly|unclear|uncertain|"
    r"it\s+is\s+(?:possible|likely|unclear)|remains\s+to\s+be\s+seen)\b",
    re.I,
)


def _score_hedging(text: str) -> float:
    """Count hedging words, but discount ones in hype-laden sentences."""
    sents = split_sentences(text)
    genuine_hits = 0
    for sent in sents:
        hedge_matches = _HEDGING_WORDS.findall(sent)
        if not hedge_matches:
            continue
        # If the sentence also has hype words, these hedges are just
        # speculation ("could skyrocket") — don't reward them.
        sent_words = {w.lower() for w in _WORD_RE.findall(sent)}
        has_hype = bool(sent_words & _HYPE_WORDS)
        if not has_hype:
            genuine_hits += len(hedge_matches)

    words = _word_count(text)
    if words == 0:
        return 0.0
    ratio = genuine_hits / words
    # 0.5% hedging words → ~4pts, 1%+ → 8pts
    return min(8.0, round(ratio * 800, 1))


# ── Signal 4: Balanced Perspective (0–10 pts) ────────────────────────
# Looks for explicit contrast markers that show the author presents
# multiple sides, not just isolated positive/negative words.

_CONTRAST_MARKERS = re.compile(
    r"\b(?:however|nevertheless|on\s+the\s+other\s+hand|"
    r"conversely|although|while|whereas|despite|"
    r"but\s+(?:analysts?|experts?|some|others?|critics?)|"
    r"at\s+the\s+same\s+time|that\s+said|still|"
    r"nonetheless|meanwhile|in\s+contrast)\b",
    re.I,
)


def _score_balance(text: str) -> float:
    markers = len(_CONTRAST_MARKERS.findall(text))
    sents = _sentence_count(text)
    density = markers / sents
    # ~1 contrast per 4 sentences → 5pts, 1 per 2 → 10pts
    return min(10.0, round(density * 20, 1))


# ── Signal 5: Factual Density (0–7 pts) ─────────────────────────────
# Presence of dates, proper nouns, specific names → factual flavour.

_FACTUAL_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|"
    r"July?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\b"
    r"|Q[1-4]\s+\d{4}"
    r"|fiscal\s+(?:year|quarter)"
    r"|\b20[0-2]\d\b"
    r"|\b(?:CEO|CFO|COO|CTO|president|chairman|director)\b",
    re.I,
)


def _score_factual_density(text: str) -> float:
    hits = len(_FACTUAL_RE.findall(text))
    sents = _sentence_count(text)
    density = hits / sents
    return min(7.0, round(density * 7, 1))


# ── Penalty 1: Hype Language (0 to −20 pts) ─────────────────────────
# Words like "shocking", "skyrocket", "explode", etc.

_HYPE_WORDS = {
    "soar", "soars", "soared", "surge", "surges", "surged",
    "rocket", "rockets", "rocketed", "skyrocket", "skyrockets", "skyrocketed",
    "explode", "explodes", "exploded", "moon", "moonshot", "parabolic",
    "plunge", "plunges", "plunged", "crash", "crashes", "crashed",
    "tank", "tanks", "tanked", "collapse", "collapses", "collapsed",
    "meltdown", "bloodbath", "panic", "capitulation", "wipeout",
    "shocking", "stunning", "unbelievable", "jaw-dropping", "mind-blowing",
    "insane", "wild", "crazy", "epic", "ridiculous", "outrageous",
    "bombshell", "guaranteed", "no-brainer",
    "game-changing", "gamechanging",
}


def _penalty_hype(text: str) -> float:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if not words:
        return 0.0
    hype_count = sum(1 for w in words if w in _HYPE_WORDS)
    ratio = hype_count / len(words)
    # 1% hype → −5, 2% → −10, 4%+ → −20
    return min(20.0, round(ratio * 500, 1))


# ── Penalty 2: Sensational Claims Density (0 to −15 pts) ────────────
# Uses pre-extracted claims from claims.py.

def _penalty_claims(claims: list[dict], text: str) -> float:
    sents = _sentence_count(text)
    if sents == 0:
        return 0.0
    claim_count = len(claims)
    density = claim_count / sents
    # 1 claim per 5 sentences → −5, 1 per 2 → −12, more → −15
    return min(15.0, round(density * 25, 1))


# ── Penalty 3: Emotional Extremes (0 to −10 pts) ────────────────────
# Extreme sentiment scores (very positive or very negative) suggest
# bias rather than balanced reporting.

def _penalty_sentiment_extreme(sentiment_score: float) -> float:
    # sentiment_score is −1.0 to +1.0; 0 is neutral (good)
    extremity = abs(sentiment_score)
    if extremity < 0.25:
        return 0.0
    if extremity < 0.4:
        return 3.0
    if extremity < 0.6:
        return 6.0
    return 10.0


# ── Penalty 4: Urgency / Manipulation Language (0 to −10 pts) ───────

_URGENCY_RE = re.compile(
    r"\b(?:buy\s+now|act\s+now|don'?t\s+miss|limited\s+time|"
    r"before\s+it'?s?\s+too\s+late|last\s+chance|hurry|"
    r"once\s+in\s+a\s+lifetime|right\s+now|immediately)\b",
    re.I,
)


def _penalty_urgency(text: str) -> float:
    hits = len(_URGENCY_RE.findall(text))
    return min(10.0, hits * 4.0)


# ── Penalty 5: Excessive Punctuation / ALL-CAPS (0 to −10 pts) ──────

def _penalty_formatting(text: str) -> float:
    excl = text.count("!")
    caps_words = len(re.findall(r"\b[A-Z]{4,}\b", text))
    # Exclude known tickers / acronyms — only flag 4+ letter ALL-CAPS
    penalty = min(5.0, excl * 1.0) + min(5.0, caps_words * 1.0)
    return min(10.0, penalty)


# ── Bonus: Article Length (0–5 pts) ──────────────────────────────────
# Very short articles are often low-effort / clickbait.

def _bonus_length(text: str) -> float:
    words = _word_count(text)
    if words >= 400:
        return 5.0
    if words >= 200:
        return 3.0
    if words >= 100:
        return 1.0
    return 0.0


# ── Bonus: Low Neutral Ratio (0 to −5 pts) ──────────────────────────
# If sentiment analysis shows very few neutral sentences, that's a
# slight red flag (everything is opinionated).

def _penalty_low_neutral(neutral_ratio: float) -> float:
    if neutral_ratio >= 0.4:
        return 0.0
    if neutral_ratio >= 0.25:
        return 2.0
    return 5.0


# ══════════════════════════════════════════════════════════════════════
#  Main scoring function
# ══════════════════════════════════════════════════════════════════════

def compute_reliability_score(
    text: str,
    *,
    claims: list[dict] | None = None,
    sentiment_score: float = 0.0,
    neutral_ratio: float = 0.5,
) -> dict:
    """Return ``{reliability_score, reliability_label, signals}``."""

    if not text or _word_count(text) < 10:
        return {
            "reliability_score": 50,
            "reliability_label": "Insufficient Text",
            "signals": {},
        }

    claims = claims or []

    # ── Positive signals (earn points above baseline) ───────────────
    s_attribution = _score_attribution(text)          # 0–15
    s_numerical = _score_numerical_evidence(text)     # 0–10
    s_hedging = _score_hedging(text)                  # 0–8
    s_balance = _score_balance(text)                  # 0–10
    s_factual = _score_factual_density(text)          # 0–7
    s_length = _bonus_length(text)                    # 0–5
    # max positive = 55

    # ── Negative signals (lose points below baseline) ───────────────
    p_hype = _penalty_hype(text)                      # 0–20
    p_claims = _penalty_claims(claims, text)           # 0–15
    p_sentiment = _penalty_sentiment_extreme(sentiment_score)  # 0–10
    p_urgency = _penalty_urgency(text)                # 0–10
    p_formatting = _penalty_formatting(text)          # 0–10
    p_neutral = _penalty_low_neutral(neutral_ratio)   # 0–5
    # max negative = 70

    total_positive = (
        s_attribution + s_numerical + s_hedging
        + s_balance + s_factual + s_length
    )
    total_negative = (
        p_hype + p_claims + p_sentiment
        + p_urgency + p_formatting + p_neutral
    )

    # Baseline 50: good articles climb toward 100, bad ones fall toward 0.
    raw = 50 + total_positive - total_negative
    score = max(0, min(100, int(round(raw))))

    # ── Label ───────────────────────────────────────────────────────
    if score >= 75:
        label = "Highly Reliable"
    elif score >= 55:
        label = "Generally Reliable"
    elif score >= 40:
        label = "Mixed Reliability"
    elif score >= 20:
        label = "Unreliable"
    else:
        label = "Very Unreliable"

    signals = {
        "source_attribution": round(s_attribution, 1),
        "numerical_evidence": round(s_numerical, 1),
        "hedging_language": round(s_hedging, 1),
        "balanced_perspective": round(s_balance, 1),
        "factual_density": round(s_factual, 1),
        "article_length": round(s_length, 1),
        "hype_penalty": round(-p_hype, 1),
        "claims_penalty": round(-p_claims, 1),
        "sentiment_extreme": round(-p_sentiment, 1),
        "urgency_penalty": round(-p_urgency, 1),
        "formatting_penalty": round(-p_formatting, 1),
        "neutral_ratio_penalty": round(-p_neutral, 1),
    }

    return {
        "reliability_score": score,
        "reliability_label": label,
        "signals": signals,
    }
