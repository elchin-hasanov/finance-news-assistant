import { z } from "zod";

export const analyzeInputSchema = z
  .object({
    url: z.string().trim().url().optional().or(z.literal("")),
    text: z.string().trim().optional().or(z.literal("")),
  })
  .refine((v) => Boolean(v.url) || Boolean(v.text), {
    message: "Provide either a valid URL or pasted text.",
    path: ["url"],
  });

export type AnalyzeInput = z.infer<typeof analyzeInputSchema>;

export type ApiErrorEnvelope = {
  error: { code: string; message: string; hint?: string | null };
};

export type AnalyzeResponse = {
  source: { url: string | null; title: string | null; domain: string | null; publish_date: string | null };
  content: { raw_text: string; extracted_text: string };
  entities: {
    companies: string[];
    tickers: string[];
    ticker_aliases: Record<string, string>;
    company_tickers: Record<string, string>;
    primary_ticker: string | null;
    primary_sector: string | null;
    primary_industry: string | null;
  };
  market: {
    primary_ticker: string | null;
    price_series: { date: string; close: number }[];
  data_source: string | null;
  last_close_date: string | null;
  price_series_days: number | null;
    day_move_pct: number | null;
    vol_20d: number | null;
    move_zscore: number | null;
    week_52_high: number | null;
    week_52_low: number | null;
    pct_from_52w_high: number | null;
    pct_from_52w_low: number | null;
    market_cap: number | null;
    sector: string | null;
    industry: string | null;
    beta: number | null;
    pe_ratio: number | null;
    sector_performance_today: number | null;
    sp500_performance_today: number | null;
    relative_strength: number | null;
  industry_benchmark: string | null;
  industry_performance_today: number | null;
  relative_strength_vs_industry: number | null;
  peer_group_label: string | null;
  peer_group_size: number | null;
  peer_avg_move_today: number | null;
  relative_strength_vs_peers: number | null;
    rsi_14d: number | null;
    ma_50d: number | null;
    ma_200d: number | null;
    unusual_volume: boolean;
    near_52w_high: boolean;
    volatility_regime: string | null;
    average_volume_20d: number | null;
    current_volume: number | null;
  };
  markets: {
    ticker: string;
    price_series: { date: string; close: number }[];
    day_move_pct: number | null;
    vol_20d: number | null;
    move_zscore: number | null;
  data_source: string | null;
  last_close_date: string | null;
  price_series_days: number | null;
    week_52_high: number | null;
    week_52_low: number | null;
    pct_from_52w_high: number | null;
    market_cap: number | null;
    sector: string | null;
    industry: string | null;
  sector_performance_today: number | null;
  sp500_performance_today: number | null;
  relative_strength: number | null;
  industry_benchmark: string | null;
  industry_performance_today: number | null;
  relative_strength_vs_industry: number | null;
  peer_group_label: string | null;
  peer_group_size: number | null;
  peer_avg_move_today: number | null;
  relative_strength_vs_peers: number | null;
    rsi_14d: number | null;
    ma_50d: number | null;
    ma_200d: number | null;
  }[];
  claims: { claim: string; numbers: { value: number; unit: string | null }[]; evidence_sentence: string }[];
  sentiment: {
    sentiment_score: number;
    sentiment_label: string;
    positive_count: number;
    negative_count: number;
    neutral_ratio: number;
  };
  polymarket: {
    title: string;
    url: string | null;
    probability: number | null;
    category: string | null;
    reason: string | null;
  }[];
  facts_only_summary: string;
};
