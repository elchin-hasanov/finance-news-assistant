"""Article reliability scoring — comprehensive multi-signal assessment.

Produces a 0–100 score where:
  80–100  = highly reliable / factual
  60–79   = mostly reliable with some caution
  40–59   = mixed / proceed with caution
  20–39   = unreliable / heavily hyped
   0–19   = extremely unreliable / likely clickbait

Signals (each weighted):
  ── Positive (increase reliability) ──
  1. Source attribution density   — how many claims cite sources
  2. Hedging / nuance language    — "however", "on the other hand", etc.
  3. Numerical evidence density   — concrete verifiable data points
  4. Neutral sentiment ratio      — factual tone
  5. Balanced perspective         — both positive and negative viewpoints

  ── Negative (decrease reliability) ──
  6. Hype word density            — sensational / clickbait language
  7. Sensational claim density    — high-scoring claims per sentence
  8. Speculation density          — "could", "might", "expected to" language
  9. Emotional intensity          — exclamation marks, ALL CAPS, superlatives
 10. Vague sourcing               — "sources say", "experts believe" without specifics
"""

from __future__ import annotations

import re
import math

from .text_utils import split_sentences, normalize_whitespace
from .hype import score_hype


# ── Attribution (positive signal) ──────────────────────────────────

_STRONG_ATTRIBUTION_RE = re.compile(
    r"\b(?:according\s+to\s+(?:the\s+)?(?:SEC|FDA|Federal|Bureau|Department|"
    r"Treasury|Reuters|Bloomberg|AP|Associated\s+Press|Wall\s+Street\s+Journal|"
    r"Financial\s+Times|company|filing|report|statement|data|study|research|"
    r"survey|analysis|audit|disclosure|prospectus|annual\s+report|10-[KQ])"
    r"|(?:SEC|regulatory|official)\s+filing[s]?\s+(?:show|reveal|indicate)"
    r"|data\s+from\s+\w+"
    r"|(?:as\s+)?reported\s+by\s+\w+"
    r"|(?:based\s+on|citing)\s+(?:data|research|filings?|reports?|analysis))\b",
    re.I,
)

_VAGUE_ATTRIBUTION_RE = re.compile(
    r"\b(?:sources?\s+(?:say|said|claim|suggest|indicate|report|familiar)"
    r"|(?:some|many|several)\s+(?:experts?|analysts?|observers?|insiders?)"
    r"\s+(?:say|said|believe|think|expect|predict|suggest)"
    r"|(?:it\s+is\s+(?:said|believed|thought|rumou?red|reported))"
    r"|(?:reportedly|allegedly|apparently|purportedly)"
    r"|(?:people\s+familiar\s+with(?:\s+the)?\s+matter)"
    r"|(?:unnamed|anonymous)\s+(?:source|official))\b",
    re.I,
)

# ── Hedging / nuance (positive signal) ─────────────────────────────

_HEDGING_RE = re.compile(
    r"\b(?:however|nevertheless|nonetheless|on\s+the\s+other\s+hand"
    r"|conversely|in\s+contrast|although|though|while\s+(?:this|that|some)"
    r"|that\s+said|to\s+be\s+fair|it(?:'s|\s+is)\s+worth\s+noting"
    r"|it\s+should\s+be\s+noted|caveat|nuance[ds]?|balanced|mixed"
    r"|both\s+(?:sides|perspectives|views)|counterpoint"
    r"|on\s+balance|at\s+the\s+same\s+time)\b",
    re.I,
)

# ── Speculation (negative signal) ──────────────────────────────────

_SPECULATION_RE = re.compile(
    r"\b(?:could|may|might|expected\s+to|predicted\s+to|set\s+to"
    r"|poised\s+to|likely\s+to|probably|possibly|potentially"
    r"|rumou?r(?:s|ed)?|speculate[ds]?|speculation|unconfirmed"
    r"|unverified|if\s+(?:this|that|the)\s+(?:happens?|materializ))\b",
    re.I,
)

# ── Emotional intensity markers ────────────────────────────────────

_SUPERLATIVE_EXTREME_RE = re.compile(
    r"\b(?:ever|biggest|largest|worst|best|highest|lowest|most|least"
    r"|first\s+(?:ever|time|in\s+history)|record[-\s]?breaking"
    r"|all[-\s]?time|never\s+(?:before|seen)|unprecedented"
    r"|historic(?:al)?|catastrophic|devastating|extraordinary"
    r"|unbelievable|incredible|shocking|stunning|jaw[-\s]?dropping"
    r"|mind[-\s]?blowing|insane|crazy)\b",
    re.I,
)

# ── Concrete numbers (positive signal) ─────────────────────────────

_CONCRETE_NUMBER_RE = re.compile(
    r"(?:\$\s?\d[\d,.]*\s*(?:million|billion|trillion|[MBT])?"
    r"|\d[\d,.]*\s*%"
    r"|\d[\d,.]*\s+(?:million|billion|trillion)"
    r"|\bEPS\s+(?:of\s+)?\$?\d"
    r"|\brevenue\s+(?:of\s+)?\$?\d"
    r"|\bQ[1-4]\s+\d{4})",
    re.I,
)

# ── Urgency / pressure language (negative) ─────────────────────────

_URGENCY_RE = re.compile(
    r"\b(?:act\s+now|buy\s+now|sell\s+(?:now|immediately|everything)"
    r"|don'?t\s+miss|last\s+chance|limited\s+time|hurry"
    r"|before\s+it(?:'s|\s+is)\s+too\s+late|you\s+(?:must|need\s+to|have\s+to)"
    r"|warning|alert|urgent)\b",
    re.I,
)


def compute_reliability_score(
    text: str,
    *,
    hype_score: int | None = None,
    claims: list[dict] | None = None,
    sentiment_score: float | None = None,
    neutral_ratio: float | None = None,
) -> dict:
    """Compute a comprehensive reliability score for an article.

    Returns a dict with:
      - reliability_score: 0–100 (higher = more reliable)
      - reliability_label: human-readable label
      - signals: dict of individual signal scores and explanations
    """
    text = normalize_whitespace(text or "")
    sentences = split_sentences(text)
    n_sentences = max(1, len(sentences))

    # ── 1. Source attribution density (0–15 pts) ───────────────────
    strong_attr = len(_STRONG_ATTRIBUTION_RE.findall(text))
    vague_attr = len(_VAGUE_ATTRIBUTION_RE.findall(text))
    # Strong attributions help; vague ones are slightly negative
    attr_ratio = strong_attr / n_sentences
    attr_score = min(15.0, attr_ratio * 60)  # ~25% sentences attributed → full 15
    attr_score -= min(5.0, vague_attr * 1.5)  # vague sourcing penalty
    attr_score = max(0.0, attr_score)

    # ── 2. Hedging / nuance language (0–10 pts) ────────────────────
    hedge_count = len(_HEDGING_RE.findall(text))
    hedge_ratio = hedge_count / n_sentences
    hedge_score = min(10.0, hedge_ratio * 40)

    # ── 3. Numerical evidence density (0–10 pts) ──────────────────
    concrete_nums = len(_CONCRETE_NUMBER_RE.findall(text))
    num_ratio = concrete_nums / n_sentences
    num_score = min(10.0, num_ratio * 25)

    # ── 4. Neutral sentiment (0–15 pts) ────────────────────────────
    # Higher neutral_ratio → more factual → more reliable
    nr = neutral_ratio if neutral_ratio is not None else 0.5
    sentiment_s = sentiment_score if sentiment_score is not None else 0.0
    # Extreme sentiment (positive or negative) reduces reliability
    sentiment_extremity = abs(sentiment_s)
    neutral_score = nr * 12 + (1 - sentiment_extremity) * 3

    # ── 5. Balanced perspective (0–10 pts) ─────────────────────────
    # Check if article presents multiple viewpoints
    has_positive = bool(re.search(r"\b(?:growth|positive|gains?|strong|upside|bullish|opportunity)\b", text, re.I))
    has_negative = bool(re.search(r"\b(?:risk|concern|decline|weak|downside|bearish|challenge)\b", text, re.I))
    balance_score = 7.0 if (has_positive and has_negative) else 2.0
    balance_score += min(3.0, hedge_count * 0.5)
    balance_score = min(10.0, balance_score)

    # ── 6. Hype word density penalty (0–15 pts deduction) ──────────
    if hype_score is None:
        hype_score, _, _ = score_hype(text)
    # hype_score is 0–100; map to 0–15 penalty
    hype_penalty = (hype_score / 100) * 15

    # ── 7. Sensational claim density penalty (0–10 pts deduction) ──
    if claims is not None:
        high_claims = sum(1 for c in claims if (c.get("sensational_score") or 0) >= 4.0)
        claim_density = high_claims / n_sentences
        claim_penalty = min(10.0, claim_density * 80)
    else:
        claim_penalty = 0.0

    # ── 8. Speculation density penalty (0–10 pts deduction) ────────
    spec_count = len(_SPECULATION_RE.findall(text))
    spec_ratio = spec_count / n_sentences
    spec_penalty = min(10.0, spec_ratio * 30)

    # ── 9. Emotional intensity penalty (0–10 pts deduction) ────────
    exclaim_count = text.count("!")
    caps_words = len(re.findall(r"\b[A-Z]{4,}\b", text))
    superlatives = len(_SUPERLATIVE_EXTREME_RE.findall(text))
    emotional_raw = (exclaim_count * 1.5) + (caps_words * 1.0) + (superlatives * 1.5)
    emotional_penalty = min(10.0, (emotional_raw / n_sentences) * 8)

    # ── 10. Urgency / pressure penalty (0–5 pts deduction) ─────────
    urgency_count = len(_URGENCY_RE.findall(text))
    urgency_penalty = min(5.0, urgency_count * 2.5)

    # ── Composite score ────────────────────────────────────────────
    positive_total = attr_score + hedge_score + num_score + neutral_score + balance_score
    negative_total = hype_penalty + claim_penalty + spec_penalty + emotional_penalty + urgency_penalty

    # Base score starts at 50 (neutral) and shifts based on signals
    # Positive signals add up to ~60, negative subtract up to ~50
    raw_score = 50 + (positive_total - 50) * 0.5 + (negative_total) * -1.0
    # Also blend in the positive signals directly
    raw_score = positive_total * 1.5 - negative_total * 1.0 + 10  # baseline of 10

    # Clamp to 0–100
    score = max(0, min(100, round(raw_score)))

    # ── Label ──────────────────────────────────────────────────────
    if score >= 80:
        label = "Highly Reliable"
    elif score >= 60:
        label = "Generally Reliable"
    elif score >= 40:
        label = "Mixed — Proceed with Caution"
    elif score >= 20:
        label = "Unreliable — Heavily Hyped"
    else:
        label = "Very Unreliable — Likely Clickbait"

    return {
        "reliability_score": score,
        "reliability_label": label,
        "signals": {
            "source_attribution": round(attr_score, 1),
            "hedging_nuance": round(hedge_score, 1),
            "numerical_evidence": round(num_score, 1),
            "neutral_tone": round(neutral_score, 1),
            "balanced_perspective": round(balance_score, 1),
            "hype_penalty": round(-hype_penalty, 1),
            "sensational_claims_penalty": round(-claim_penalty, 1),
            "speculation_penalty": round(-spec_penalty, 1),
            "emotional_intensity_penalty": round(-emotional_penalty, 1),
            "urgency_penalty": round(-urgency_penalty, 1),
        },
    }
