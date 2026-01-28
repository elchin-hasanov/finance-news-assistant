from __future__ import annotations

import json
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from ..settings import get_settings
from .text_utils import normalize_whitespace


_PAYWALL_HINT_RE = re.compile(r"subscribe|sign in|sign-in|paywall|subscription|metered", re.I)


_BOILERPLATE_RE = re.compile(
    r"\b(\n|\r|\t|\s)*(subscribe|sign in|create (a )?free account|watchlist|podcasts|pro\b|terms|privacy|cookie|cookies|advertis|share via|facebook|twitter|linkedin|email|menu|livestream|latest video)\b",
    re.I,
)


_JUNK_LINE_RE = re.compile(
    r"(?im)^(?:\s*(?:watch\s+live|markets|investing|tech|media|politics|video|live|watch|search|skip\s+navigation|read\s+more|more\s+from|related|trending|copyright|all\s+rights\s+reserved)\s*)$"
)


def _extract_json_ld_article_text(soup: BeautifulSoup) -> str | None:
    """Try to extract article body from JSON-LD blocks.

    Many publisher pages include structured data with `articleBody`.
    """

    scripts = soup.find_all("script", attrs={"type": re.compile(r"application/(ld\+json|json)\b", re.I)})
    for s in scripts:
        raw = s.string
        if not raw:
            continue
        raw = raw.strip()
        if len(raw) < 10:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        candidates: list[dict] = []
        if isinstance(payload, dict):
            candidates.append(payload)
            if isinstance(payload.get("@graph"), list):
                candidates.extend([x for x in payload["@graph"] if isinstance(x, dict)])
        elif isinstance(payload, list):
            candidates.extend([x for x in payload if isinstance(x, dict)])

        for obj in candidates:
            t = (obj.get("@type") or "")
            types: list[str]
            if isinstance(t, list):
                types = [str(x) for x in t]
            else:
                types = [str(t)]

            if not any(str(tt).strip().lower() in {"newsarticle", "article", "report", "analysis"} for tt in types):
                continue

            body = obj.get("articleBody")
            if isinstance(body, str):
                body = normalize_whitespace(body)
                if len(body) > 40:
                    return body

            # Some sites store paragraphs in an array.
            body2 = obj.get("text")
            if isinstance(body2, str):
                body2 = normalize_whitespace(body2)
                if len(body2) > 40:
                    return body2

    return None


def _paragraph_text_from(container) -> str:
    ps = container.find_all(["p", "li"])
    parts: list[str] = []
    for p in ps:
        t = normalize_whitespace(p.get_text(" "))
        if len(t) < 40:
            continue
        if _BOILERPLATE_RE.search(t):
            continue
        if _JUNK_LINE_RE.search(t):
            continue
        parts.append(t)
    return normalize_whitespace("\n\n".join(parts))


def _best_paragraph_container(soup: BeautifulSoup) -> str | None:
    """Fallback extraction: pick container with best paragraph density."""

    # Candidate selectors commonly used for content.
    selectors = [
        "article",
        "main",
        "[role='main']",
        "div[itemprop='articleBody']",
        "div[class*='article']",
        "div[class*='content']",
        "div[class*='body']",
        "section[class*='article']",
    ]

    best_text = ""
    best_score = -1

    for sel in selectors:
        for node in soup.select(sel):
            txt = _paragraph_text_from(node)
            if len(txt) < 300:
                continue

            p_count = len(node.find_all("p"))
            score = len(txt) + 200 * min(p_count, 20)
            if score > best_score:
                best_score = score
                best_text = txt

    if best_text and len(best_text) > 400:
        return best_text
    return None


def _domain(url: str) -> str | None:
    try:
        return urlparse(url).netloc or None
    except Exception:
        return None


def fetch_url(url: str) -> tuple[str, dict]:
    settings = get_settings()
    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        # Some sites return alternate content unless a plausible referer is present.
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }

    with httpx.Client(
        follow_redirects=True,
        timeout=settings.http_timeout_seconds,
        headers=headers,
    ) as client:
        r = client.get(url)

    status = r.status_code
    if status in {401, 403, 409, 429}:
        raise FetchBlockedError(f"Fetch blocked with HTTP {status}.")
    if status >= 400:
        raise FetchFailedError(f"Fetch failed with HTTP {status}.")

    text = r.text or ""
    if _PAYWALL_HINT_RE.search(text[:20000]):
        raise FetchBlockedError("Page looks paywalled or requires sign-in.")

    meta = {"url": url, "domain": _domain(url)}
    return text, meta


class FetchBlockedError(RuntimeError):
    pass


class FetchFailedError(RuntimeError):
    pass


def extract_article_text(html: str) -> tuple[str, str | None, str | None]:
    soup = BeautifulSoup(html, "lxml")

    # Extract JSON-LD before stripping script tags.
    jsonld_text = _extract_json_ld_article_text(soup)

    for tag in soup(["style", "nav", "footer", "aside", "noscript"]):
        tag.decompose()

    title = None
    if soup.title and soup.title.string:
        title = normalize_whitespace(soup.title.string)

    publish_date = None
    # Common meta tags
    for key in [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "article:published_time"}),
        ("meta", {"name": "pubdate"}),
        ("meta", {"name": "date"}),
        ("time", {}),
    ]:
        el = soup.find(key[0], key[1])
        if not el:
            continue
        if el.name == "time":
            dt = el.get("datetime") or el.get_text(" ")
        else:
            dt = el.get("content")
        if dt:
            publish_date = normalize_whitespace(dt)[:10]
            break

    if jsonld_text:
        return jsonld_text, title, publish_date

    # Prefer <article> but only keep paragraph-like content.
    article = soup.find("article")
    if article:
        text = _paragraph_text_from(article)
        if len(text) > 400:
            return text, title, publish_date

    # Next: choose best content-ish container by paragraph density.
    dense = _best_paragraph_container(soup)
    if dense:
        return dense, title, publish_date

    # Last resort: largest text block among candidate containers, filtered by boilerplate regex.
    candidates = soup.find_all(["main", "div", "section"]) or []
    best = ""
    best_score = -1
    for c in candidates:
        t = normalize_whitespace(c.get_text(" "))
        if len(t) < 400:
            continue
        if _BOILERPLATE_RE.search(t[:2000]):
            # If there are many boilerplate markers near the top, penalize.
            score = len(t) - 500
        else:
            score = len(t)
        if score > best_score:
            best_score = score
            best = t

    if len(best) > 400:
        return best, title, publish_date

    return normalize_whitespace(soup.get_text(" ")), title, publish_date


def newspaper_fallback(url: str) -> tuple[str, str | None, str | None]:
    try:
        from newspaper import Article

        a = Article(url)
        a.download()
        a.parse()
        text = normalize_whitespace(a.text or "")
        title = normalize_whitespace(a.title) if a.title else None
        publish_date = a.publish_date.date().isoformat() if a.publish_date else None
        return text, title, publish_date
    except Exception:
        return "", None, None
