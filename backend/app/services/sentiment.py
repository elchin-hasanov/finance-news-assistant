"""Sentiment analysis.

This replaces the previous lexicon-only approach with a modern transformer model
when available.

Model choice (default):
- `ProsusAI/finbert`

Why:
- Small-ish, widely used, easy to run on CPU.
- Provides a stable 3-class distribution (negative/neutral/positive).

Fallbacks:
- If transformers/torch isn't installed (or model fails to load), fall back to
    the legacy finance lexicon so the API never breaks.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import re
import os

# Positive sentiment words in finance context
POSITIVE_WORDS = {
    "profit", "profits", "profitable", "profitability",
    "growth", "growing", "grew", "gains", "gained",
    "strong", "stronger", "strength", "robust",
    "beat", "beats", "exceeded", "exceeds", "outperform", "outperformed",
    "success", "successful", "successfully",
    "improve", "improved", "improvement", "improvements",
    "increase", "increased", "increasing", "rises", "rose", "rising",
    "bullish", "positive", "upbeat", "optimistic",
    "recovery", "recover", "recovered", "rebound",
    "earnings", "revenue", "sales", "demand",
}

# Negative sentiment words in finance context
NEGATIVE_WORDS = {
    "loss", "losses", "losing", "lost",
    "decline", "declined", "declining", "decrease", "decreased",
    "fell", "fall", "falling", "drops", "dropped", "dropping",
    "weak", "weaker", "weakness", "poor", "disappointing",
    "miss", "missed", "underperform", "underperformed",
    "fail", "failed", "failure",
    "concern", "concerns", "worried", "worry", "worries",
    "risk", "risks", "risky", "uncertainty", "uncertain",
    "bearish", "negative", "pessimistic",
    "downturn", "recession", "crisis", "crash",
    "layoff", "layoffs", "bankruptcy", "debt",
}


def analyze_sentiment(text: str) -> dict[str, float | int]:
    """
    Analyze sentiment of financial text.
    
    Returns:
        dict with:
            - sentiment_score: -1.0 (very negative) to +1.0 (very positive)
            - positive_count: number of positive words
            - negative_count: number of negative words
            - neutral_ratio: proportion of text that is neutral
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return {
            "sentiment_score": 0.0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_ratio": 1.0,
        }

    # Keep legacy counts as *auxiliary* stats; do not use them to compute sentiment.
    tokens = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", cleaned.lower())
    positive_count = sum(1 for w in tokens if w in POSITIVE_WORDS)
    negative_count = sum(1 for w in tokens if w in NEGATIVE_WORDS)

    # Prefer transformer distribution.
    dist = _transformer_sentiment_dist(cleaned)
    if dist is not None:
        pos = float(dist.get("positive") or 0.0)
        neu = float(dist.get("neutral") or 0.0)
        neg = float(dist.get("negative") or 0.0)
        score = float(pos - neg)
        neutral_ratio = float(neu)
    else:
        # Lexicon fallback: calibrated to [-1, +1] and provide a reasonable neutral ratio proxy.
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
            neutral_ratio = 1.0
        else:
            score = (positive_count - negative_count) / float(total)
            # If there are few sentiment tokens relative to length, treat that as neutral-ish.
            neutral_ratio = max(0.0, min(1.0, 1.0 - (total / max(12.0, float(len(tokens))))))

    return {
        "sentiment_score": float(round(score, 3)),
        "positive_count": int(positive_count),
        "negative_count": int(negative_count),
        "neutral_ratio": float(round(neutral_ratio, 3)),
    }


@lru_cache(maxsize=1)
def _get_sentiment_pipeline():
    """Lazily load the HF pipeline only once per process."""
    # Render free/starter instances are memory constrained and can OOM when loading
    # torch/transformers models. Make this opt-in via env var.
    enable = os.getenv("ENABLE_TRANSFORMER_SENTIMENT", "0").strip().lower()
    if enable not in {"1", "true", "yes", "on"}:
        return None

    try:
        from transformers import pipeline

        return pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            top_k=None,
        )
    except Exception:
        return None


def _transformer_sentiment_score(text: str) -> float | None:
    """Return sentiment score in [-1, +1], or None if model unavailable."""
    pipe = _get_sentiment_pipeline()
    if pipe is None:
        return None

    try:
        # Truncate aggressively to keep latency bounded.
        txt = text
        if len(txt) > 6000:
            txt = txt[:6000]

        out: Any = pipe(txt)
        # Pipeline might return list[dict] or list[list[dict]] depending on top_k.
        if isinstance(out, list) and out and isinstance(out[0], list):
            dist = out[0]
        else:
            dist = out

        if not isinstance(dist, list):
            return None

        probs: dict[str, float] = {}
        for d in dist:
            label = str(d.get("label") or "").lower()
            score = float(d.get("score") or 0.0)
            probs[label] = score

        # Normalize label variants.
        # FinBERT typically returns: positive / neutral / negative.
        pos = probs.get("positive") or probs.get("label_2")
        neg = probs.get("negative") or probs.get("label_0")
        neu = probs.get("neutral") or probs.get("label_1")
        if pos is None or neg is None:
            return None

        # Map to [-1, +1] emphasizing net positivity.
        # (Neutral is implicitly handled by both pos/neg being low.)
        _ = neu  # may be present but unused
        return float(pos - neg)
    except Exception:
        return None


def _chunk_text(text: str, *, max_chars: int = 1400, overlap: int = 150) -> list[str]:
    """Split text into overlapping chunks to keep transformer latency bounded.

    FinBERT pipelines may truncate long inputs; chunking preserves coverage.
    """
    t = (text or "").strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [t]
    out: list[str] = []
    i = 0
    while i < len(t):
        j = min(len(t), i + max_chars)
        out.append(t[i:j])
        if j == len(t):
            break
        i = max(0, j - overlap)
    return out


def _transformer_sentiment_dist(text: str) -> dict[str, float] | None:
    """Return a calibrated probability distribution for (pos/neu/neg) or None."""
    pipe = _get_sentiment_pipeline()
    if pipe is None:
        return None

    try:
        chunks = _chunk_text(text)
        if not chunks:
            return None

        # Aggregate by chunk length (proxy for token count).
        w_sum = 0.0
        agg = {"positive": 0.0, "neutral": 0.0, "negative": 0.0}

        for ch in chunks[:8]:  # hard cap for latency
            out: Any = pipe(ch)
            dist = out[0] if isinstance(out, list) and out and isinstance(out[0], list) else out
            if not isinstance(dist, list):
                continue

            probs: dict[str, float] = {}
            for d in dist:
                label = str(d.get("label") or "").lower()
                score = float(d.get("score") or 0.0)
                probs[label] = score

            pos = float(probs.get("positive") or probs.get("label_2") or 0.0)
            neg = float(probs.get("negative") or probs.get("label_0") or 0.0)
            neu = float(probs.get("neutral") or probs.get("label_1") or 0.0)
            s = pos + neg + neu
            if s <= 0:
                continue
            pos, neg, neu = pos / s, neg / s, neu / s

            w = float(max(200, len(ch)))
            w_sum += w
            agg["positive"] += pos * w
            agg["negative"] += neg * w
            agg["neutral"] += neu * w

        if w_sum <= 0:
            return None

        out = {k: float(v / w_sum) for k, v in agg.items()}
        # Ensure exact sum=1-ish.
        s = out["positive"] + out["negative"] + out["neutral"]
        if s > 0:
            out = {k: float(v / s) for k, v in out.items()}
        return out
    except Exception:
        return None


def get_sentiment_label(score: float) -> str:
    """Convert numerical sentiment score to human-readable label."""
    # News sentiment tends to cluster near 0; keep 'Very' bands rare.
    if score >= 0.7:
        return "Very Positive"
    if score >= 0.25:
        return "Positive"
    if score > -0.25:
        return "Neutral"
    if score > -0.7:
        return "Negative"
    return "Very Negative"
