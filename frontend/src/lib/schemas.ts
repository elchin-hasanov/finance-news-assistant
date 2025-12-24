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
  };
  market: {
    primary_ticker: string | null;
    price_series: { date: string; close: number }[];
    day_move_pct: number | null;
    vol_20d: number | null;
    move_zscore: number | null;
  };
  markets: {
    ticker: string;
    price_series: { date: string; close: number }[];
    day_move_pct: number | null;
    vol_20d: number | null;
    move_zscore: number | null;
  }[];
  claims: { claim: string; numbers: { value: number; unit: string | null }[]; evidence_sentence: string }[];
  hype: { score_0_100: number; hype_words: { word: string; count: number }[]; ratio: number };
  facts_only_summary: string;
};
