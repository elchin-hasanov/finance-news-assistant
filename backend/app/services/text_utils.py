from __future__ import annotations

import re


_WS_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = _WS_RE.sub(" ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    # Lightweight sentence splitter; good enough for deterministic extraction.
    text = normalize_whitespace(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\(\[])", text)
    return [p.strip() for p in parts if p.strip()]
