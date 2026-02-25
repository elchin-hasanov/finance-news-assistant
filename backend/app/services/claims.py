"""Sensational-claim extraction — v2.

Design goals
────────────
1. **Precision over recall** – only surface claims that are genuinely
   sensational, attention-grabbing, or contain unverified / exaggerated
   assertions.
2. **Objective multi-signal scoring** – six positive signals, three penalty
   signals, each 0-3 pts, combined into a 0-10 normalised score.
3. **Category tagging** – each claim gets a human-readable category so the
   extension popup can show *why* it was flagged.
4. **Strict year filtering** – bare years (2009, 2021, 2024) are NOT treated
   as noteworthy numbers unless they appear with both a temporal preposition
   AND a comparative/magnitude marker.  "In 2021, Apple tested…" ≠ sensational.
"""

from __future__ import annotations

import re

from .text_utils import split_sentences

# ---------------------------------------------------------------------------
# Number extraction
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(
    r"(?P<prefix>\$)?"
    r"(?P<num>\d+(?:,\d{3})*(?:\.\d+)?)"
    r"\s*(?P<suffix>%|[MBT]|million|billion|trillion)?",
    re.I,
)


def _parse_number(m: re.Match) -> tuple[float, str | None] | None:
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
        elif suf in {"b", "billion"}:
            unit = "billion" if unit is None else unit + " billion"
        elif suf in {"t", "trillion"}:
            unit = "trillion" if unit is None else unit + " trillion"

    return val, unit


def _extract_numbers(sentence: str) -> list[dict]:
    """Pull verifiable numbers; strict year filtering."""
    nums: list[dict] = []
    for m in _NUMBER_RE.finditer(sentence):
        parsed = _parse_number(m)
        if parsed is None:
            continue
        val, unit = parsed

        # Year filtering — keep only when temporal preposition + comparison
        if unit is None and 1900 <= val <= 2100:
            before = sentence[: m.start()].lower()
            has_preposition = bool(
                re.search(
                    r"\b(?:in|since|by|from|before|after|during|until)\s*$",
                    before,
                )
            )
            has_comparison = bool(
                re.search(
                    r"\b(?:first|biggest|largest|worst|best|highest|lowest"
                    r"|most|least|record|since|ever)\b",
                    sentence,
                    re.I,
                )
            )
            if not (has_preposition and has_comparison):
                continue

        nums.append({"value": val, "unit": unit})
    return nums


# ---------------------------------------------------------------------------
# Scoring signals  (each returns 0.0 – 3.0)
# ---------------------------------------------------------------------------

_DRAMATIC_RE = re.compile(
    r"\b(?:surge[ds]?|soar(?:s|ed|ing)?|plunge[ds]?|crash(?:es|ed|ing)?"
    r"|plummet(?:s|ed|ing)?|skyrocket(?:s|ed|ing)?|tank(?:s|ed|ing)?"
    r"|collapse[ds]?|spike[ds]?|explode[ds]?|crater(?:s|ed|ing)?"
    r"|tumble[ds]?|wipe[ds]?\s+out|double[ds]?|triple[ds]?|halve[ds]?)\b",
    re.I,
)

_SUPERLATIVE_RE = re.compile(
    r"\b(?:biggest|largest|worst|best|highest|lowest|most|least|first|last)"
    r"\s+(?:ever|in\s+\d+\s+years?|since\s+\d{4}|in\s+history|on\s+record)\b",
    re.I,
)

_SPECULATIVE_RE = re.compile(
    r"\b(?:could|may|might|expected\s+to|predicted\s+to|set\s+to|poised\s+to)"
    r"\s+(?:crash|collapse|surge|soar|plunge|double|triple|reach|hit|exceed"
    r"|fall|drop|rise|skyrocket|plummet)\b",
    re.I,
)

_DISTRESS_RE = re.compile(
    r"\b(?:bankrupt(?:cy)?|insolven[ct]|default(?:s|ed)?|layoff[s]?"
    r"|laid\s+off|cut\s+\d|fire[ds]?\s+\d|eliminat|shut(?:ting)?\s+down"
    r"|wind(?:ing)?\s+down|crisis|catastroph|disaster|turmoil|panic"
    r"|meltdown)\b",
    re.I,
)

_HYPE_RE = re.compile(
    r"\b(?:game[-\s]?changer|revolutionary|disruptive?"
    r"|transformative?|breakthrough|unprecedented|paradigm\s+shift"
    r"|moon(?:shot)?)\b",
    re.I,
)

_AMPLIFIER_RE = re.compile(
    r"\b(?:record|historic|massive|huge|enormous|staggering|shocking"
    r"|stunning|remarkable)\b",
    re.I,
)


def _score_dramatic(s: str) -> float:
    return min(3.0, len(_DRAMATIC_RE.findall(s)) * 1.5)


def _score_magnitude(s: str, nums: list[dict]) -> float:
    score = 0.0
    for n in nums:
        u = n.get("unit") or ""
        v = n["value"]
        if "%" in u:
            if v >= 50:
                score += 3.0
            elif v >= 20:
                score += 2.0
            elif v >= 10:
                score += 1.0
            elif v >= 5:
                score += 0.5
        if "billion" in u or "trillion" in u:
            score += 1.5
        if "$" in u and v >= 100:
            score += 0.5
    return min(3.0, score)


def _score_superlative(s: str) -> float:
    return 3.0 if _SUPERLATIVE_RE.search(s) else 0.0


def _score_speculative(s: str) -> float:
    return 2.5 if _SPECULATIVE_RE.search(s) else 0.0


def _score_distress(s: str) -> float:
    return min(3.0, len(_DISTRESS_RE.findall(s)) * 1.5)


def _score_hype(s: str) -> float:
    return min(3.0, len(_HYPE_RE.findall(s)) * 2.0)


def _score_amplifier(s: str) -> float:
    return min(2.0, len(_AMPLIFIER_RE.findall(s)) * 1.0)


# Penalties (negative) -------------------------------------------------------

_ROUTINE_RE = re.compile(
    r"(?:"
    r"^\s*(?:the\s+)?company\s+(?:reported|announced|said|stated)\s+"
    r"(?:that\s+)?(?:its\s+)?(?:Q\d|quarterly|annual)"
    r"|^\s*(?:according\s+to|based\s+on|as\s+of|for\s+the\s+(?:quarter|year))"
    r"|^\s*(?:revenue|earnings|net\s+income|EPS)\s+(?:was|were|came\s+in\s+at)"
    r"|^\s*shares\s+(?:are\s+)?(?:trading|traded)\s+at"
    r")",
    re.I,
)

_ATTRIBUTION_RE = re.compile(
    r"\b(?:according\s+to\s+(?:SEC|regulatory|official)|as\s+reported\s+by"
    r"|data\s+(?:from|shows?|indicates?)|filings?\s+(?:show|reveal|indicate))\b",
    re.I,
)

_HISTORICAL_RECAP_RE = re.compile(
    r"\b(?:in\s+\d{4}\s*,|back\s+in\s+\d{4}|years?\s+ago|previously"
    r"|at\s+the\s+time)\b",
    re.I,
)

# ── v3 enrichment regexes ─────────────────────────────────────────

_OFFICIAL_SOURCE_RE = re.compile(
    r"\b(?:according\s+to\s+(?:the\s+)?(?:SEC|FDA|Federal|Bureau|Department|"
    r"Treasury|company|CEO|CFO|COO|CTO|president|chairman|board|10-[KQ]|"
    r"annual\s+report|filing|prospectus|disclosure|regulatory|official)|"
    r"(?:SEC|regulatory|official)\s+filing[s]?\s+(?:show|reveal|indicate)|"
    r"the\s+company\s+(?:said|stated|reported|confirmed|disclosed))\b",
    re.I,
)

_NAMED_SOURCE_RE = re.compile(
    r"\b(?:according\s+to\s+(?:Reuters|Bloomberg|AP|CNBC|WSJ|"
    r"Wall\s+Street\s+Journal|Financial\s+Times|Barron'?s|"
    r"MarketWatch|Moody'?s|S&P|Fitch|Goldman|Morgan\s+Stanley|"
    r"JPMorgan|Bank\s+of\s+America|Citigroup|analysts?\s+at\s+\w+)|"
    r"(?:as\s+)?reported\s+by\s+(?:Reuters|Bloomberg|AP|CNBC|WSJ)|"
    r"\b[A-Z][a-z]+\s+[A-Z][a-z]+,?\s+(?:an?\s+)?(?:analyst|economist|"
    r"strategist|portfolio\s+manager|CEO|CFO|CTO|director)\b)\b",
    re.I,
)

_VAGUE_SOURCE_RE = re.compile(
    r"\b(?:sources?\s+(?:say|said|claim|suggest|familiar)"
    r"|(?:some|many|several)\s+(?:experts?|analysts?|observers?|insiders?)"
    r"\s+(?:say|said|believe|think|expect)"
    r"|(?:it\s+is\s+(?:said|believed|thought|rumou?red|reported))"
    r"|(?:reportedly|allegedly|apparently|purportedly)"
    r"|(?:unnamed|anonymous)\s+(?:source|official))\b",
    re.I,
)

_EMOTIONAL_MARKERS_RE = re.compile(
    r"\b(?:shocking|stunning|unbelievable|incredible|jaw[-\s]?dropping"
    r"|mind[-\s]?blowing|insane|crazy|wild|epic|outrageous|ridiculous"
    r"|astonishing|extraordinary|devastating|catastrophic|nightmare"
    r"|amazing|fantastic|terrifying|horrifying)\b",
    re.I,
)

_VAGUE_LANGUAGE_RE = re.compile(
    r"\b(?:some\s+(?:people|analysts|experts)|many\s+(?:believe|think|say)"
    r"|it\s+(?:seems|appears)|there\s+(?:are|is)\s+(?:growing|increasing)"
    r"|(?:significant|substantial|considerable)\s+(?:amount|number|portion)"
    r"|(?:a\s+lot|lots)\s+of"
    r"|(?:various|numerous|countless|several)\s+(?:factors?|reasons?|issues?))\b",
    re.I,
)

_FORWARD_LOOKING_RE = re.compile(
    r"\b(?:could|may|might|will|expected\s+to|predicted\s+to|set\s+to"
    r"|poised\s+to|likely\s+to|forecast|outlook|projection|guidance"
    r"|forward[-\s]looking|going\s+forward|in\s+the\s+(?:coming|next)"
    r"|by\s+(?:2025|2026|2027|2028|2029|2030|year[-\s]end))\b",
    re.I,
)


def _penalty_routine(s: str) -> float:
    return -2.0 if _ROUTINE_RE.search(s) else 0.0


def _penalty_attribution(s: str) -> float:
    return -1.0 if _ATTRIBUTION_RE.search(s) else 0.0


def _penalty_historical(s: str) -> float:
    """Penalise sentences that purely recap old events."""
    if not _HISTORICAL_RECAP_RE.search(s):
        return 0.0
    # Don't penalise if there's also forward-looking language
    if re.search(r"\b(?:now|today|currently|going\s+forward|will|plan)\b", s, re.I):
        return 0.0
    return -1.5


# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------

_CATEGORY_MAP: list[tuple[re.Pattern, str]] = [
    (_SPECULATIVE_RE, "Prediction"),
    (_DISTRESS_RE, "Financial Distress"),
    (_HYPE_RE, "Hype / Buzzword"),
    (_SUPERLATIVE_RE, "Superlative"),
    (_DRAMATIC_RE, "Dramatic Language"),
]


def _classify(s: str) -> str:
    for rx, label in _CATEGORY_MAP:
        if rx.search(s):
            return label
    return "Quantitative Claim"


# ---------------------------------------------------------------------------
# v3 enrichment helpers
# ---------------------------------------------------------------------------

def _assess_source_quality(s: str) -> str:
    """Classify the source quality of a claim sentence."""
    if _OFFICIAL_SOURCE_RE.search(s):
        return "official"
    if _NAMED_SOURCE_RE.search(s):
        return "named"
    if _VAGUE_SOURCE_RE.search(s):
        return "vague"
    return "unattributed"


def _score_emotional_intensity(s: str) -> float:
    """Score emotional intensity 0–3."""
    hits = len(_EMOTIONAL_MARKERS_RE.findall(s))
    exclaim = s.count("!")
    caps = len(re.findall(r"\b[A-Z]{4,}\b", s))
    raw = hits * 1.0 + exclaim * 0.5 + caps * 0.3
    return min(3.0, raw)


def _score_vagueness(s: str) -> float:
    """Score how vague/unsubstantiated a claim is (0–3)."""
    vague_hits = len(_VAGUE_LANGUAGE_RE.findall(s))
    vague_source_hits = len(_VAGUE_SOURCE_RE.findall(s))
    # Concrete numbers reduce vagueness
    concrete = len(re.findall(
        r"(?:\$\s?\d[\d,.]*|\d[\d,.]*\s*%|\d[\d,.]*\s+(?:million|billion|trillion))",
        s, re.I,
    ))
    raw = (vague_hits + vague_source_hits) * 1.0 - concrete * 0.5
    return max(0.0, min(3.0, raw))


def _is_forward_looking(s: str) -> bool:
    """Check if a sentence is forward-looking / speculative."""
    return bool(_FORWARD_LOOKING_RE.search(s))


# ---------------------------------------------------------------------------
# Minimum-quality gate
# ---------------------------------------------------------------------------

_CLAIM_HINT_RE = re.compile(
    r"(\$\s?\d|\d\s?%|\b(?:million|billion|trillion)\b"
    r"|\bEPS\b|\brevenue\b|\bguidance\b|\bforecast\b"
    r"|\b(?:surge|plunge|crash|soar|skyrocket|plummet|record"
    r"|unprecedented|stunning|shocking|remarkable)\b)",
    re.I,
)


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

MAX_CLAIM_LENGTH = 200


def _truncate(text: str, max_len: int = MAX_CLAIM_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    t = text[:max_len]
    for end in [". ", "! ", "? "]:
        idx = t.rfind(end)
        if idx > max_len // 2:
            return t[: idx + 1].strip()
    for brk in [", ", " "]:
        idx = t.rfind(brk)
        if idx > max_len // 2:
            return t[:idx].strip() + "..."
    return t.strip() + "..."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_claims(text: str, limit: int = 10) -> list[dict]:
    """Extract and rank the most sensational claims from *text*.

    Returns a list of dicts with keys:
      claim, numbers, evidence_sentence, sensational_score, category,
      source_quality, emotional_intensity, vagueness_score, forward_looking
    """
    sentences = split_sentences(text)
    scored: list[tuple[float, dict]] = []

    for s in sentences:
        if not _CLAIM_HINT_RE.search(s):
            continue
        if len(s) < 30 or len(s) > 500:
            continue

        nums = _extract_numbers(s)

        # Composite score
        raw = (
            _score_dramatic(s)
            + _score_magnitude(s, nums)
            + _score_superlative(s)
            + _score_speculative(s)
            + _score_distress(s)
            + _score_hype(s)
            + _score_amplifier(s)
            + _penalty_routine(s)
            + _penalty_attribution(s)
            + _penalty_historical(s)
        )

        # Bonus for having concrete verifiable numbers (%, $, billion…)
        verifiable = sum(
            1
            for n in nums
            if n.get("unit") in {"%", "$", "$ million", "$ billion", "$ trillion",
                                  "million", "billion", "trillion"}
        )
        raw += verifiable * 0.5

        # Bonus for exclamation marks
        if "!" in s:
            raw += 0.5

        # v3: emotional intensity adds to score
        emotional = _score_emotional_intensity(s)
        raw += emotional * 0.5

        # v3: vague unattributed claims are *more* sensational (less trustworthy)
        vagueness = _score_vagueness(s)
        source_q = _assess_source_quality(s)
        if source_q == "unattributed" and vagueness >= 1.0:
            raw += 0.5
        # Well-attributed claims are less sensational
        if source_q in ("official", "named"):
            raw -= 1.0

        score = max(0.0, min(10.0, raw))

        # Raised threshold: only truly sensational claims (was 1.0, now 2.0)
        if score < 2.0:
            continue

        forward = _is_forward_looking(s)

        scored.append(
            (
                score,
                {
                    "claim": _truncate(s),
                    "numbers": nums,
                    "evidence_sentence": s,
                    "sensational_score": round(score, 2),
                    "category": _classify(s),
                    "source_quality": source_q,
                    "emotional_intensity": round(emotional, 2),
                    "vagueness_score": round(vagueness, 2),
                    "forward_looking": forward,
                },
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]
