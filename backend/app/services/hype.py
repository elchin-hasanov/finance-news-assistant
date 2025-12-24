from __future__ import annotations

import re
from collections import Counter


HYPE_WORDS = [
    # Price action / trading hype
    "soar",
    "soars",
    "soared",
    "surge",
    "surges",
    "surged",
    "rocket",
    "rockets",
    "rocketed",
    "rip",
    "rips",
    "ripped",
    "skyrocket",
    "skyrockets",
    "skyrocketed",
    "explode",
    "explodes",
    "exploded",
    "moon",
    "moonshot",
    "parabolic",
    "meltup",
    "melt-up",
    "breakout",
    "breakouts",
    "rip-roaring",
    "riproaring",
    "rip-roar",
    "rally",
    "rallies",
    "rallied",
    "stampede",
    "frenzy",
    "mania",
    "feeding",
    "buying",

    # Downside panic
    "plunge",
    "plunges",
    "plunged",
    "crash",
    "crashes",
    "crashed",
    "tank",
    "tanks",
    "tanked",
    "collapse",
    "collapses",
    "collapsed",
    "meltdown",
    "bloodbath",
    "panic",
    "capitulation",
    "wipeout",
    "wipe-out",
    "wrecked",

    # Strong adjectives / sensational framing
    "shocking",
    "stunning",
    "unbelievable",
    "jawdropping",
    "jaw-dropping",
    "mindblowing",
    "mind-blowing",
    "massive",
    "huge",
    "giant",
    "monster",
    "epic",
    "insane",
    "wild",
    "crazy",
    "legendary",
    "nuclear",
    "bananas",
    "ridiculous",
    "outrageous",
    "astonishing",
    "incredible",
    "unprecedented",
    "historic",
    "record",
    "recordbreaking",
    "record-breaking",
    "blockbuster",

    # Hype / pump language
    "gamechanging",
    "game-changing",
    "machine",
    "dominate",
    "dominates",
    "dominant",
    "destroys",
    "crushes",
    "smashes",
    "blowout",
    "bombshell",
    "slam",
    "slams",
    "slammed",
    "mustbuy",
    "must-buy",
    "cantlose",
    "can't-lose",
    "no-brainer",
    "guaranteed",
    "surething",
    "sure-thing",
    "easy",
    "free",

    # Urgency / emotional triggers
    "urgent",
    "now",
    "immediately",
    "instantly",
    "rightnow",
    "right-now",
    "warning",
    "alert",
    "boom",
    "bust",
]

# Multi-word phrases are often stronger signals than single tokens.
HYPE_PHRASES = [
    "to the moon",
    "once in a lifetime",
    "could explode",
    "set to explode",
    "massive upside",
    "huge upside",
    "buy now",
    "you can't lose",
    "can't lose",
    "no brainer",
    "sure thing",
    "blood in the streets",
    "sell everything",
    "panic selling",
    "record high",
    "record low",
]

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']+")


def score_hype(text: str) -> tuple[int, list[tuple[str, int]], float]:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    total = len(words)
    if total == 0:
        return 0, [], 0.0

    hype_set = set(HYPE_WORDS)
    hype_hits = [w for w in words if w in hype_set]
    counts = Counter(hype_hits)
    hype_count = sum(counts.values())

    # Phrase matches (case-insensitive) count as extra "hype hits".
    lower = text.lower()
    phrase_hits = 0
    for p in HYPE_PHRASES:
        # Count non-overlapping occurrences.
        if not p:
            continue
        phrase_hits += lower.count(p)

    # Primary signal: % of hype tokens in the text (bounded and then mapped to 0..70).
    # Using a gentle non-linearity keeps the score from being almost always 0 or 100.
    ratio = hype_count / total
    base = int(round(min(0.08, ratio) / 0.08 * 70))  # 8% hype tokens -> 70 points

    # Bonuses: phrases, exclamation points, ALL CAPS shouting.
    phrase_bonus = min(15, phrase_hits * 5)
    exclaim_bonus = min(8, text.count("!") * 2)
    caps_tokens = re.findall(r"\b[A-Z]{3,}\b", text)
    caps_bonus = min(12, len(caps_tokens))

    score = min(100, base + phrase_bonus + exclaim_bonus + caps_bonus)

    top = counts.most_common(8)
    return score, top, ratio
