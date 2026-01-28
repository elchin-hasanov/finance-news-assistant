from __future__ import annotations

from fastapi import HTTPException

from ..models import (
    AnalyzeRequest,
    AnalyzeResponse,
    Claim,
    ContentInfo,
    EntitiesInfo,
    MarketInfo,
    TickerMarketContext,
    PolymarketInsight,
    SentimentInfo,
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
from .market import fetch_market_context, fetch_markets_context
from .sentiment import analyze_sentiment, get_sentiment_label
from .text_utils import normalize_whitespace
from .summary import facts_only_summary
from .polymarket import top_relevant_bets


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
            d = (domain or "").lower()
            is_yahoo = "yahoo.com" in d or "finance.yahoo" in d
            hint = "Paste text instead."
            if is_yahoo:
                hint = "Yahoo Finance blocks automated fetching (HTTP 403). Click 'Paste text' and paste the article content."
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "FETCH_BLOCKED",
                        "message": str(e),
                        "hint": hint,
                        "domain": domain,
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
    
    # Pass headline to primary ticker selection for better accuracy
    headline = title or ""
    primary_ticker = choose_primary_ticker(tickers, text=extracted_text, headline=headline)

    market_res = fetch_market_context(primary_ticker)
    markets_res = fetch_markets_context(tickers)

    claims_raw = extract_claims(extracted_text, limit=10)
    claims = [Claim(**c) for c in claims_raw]

    # Sentiment analysis
    sentiment_result = analyze_sentiment(extracted_text)
    sentiment_label = get_sentiment_label(sentiment_result["sentiment_score"])

    facts_summary = facts_only_summary(
        extracted_text,
        primary_ticker=primary_ticker,
        day_move_pct=market_res.day_move_pct,
        claims=claims_raw,
    )

    polymarket = top_relevant_bets(
        text=extracted_text,
        tickers=tickers,
        companies=companies,
        limit=3,
    )
    polymarket_models = [PolymarketInsight(**b.__dict__) for b in polymarket]

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
            primary_sector=market_res.sector,
            primary_industry=market_res.industry,
        ),
        market=MarketInfo(
            primary_ticker=primary_ticker,
            price_series=market_res.price_series,
            data_source=getattr(market_res, "data_source", None),
            last_close_date=getattr(market_res, "last_close_date", None),
            price_series_days=getattr(market_res, "price_series_days", None),
            current_price=getattr(market_res, "current_price", None),
            day_move_pct=market_res.day_move_pct,
            vol_20d=market_res.vol_20d,
            move_zscore=market_res.move_zscore,
            week_52_high=market_res.week_52_high,
            week_52_low=market_res.week_52_low,
            pct_from_52w_high=market_res.pct_from_52w_high,
            pct_from_52w_low=market_res.pct_from_52w_low,
            market_cap=market_res.market_cap,
            sector=market_res.sector,
            industry=market_res.industry,
            beta=market_res.beta,
            pe_ratio=market_res.pe_ratio,
            sector_performance_today=market_res.sector_performance_today,
            sp500_performance_today=market_res.sp500_performance_today,
            relative_strength=market_res.relative_strength,
            industry_benchmark=getattr(market_res, "industry_benchmark", None),
            industry_performance_today=getattr(market_res, "industry_performance_today", None),
            relative_strength_vs_industry=getattr(market_res, "relative_strength_vs_industry", None),
            peer_group_label=getattr(market_res, "peer_group_label", None),
            peer_group_size=getattr(market_res, "peer_group_size", None),
            peer_avg_move_today=getattr(market_res, "peer_avg_move_today", None),
            relative_strength_vs_peers=getattr(market_res, "relative_strength_vs_peers", None),
            rsi_14d=market_res.rsi_14d,
            ma_50d=market_res.ma_50d,
            ma_200d=market_res.ma_200d,
            unusual_volume=market_res.unusual_volume,
            near_52w_high=market_res.near_52w_high,
            volatility_regime=market_res.volatility_regime,
            average_volume_20d=market_res.average_volume_20d,
            current_volume=market_res.current_volume,
        ),
        markets=[
            TickerMarketContext(
                ticker=m.ticker,
                price_series=m.price_series,
                day_move_pct=m.day_move_pct,
                vol_20d=m.vol_20d,
                move_zscore=m.move_zscore,
                data_source=getattr(m, "data_source", None),
                last_close_date=getattr(m, "last_close_date", None),
                price_series_days=getattr(m, "price_series_days", None),
                week_52_high=m.week_52_high,
                week_52_low=m.week_52_low,
                pct_from_52w_high=m.pct_from_52w_high,
                market_cap=m.market_cap,
                sector=m.sector,
                industry=m.industry,
                rsi_14d=m.rsi_14d,
                ma_50d=m.ma_50d,
                ma_200d=m.ma_200d,
                sector_performance_today=getattr(m, "sector_performance_today", None),
                sp500_performance_today=getattr(m, "sp500_performance_today", None),
                relative_strength=getattr(m, "relative_strength", None),
            )
            for m in markets_res
        ],
        claims=claims,
        sentiment=SentimentInfo(
            sentiment_score=sentiment_result["sentiment_score"],
            sentiment_label=sentiment_label,
            positive_count=sentiment_result["positive_count"],
            negative_count=sentiment_result["negative_count"],
            neutral_ratio=sentiment_result["neutral_ratio"],
        ),
    polymarket=polymarket_models,
        facts_only_summary=facts_summary,
    )
