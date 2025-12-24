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


class PricePoint(BaseModel):
    date: str
    close: float


class MarketInfo(BaseModel):
    primary_ticker: str | None
    price_series: list[PricePoint] = Field(default_factory=list)
    day_move_pct: float | None
    vol_20d: float | None
    move_zscore: float | None


class TickerMarketContext(BaseModel):
    ticker: str
    price_series: list[PricePoint] = Field(default_factory=list)
    day_move_pct: float | None
    vol_20d: float | None
    move_zscore: float | None


class NumberValue(BaseModel):
    value: float
    unit: str | None = None


class Claim(BaseModel):
    claim: str
    numbers: list[NumberValue] = Field(default_factory=list)
    evidence_sentence: str


class HypeWordCount(BaseModel):
    word: str
    count: int


class HypeInfo(BaseModel):
    score_0_100: int
    hype_words: list[HypeWordCount] = Field(default_factory=list)
    ratio: float


class AnalyzeResponse(BaseModel):
    source: SourceInfo
    content: ContentInfo
    entities: EntitiesInfo
    market: MarketInfo
    markets: list[TickerMarketContext] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    hype: HypeInfo
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
