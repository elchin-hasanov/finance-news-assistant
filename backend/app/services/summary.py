from __future__ import annotations

import re

from .text_utils import split_sentences


_EMOTION_STOP = {
    "incredible",
    "incredibly",
    "shocking",
    "shocked",
    "massive",
    "huge",
    "wild",
    "crazy",
    "insane",
    "unbelievable",
    "stunning",
    "jaw-dropping",
    "record",
    "record-breaking",
    "astonishing",
    "dramatically",
    "dramatic",
    "extremely",
    "remarkably",
    "surprisingly",
    "soaring",
    "plunging",
}


def _de_emote(sentence: str) -> str:
    words = sentence.split()
    cleaned = []
    for w in words:
        key = re.sub(r"[^A-Za-z\-]", "", w).lower()
        if key in _EMOTION_STOP:
            continue
        cleaned.append(w)
    return " ".join(cleaned)


def facts_only_summary(
    text: str,
    primary_ticker: str | None,
    day_move_pct: float | None,
    claims: list[dict],
) -> str:
    sents = split_sentences(text)

    out: list[str] = []
    if primary_ticker:
        if day_move_pct is not None:
            out.append(f"{primary_ticker} moved {day_move_pct:.2f}% in the most recent session.")
        else:
            out.append(f"The article discusses {primary_ticker}.")

    # Prefer up to 3 claim sentences
    for c in claims[:3]:
        out.append(_de_emote(c["evidence_sentence"]))

    # Backfill with early neutral sentences if we lack content
    if len(out) < 3:
        for s in sents[:6]:
            s2 = _de_emote(s)
            if s2 and s2 not in out:
                out.append(s2)
            if len(out) >= 4:
                break

    out = [s.strip() for s in out if s.strip()]
    out = out[:6]
    return " ".join(out)
