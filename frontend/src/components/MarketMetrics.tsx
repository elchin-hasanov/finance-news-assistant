"use client";

import { AnalyzeResponse } from "@/lib/schemas";
import { Badge } from "./Badge";

type MarketMetricsProps = {
  market: AnalyzeResponse["market"];
};

function fmtNumber(num: number | null | undefined, decimals = 2) {
  if (num === null || num === undefined) return "N/A";
  return num.toFixed(decimals);
}

function fmtPrice(num: number | null | undefined) {
  if (num === null || num === undefined) return "N/A";
  return `$${num.toFixed(2)}`;
}

function fmtLargeNumber(num: number | null | undefined) {
  if (num === null || num === undefined) return "N/A";
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  return `$${num.toFixed(0)}`;
}

function InfoLabel({ label, help }: { label: string; help: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-gray-500">
      <span>{label}</span>
      <span className="group relative inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-gray-200 bg-white text-[10px] text-gray-500">
        i
        <span className="pointer-events-none absolute right-0 top-5 z-20 hidden w-64 rounded-md border bg-white p-2 text-xs text-gray-700 shadow-lg group-hover:block">
          {help}
        </span>
      </span>
    </span>
  );
}

function pctColor(pct: number | null | undefined) {
  if (pct === null || pct === undefined) return "text-gray-600";
  if (pct === 0) return "text-gray-700";
  return pct > 0 ? "text-green-600" : "text-red-600";
}

function rsiColor(rsi: number | null | undefined) {
  if (rsi === null || rsi === undefined) return "text-gray-600";
  if (rsi > 70) return "text-red-600 font-semibold";
  if (rsi < 30) return "text-green-600 font-semibold";
  return "text-gray-600";
}

function fmtSignedPct(num: number | null | undefined) {
  if (num === null || num === undefined) return "N/A";
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toFixed(2)}%`;
}

function fmtRel(label: string, value: number | null | undefined, suffix: string) {
  if (value === null || value === undefined) return null;
  return (
    <div>
      <span className="font-medium">{label}:</span>{" "}
      <span className={pctColor(value)}>{fmtSignedPct(value)}</span>
      <span className="text-gray-500"> {suffix}</span>
    </div>
  );
}

export function MarketMetrics({ market }: MarketMetricsProps) {
  const lastClose = market.price_series?.at(-1)?.close ?? null;
  const week52High = market.week_52_high;
  const week52Low = market.week_52_low;

  const rangePct = (() => {
    if (lastClose === null || week52High === null || week52Low === null) return null;
    const denom = week52High - week52Low;
    if (denom <= 0) return null;
    const v = ((lastClose - week52Low) / denom) * 100;
    return Math.max(0, Math.min(100, v));
  })();

  return (
    <div className="space-y-4">
      <div className="rounded border bg-white p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-xs text-gray-500">Metrics for</div>
            <div className="text-sm font-semibold text-gray-900">{market.primary_ticker ?? "Unknown"}</div>
          </div>
          <div className="text-xs text-gray-600">
            <span>
              Source: <span className="font-medium">{market.data_source ?? "N/A"}</span>
            </span>
            {market.last_close_date ? (
              <span>
                {" "}
                · Last close: <span className="font-medium">{market.last_close_date}</span>
              </span>
            ) : null}
            {typeof market.price_series_days === "number" ? (
              <span>
                {" "}
                · Chart points: <span className="font-medium">{market.price_series_days}</span>
              </span>
            ) : null}
          </div>
        </div>
        <div className="mt-2 text-xs text-gray-500">
          Returns are close-to-close using the latest two available trading days from the provider.
        </div>
      </div>

      {(market.sector || market.industry) && (
        <div className="flex gap-2 flex-wrap">
          {market.sector && <Badge variant="blue">{market.sector}</Badge>}
          {market.industry && <Badge variant="purple">{market.industry}</Badge>}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {lastClose !== null && (
          <div className="bg-gray-50 p-3 rounded">
            <div className="mb-1">
              <InfoLabel
                label="Last Close"
                help="The most recent daily closing price available from the data provider (not real-time)."
              />
            </div>
            <div className="text-lg font-bold text-gray-900">{fmtPrice(lastClose)}</div>
          </div>
        )}

        {market.day_move_pct !== null && (
          <div className="bg-gray-50 p-3 rounded">
            <div className="mb-1">
              <InfoLabel
                label="Daily Move"
                help="% change from the prior trading day close to the latest close in the dataset (close-to-close)."
              />
            </div>
            <div className={`text-lg font-bold ${pctColor(market.day_move_pct)}`}>
              {market.day_move_pct > 0 ? "+" : ""}
              {fmtNumber(market.day_move_pct)}%
            </div>
          </div>
        )}

        {market.market_cap !== null && (
          <div className="bg-gray-50 p-3 rounded">
            <div className="mb-1">
              <InfoLabel
                label="Market Cap"
                help="Company value = shares outstanding × price (best-effort, can be stale/missing for some tickers)."
              />
            </div>
            <div className="text-lg font-bold text-gray-900">{fmtLargeNumber(market.market_cap)}</div>
          </div>
        )}

        {market.pe_ratio !== null && (
          <div className="bg-gray-50 p-3 rounded">
            <div className="mb-1">
              <InfoLabel
                label="P/E"
                help="Trailing price-to-earnings ratio (price divided by trailing 12-month earnings per share)."
              />
            </div>
            <div className="text-lg font-bold text-gray-900">{fmtNumber(market.pe_ratio, 1)}</div>
          </div>
        )}
      </div>

      <div className="bg-gray-50 p-4 rounded">
        <div className="mb-3 flex items-center justify-between gap-3">
          <InfoLabel
            label="Market context (today)"
            help="Close-to-close daily move compared to industry (best-effort ETF), sector ETF, and the broad market (SPY). If a comparator can’t be computed (missing sector/industry, rate limits, or no suitable ETF), we’ll show why."
          />
          <div className="text-[11px] text-gray-500">Comparators are optional and may be unavailable.</div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div className="rounded bg-white border p-3">
            <div className="text-xs text-gray-500">Stock</div>
            <div className={`text-sm font-semibold ${pctColor(market.day_move_pct)}`}>{fmtSignedPct(market.day_move_pct)}</div>
          </div>

          <div className="rounded bg-white border p-3">
            <div className="text-xs text-gray-500">Industry</div>
            {market.industry_performance_today !== null ? (
              <div className={`text-sm font-semibold ${pctColor(market.industry_performance_today)}`}>{fmtSignedPct(market.industry_performance_today)}</div>
            ) : (
              <div className="text-sm font-semibold text-gray-400">Not available</div>
            )}
            <div className="mt-1 text-[11px] text-gray-500">
              {market.industry_benchmark
                ? `(${market.industry_benchmark})`
                : market.industry
                  ? "(No mapped industry ETF yet)"
                  : "(Industry unknown)"}
            </div>
          </div>

          <div className="rounded bg-white border p-3">
            <div className="text-xs text-gray-500">Sector ETF</div>
            {market.sector_performance_today !== null ? (
              <div className={`text-sm font-semibold ${pctColor(market.sector_performance_today)}`}>{fmtSignedPct(market.sector_performance_today)}</div>
            ) : (
              <div className="text-sm font-semibold text-gray-400">Not available</div>
            )}
            <div className="mt-1 text-[11px] text-gray-500">{market.sector ? `(${market.sector})` : "(Sector unknown)"}</div>
          </div>

          <div className="rounded bg-white border p-3">
            <div className="text-xs text-gray-500">S&P 500 (SPY)</div>
            {market.sp500_performance_today !== null ? (
              <div className={`text-sm font-semibold ${pctColor(market.sp500_performance_today)}`}>{fmtSignedPct(market.sp500_performance_today)}</div>
            ) : (
              <div className="text-sm font-semibold text-gray-400">Not available</div>
            )}
          </div>
        </div>

        <div className="mt-3 space-y-1 text-xs text-gray-600">
          {fmtRel("Relative vs industry", market.relative_strength_vs_industry, "(stock minus industry)")}
          {fmtRel("Relative vs sector", market.relative_strength, "(stock minus sector)")}

          {market.peer_avg_move_today !== null ? (
            <div>
              <span className="font-medium">Peers avg:</span>{" "}
              <span className={pctColor(market.peer_avg_move_today)}>{fmtSignedPct(market.peer_avg_move_today)}</span>
              {market.peer_group_label ? (
                <span className="text-gray-500"> ({market.peer_group_label}{market.peer_group_size ? `, n=${market.peer_group_size}` : ""})</span>
              ) : null}
            </div>
          ) : (
            <div className="text-gray-500">
              <span className="font-medium">Peers avg:</span> Not available (computed only when enough peers can be found without hitting data limits)
            </div>
          )}

          {fmtRel("Relative vs peers", market.relative_strength_vs_peers, "(stock minus peer avg)")}
        </div>
      </div>

      {week52High !== null && week52Low !== null && rangePct !== null && (
        <div className="bg-gray-50 p-4 rounded">
          <div className="text-xs text-gray-500 mb-2">52-Week Range (last ~252 trading days)</div>
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium">{fmtPrice(week52Low)}</span>
            <span className="text-sm font-medium">{fmtPrice(week52High)}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${rangePct}%` }} />
          </div>
          {market.pct_from_52w_high !== null && (
            <div className="text-xs text-gray-600 mt-1">{fmtNumber(market.pct_from_52w_high)}% from 52W high</div>
          )}
          {market.pct_from_52w_low !== null && (
            <div className="text-xs text-gray-600 mt-1">{fmtNumber(market.pct_from_52w_low)}% from 52W low</div>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {market.rsi_14d !== null && (
          <div className="bg-gray-50 p-3 rounded">
            <div className="mb-1">
              <InfoLabel
                label="RSI (14d)"
                help="Relative Strength Index (0–100). Common interpretation: >70 overbought, <30 oversold. Not a guarantee, just a momentum indicator."
              />
            </div>
            <div className={`text-lg font-bold ${rsiColor(market.rsi_14d)}`}>
              {fmtNumber(market.rsi_14d, 0)}
              {market.rsi_14d > 70 ? <span className="text-xs ml-1">(Overbought)</span> : null}
              {market.rsi_14d < 30 ? <span className="text-xs ml-1">(Oversold)</span> : null}
            </div>
            <div className="mt-1 text-xs text-gray-500">Momentum oscillator (0–100).</div>
          </div>
        )}

        {market.ma_50d !== null && (
          <div className="bg-gray-50 p-3 rounded">
            <div className="text-xs text-gray-500 mb-1">50-Day MA</div>
            <div className="text-lg font-bold text-gray-900">{fmtPrice(market.ma_50d)}</div>
            <div className="mt-1 text-xs text-gray-500">Average close over ~50 trading days.</div>
          </div>
        )}

        {market.ma_200d !== null && (
          <div className="bg-gray-50 p-3 rounded">
            <div className="text-xs text-gray-500 mb-1">200-Day MA</div>
            <div className="text-lg font-bold text-gray-900">{fmtPrice(market.ma_200d)}</div>
            <div className="mt-1 text-xs text-gray-500">Long-term trend filter (~200 trading days).</div>
          </div>
        )}
      </div>

      {market.vol_20d !== null && (
        <div className="bg-gray-50 p-3 rounded">
          <div className="mb-1">
            <InfoLabel
              label="20D Volatility"
              help="Standard deviation of daily returns over the last ~20 trading days (in %). Higher means bigger typical daily swings."
            />
          </div>
          <div className="text-sm text-gray-700">
            {fmtNumber(market.vol_20d)}%
            {market.move_zscore !== null ? <span className="ml-2 text-gray-600">(Z: {fmtNumber(market.move_zscore)})</span> : null}
          </div>
        </div>
      )}
    </div>
  );
}
