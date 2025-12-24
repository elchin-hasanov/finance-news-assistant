from __future__ import annotations

from fastapi import HTTPException

from ..models import (
    AnalyzeRequest,
    AnalyzeResponse,
    Claim,
    ContentInfo,
    EntitiesInfo,
    HypeInfo,
    HypeWordCount,
    MarketInfo,
    SourceInfo,
)
from .claims import extract_claims
from .entities import (
    choose_primary_ticker,
    extract_companies,
    extract_tickers,
    infer_company_tickers,
    infer_ticker_aliases,
)
from .fetching import FetchBlockedError, FetchFailedError, extract_article_text, fetch_url, newspaper_fallback
from .hype import score_hype
from .market import fetch_market_context, fetch_markets_context
from .text_utils import normalize_whitespace
from .summary import facts_only_summary


def analyze_article(req: AnalyzeRequest) -> AnalyzeResponse:
    raw_text = req.text or ""
    extracted_text = ""

    source_url = req.url
    title = None
    domain = None
    publish_date = None

    if req.url:
        try:
            html, meta = fetch_url(req.url)
            domain = meta.get("domain")
            extracted_text, title, publish_date = extract_article_text(html)

            if len(extracted_text) < 300:
                fb_text, fb_title, fb_date = newspaper_fallback(req.url)
                if len(fb_text) > len(extracted_text):
                    extracted_text = fb_text
                    title = title or fb_title
                    publish_date = publish_date or fb_date

            raw_text = extracted_text

        except FetchBlockedError as e:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "FETCH_BLOCKED",
                        "message": str(e),
                        "hint": "Paste text instead.",
                    }
                },
            )
        except FetchFailedError as e:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": {
                        "code": "FETCH_FAILED",
                        "message": str(e),
                        "hint": f"URL fetch failed for {domain or 'unknown domain'}. If the site blocks bots, paste text instead.",
                    }
                },
            )

    if req.text and not req.url:
        extracted_text = normalize_whitespace(req.text)
        raw_text = extracted_text

    extracted_text = normalize_whitespace(extracted_text or raw_text)
    raw_text = normalize_whitespace(raw_text)

    raw_tickers = extract_tickers(extracted_text)
    ticker_aliases = infer_ticker_aliases(extracted_text)

    # Add inferred tickers from aliases (e.g., BP) even if not in ticker syntax.
    for _, t in ticker_aliases.items():
        if t not in raw_tickers:
            raw_tickers.append(t)

    # Company-first approach: detect companies, resolve to tickers, and use those for market data.
    companies = extract_companies(extracted_text, raw_tickers)
    company_tickers = infer_company_tickers(companies, ticker_aliases)

    resolved_tickers: list[str] = []
    seen = set()
    for _, t in company_tickers.items():
        if t and t not in seen:
            seen.add(t)
            resolved_tickers.append(t)

    # Fallback to raw tickers only if we couldn't resolve any company->ticker.
    tickers = resolved_tickers if resolved_tickers else raw_tickers
    primary_ticker = choose_primary_ticker(tickers)

    market_res = fetch_market_context(primary_ticker)
    markets_res = fetch_markets_context(tickers)

    claims_raw = extract_claims(extracted_text, limit=10)
    claims = [Claim(**c) for c in claims_raw]

    hype_score, hype_words, ratio = score_hype(extracted_text)

    facts_summary = facts_only_summary(
        extracted_text,
        primary_ticker=primary_ticker,
        day_move_pct=market_res.day_move_pct,
        claims=claims_raw,
    )

    return AnalyzeResponse(
        source=SourceInfo(
            url=source_url,
            title=title,
            domain=domain,
            publish_date=publish_date,
        ),
        content=ContentInfo(raw_text=raw_text, extracted_text=extracted_text),
        entities=EntitiesInfo(
            companies=companies,
            tickers=tickers,
            ticker_aliases={k: v for k, v in ticker_aliases.items()},
            company_tickers={k: v for k, v in company_tickers.items()},
            primary_ticker=primary_ticker,
        ),
        market=MarketInfo(
            primary_ticker=primary_ticker,
            price_series=market_res.price_series,
            day_move_pct=market_res.day_move_pct,
            vol_20d=market_res.vol_20d,
            move_zscore=market_res.move_zscore,
        ),
        markets=[
            {
                "ticker": m.ticker,
                "price_series": m.price_series,
                "day_move_pct": m.day_move_pct,
                "vol_20d": m.vol_20d,
                "move_zscore": m.move_zscore,
            }
            for m in markets_res
        ],
        claims=claims,
        hype=HypeInfo(
            score_0_100=hype_score,
            ratio=ratio,
            hype_words=[HypeWordCount(word=w, count=c) for w, c in hype_words],
        ),
        facts_only_summary=facts_summary,
    )
