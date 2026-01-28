from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    code: str
    message: str
    hint: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorPayload


class AnalyzeRequest(BaseModel):
    url: str | None = None
    text: str | None = None


class SourceInfo(BaseModel):
    url: str | None
    title: str | None
    domain: str | None
    publish_date: str | None


class ContentInfo(BaseModel):
    raw_text: str
    extracted_text: str


class EntitiesInfo(BaseModel):
    companies: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    # Mapping of short codes / abbreviations found to their resolved tickers.
    ticker_aliases: dict[str, str] = Field(default_factory=dict)
    # Optional mapping of company names to tickers when we can infer it.
    company_tickers: dict[str, str] = Field(default_factory=dict)
    primary_ticker: str | None = None
    primary_sector: str | None = None
    primary_industry: str | None = None


class PricePoint(BaseModel):
    date: str
    close: float


class MarketInfo(BaseModel):
    primary_ticker: str | None
    price_series: list[PricePoint] = Field(default_factory=list)
    # Meta about the market data returned (for UI clarity).
    data_source: str | None = None  # "yfinance" | "alpha_vantage" | None
    last_close_date: str | None = None
    price_series_days: int | None = None
    current_price: float | None = None
    day_move_pct: float | None
    vol_20d: float | None
    move_zscore: float | None
    # Enhanced metrics
    week_52_high: float | None = None
    week_52_low: float | None = None
    pct_from_52w_high: float | None = None
    pct_from_52w_low: float | None = None
    market_cap: float | None = None
    sector: str | None = None
    industry: str | None = None
    beta: float | None = None
    pe_ratio: float | None = None
    # Comparative metrics
    sector_performance_today: float | None = None
    sp500_performance_today: float | None = None
    relative_strength: float | None = None
    industry_benchmark: str | None = None
    industry_performance_today: float | None = None
    relative_strength_vs_industry: float | None = None
    peer_group_label: str | None = None
    peer_group_size: int | None = None
    peer_avg_move_today: float | None = None
    relative_strength_vs_peers: float | None = None
    # Technical indicators
    rsi_14d: float | None = None
    ma_50d: float | None = None
    ma_200d: float | None = None
    # Context flags
    unusual_volume: bool = False
    near_52w_high: bool = False
    volatility_regime: str | None = None  # "low" | "normal" | "high"
    average_volume_20d: float | None = None
    current_volume: float | None = None


class TickerMarketContext(BaseModel):
    ticker: str
    price_series: list[PricePoint] = Field(default_factory=list)
    day_move_pct: float | None
    vol_20d: float | None
    move_zscore: float | None
    data_source: str | None = None
    last_close_date: str | None = None
    price_series_days: int | None = None
    # Enhanced metrics
    week_52_high: float | None = None
    week_52_low: float | None = None
    pct_from_52w_high: float | None = None
    market_cap: float | None = None
    sector: str | None = None
    industry: str | None = None
    rsi_14d: float | None = None
    ma_50d: float | None = None
    ma_200d: float | None = None
    sector_performance_today: float | None = None
    sp500_performance_today: float | None = None
    relative_strength: float | None = None
    industry_benchmark: str | None = None
    industry_performance_today: float | None = None
    relative_strength_vs_industry: float | None = None
    peer_group_label: str | None = None
    peer_group_size: int | None = None
    peer_avg_move_today: float | None = None
    relative_strength_vs_peers: float | None = None


class NumberValue(BaseModel):
    value: float
    unit: str | None = None


class Claim(BaseModel):
    claim: str
    numbers: list[NumberValue] = Field(default_factory=list)
    evidence_sentence: str


class SentimentInfo(BaseModel):
    sentiment_score: float  # -1.0 to +1.0
    sentiment_label: str  # "Very Positive", "Positive", etc.
    positive_count: int
    negative_count: int
    neutral_ratio: float


class PolymarketInsight(BaseModel):
    title: str
    url: str | None = None
    probability: float | None = None
    category: str | None = None
    reason: str | None = None


class AnalyzeResponse(BaseModel):
    source: SourceInfo
    content: ContentInfo
    entities: EntitiesInfo
    market: MarketInfo
    markets: list[TickerMarketContext] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    sentiment: SentimentInfo
    polymarket: list[PolymarketInsight] = Field(default_factory=list)
    facts_only_summary: str


def json_safe(value: Any) -> Any:
    """Convert NaN/Inf floats into None for stable JSON."""
    try:
        import math

        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
    except Exception:
        return value
    return value
