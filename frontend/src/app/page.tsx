"use client";

import { useMemo, useState } from "react";
import { analyze, type ApiError } from "@/lib/api";
import { analyzeInputSchema, type AnalyzeResponse } from "@/lib/schemas";
import { StockChart } from "@/components/StockChart";
import { Badge } from "@/components/Badge";
import { MarketMetrics } from "@/components/MarketMetrics";

type Tab = "link" | "text";

export default function Home() {
  const [tab, setTab] = useState<Tab>("link");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [blockedHint, setBlockedHint] = useState<string | null>(null);
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);

  const marketByTicker = useMemo(() => {
    const out = new Map<string, AnalyzeResponse["markets"][number]>();
    for (const m of data?.markets ?? []) out.set(m.ticker, m);
    return out;
  }, [data]);

  const companyCards = useMemo(() => {
    const entries = Object.entries(data?.entities.company_tickers ?? {});
    const cards = entries
      .map(([company, ticker]) => {
        const m = marketByTicker.get(ticker);
        const series = m?.price_series ?? [];
        const first = series.at(0)?.close;
        const last = series.at(-1)?.close;
        const pct30 = last != null && first != null && first !== 0 ? ((last - first) / first) * 100 : null;
        return {
          company,
          ticker,
          series,
          pct30,
        };
      })
  // Only show companies we can actually chart.
  .filter((c) => (c.series?.length ?? 0) > 0)
      .sort((a, b) => (b.pct30 ?? -1e9) - (a.pct30 ?? -1e9));

    return cards;
  }, [data, marketByTicker]);

  const selected = useMemo(() => {
    if (!companyCards.length) return null;
    const chosen = selectedCompany ? companyCards.find((c) => c.company === selectedCompany) : null;
    return chosen ?? companyCards[0];
  }, [companyCards, selectedCompany]);

  const input = useMemo(() => ({ url: tab === "link" ? url : "", text: tab === "text" ? text : "" }), [tab, url, text]);

  async function onSubmit() {
    setError(null);
    setBlockedHint(null);
    setData(null);

    const parsed = analyzeInputSchema.safeParse(input);
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Invalid input");
      return;
    }

    setLoading(true);
    try {
      const res = await analyze(parsed.data);
      setData(res);
      const companyTickers = res.entities.company_tickers || {};
      const marketByTickerLocal = new Map(res.markets.map((m) => [m.ticker, m] as const));
      const firstCompanyWithSeries =
        Object.entries(companyTickers).find(([, t]) => (marketByTickerLocal.get(t)?.price_series?.length ?? 0) > 0)?.[0] ??
        Object.keys(companyTickers)[0] ??
        null;
      setSelectedCompany(firstCompanyWithSeries);
    } catch (e: unknown) {
      const err = e as ApiError;
      const code = err?.code;
      const message = err?.message;
      const hint = err?.hint ?? undefined;

      if (code === "FETCH_BLOCKED") {
        setBlockedHint(hint || "This site blocked automated fetching. Paste the article text instead.");
        setTab("text");
      }
      setError(hint ? `${message} — ${hint}` : message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <header className="mb-8">
          <h1 className="text-3xl font-extrabold tracking-tight">De-hype financial news</h1>
          <p className="mt-2 text-gray-800">
            Paste a link or the raw text. Well extract tickers, market context, sentiment, and a facts-only rewrite.
          </p>
        </header>

        <div className="grid gap-6 lg:grid-cols-[420px_1fr]">
          <div className="rounded-xl border bg-white p-5 shadow-sm">
            <div className="flex gap-2">
            <button
              className={`rounded-md px-3 py-2 text-sm font-medium ${tab === "link" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-800"}`}
              onClick={() => setTab("link")}
              type="button"
            >
              Paste link
            </button>
            <button
              className={`rounded-md px-3 py-2 text-sm font-medium ${tab === "text" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-800"}`}
              onClick={() => setTab("text")}
              type="button"
            >
              Paste text
            </button>
            </div>

            <div className="mt-4">
              {tab === "link" ? (
                <div>
                  <label className="text-sm font-semibold text-gray-900">Article URL</label>
                  <input
                    className="mt-2 w-full rounded-md border px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="https://..."
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                  />
                  <p className="mt-2 text-xs text-gray-600">If fetching is blocked or paywalled, you’ll be prompted to paste text.</p>
                </div>
              ) : (
                <div>
                  <label className="text-sm font-semibold text-gray-900">Article text</label>
                  <textarea
                    className="mt-2 h-56 w-full rounded-md border px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Paste the article content here..."
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                  />
                </div>
              )}
            </div>

            <div className="mt-4 flex items-center gap-3">
              <button
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                disabled={loading}
                onClick={onSubmit}
                type="button"
              >
                {loading ? "Analyzing…" : "Analyze"}
              </button>
              {blockedHint ? <span className="text-sm font-medium text-amber-800">{blockedHint}</span> : null}
            </div>

            {error ? (
              <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800">{error}</div>
            ) : null}
          </div>

          {data ? (
            <div className="grid gap-6">
            <section className="rounded-xl border bg-white p-5 shadow-sm">
              <h2 className="text-lg font-extrabold text-slate-900">Article</h2>
              <div className="mt-2 text-sm text-gray-800">
                <div className="flex flex-wrap items-center gap-2">
                  {data.source.title ? <span className="font-medium">{data.source.title}</span> : <span className="text-gray-500">(No title detected)</span>}
                  {data.source.domain ? <Badge>{data.source.domain}</Badge> : null}
                  {data.source.publish_date ? <Badge>{data.source.publish_date}</Badge> : null}
                </div>
                <div className="mt-2 break-all text-xs text-gray-600">{data.source.url}</div>
              </div>
            </section>

            <section className="rounded-xl border bg-white p-5 shadow-sm">
              <h2 className="text-lg font-extrabold text-slate-900">Entities</h2>
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div>
                  <div className="text-sm font-medium text-gray-800">Companies</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {data.entities.companies.length ? data.entities.companies.map((c) => <Badge key={c}>{c}</Badge>) : <span className="text-sm text-gray-500">No companies detected.</span>}
                  </div>
                </div>
                <div>
                  {Object.keys(data.entities.company_tickers || {}).length ? (
                    <div className="mt-3">
                      <div className="text-xs font-semibold text-gray-700">Resolved market tickers (internal)</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {Object.entries(data.entities.company_tickers).map(([k, v]) => (
                          <Badge key={k}>{k} → {v}</Badge>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            </section>

            <section className="rounded-xl border bg-white p-5 shadow-sm">
              <h2 className="text-lg font-extrabold text-slate-900">Sentiment Analysis</h2>
              <div className="mt-3 grid gap-4 md:grid-cols-[1fr_240px]">
                <div>
                  <div className="text-sm font-medium text-gray-700">Overall Sentiment</div>
                  <div className={`mt-1 text-3xl font-extrabold ${data.sentiment.sentiment_score >= 0.25 ? "text-emerald-700" : data.sentiment.sentiment_score <= -0.25 ? "text-red-700" : "text-slate-800"}`}
                  >
                    {data.sentiment.sentiment_label}
                  </div>
                  <div className="mt-2 text-sm text-gray-700">
                    Sentiment Score: <span className="font-semibold tabular-nums">{data.sentiment.sentiment_score.toFixed(3)}</span>
                  </div>
                  <div className="mt-3 h-3 w-full rounded-full bg-gray-200">
                    <div
                      className="h-3 rounded-full bg-emerald-600"
                      style={{ width: `${Math.round(((data.sentiment.sentiment_score + 1) / 2) * 100)}%` }}
                      aria-label="Sentiment bar"
                    />
                  </div>
                  <div className="mt-2 text-xs text-gray-600">
                    Note: word counts below are auxiliary (lexicon) stats. The score is primarily model-based when available.
                  </div>
                </div>

                <div className="grid gap-3">
                  <div className="rounded-lg border bg-emerald-50 p-3">
                    <div className="text-xs font-semibold text-emerald-800">Positive words (aux)</div>
                    <div className="mt-1 text-2xl font-extrabold text-emerald-900 tabular-nums">{data.sentiment.positive_count}</div>
                  </div>
                  <div className="rounded-lg border bg-red-50 p-3">
                    <div className="text-xs font-semibold text-red-800">Negative words (aux)</div>
                    <div className="mt-1 text-2xl font-extrabold text-red-900 tabular-nums">{data.sentiment.negative_count}</div>
                  </div>
                  <div className="rounded-lg border bg-slate-50 p-3">
                    <div className="text-xs font-semibold text-slate-800">Model neutral probability</div>
                    <div className="mt-1 text-2xl font-extrabold text-slate-900 tabular-nums">
                      {Math.round(data.sentiment.neutral_ratio * 100)}%
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="rounded-xl border bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-lg font-extrabold text-slate-900">Market context</h2>
                {!data.market.primary_ticker ? <Badge>No market data</Badge> : null}
              </div>

              {data.market.primary_ticker ? (
                <div className="mt-4">
                  {/* Prefer showing the metrics even when we don't have a chart series */}
                  <div className="mx-auto mt-6 max-w-4xl rounded-xl border bg-white p-6 shadow-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-lg font-extrabold text-slate-900">
                          {selected?.company ?? data.market.primary_ticker}
                        </div>
                        <div className="mt-1 text-sm text-gray-600">
                          Ticker: <span className="font-semibold">{data.market.primary_ticker}</span>
                        </div>
                      </div>
                    </div>

                    {companyCards.length ? (
                      <div className="mt-4">
                        <div className="text-sm font-semibold text-gray-900 mb-3">Price Chart (30 days)</div>
                        <div className="flex flex-wrap gap-2 mb-4">
                          {companyCards.map((c) => (
                            <button
                              key={c.company}
                              type="button"
                              onClick={() => setSelectedCompany(c.company)}
                              className={`rounded-full border px-3 py-1 text-xs font-semibold ${selected?.company === c.company ? "bg-blue-600 text-white border-blue-600" : "bg-white text-gray-800 border-gray-200"}`}
                            >
                              {c.company}
                            </button>
                          ))}
                        </div>
                        {selected ? <StockChart data={selected.series} /> : null}
                      </div>
                    ) : (
                      <p className="mt-4 text-sm text-gray-700">No price chart available, but market metrics may still be available below.</p>
                    )}

                    <div className="mt-6 pt-6 border-t border-gray-200">
                      <h3 className="text-sm font-semibold text-gray-900 mb-4">Market Metrics</h3>
                      <MarketMetrics market={data.market} />
                    </div>
                  </div>
                </div>
              ) : null}

              <p className="mt-3 text-xs text-gray-600">
                Market context is shown only for public securities where we can reliably resolve a real ticker.
              </p>
            </section>



            <section className="rounded-xl border bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold">Facts-only rewrite</h2>
              <p className="mt-3 text-sm leading-6 text-gray-900">{data.facts_only_summary}</p>
            </section>

            <section className="rounded-xl border bg-white p-5 shadow-sm">
              <h2 className="text-lg font-extrabold text-slate-900">Polymarket insights</h2>
              <p className="mt-2 text-sm text-gray-700">
                Top 3 prediction markets that match the articles topic (curated/offline matching).
              </p>

              {data.polymarket?.length ? (
                <div className="mt-4 grid gap-3">
                  {data.polymarket.slice(0, 3).map((m) => (
                    <div key={m.title} className="rounded-lg border bg-gray-50 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-sm font-semibold text-gray-900">{m.title}</div>
                        {m.category ? <Badge>{m.category}</Badge> : null}
                      </div>
                      {m.reason ? <div className="mt-2 text-xs text-gray-600">{m.reason}</div> : null}
                      {m.url ? (
                        <div className="mt-2 text-xs">
                          <a className="text-blue-700 underline" href={m.url} target="_blank" rel="noreferrer">
                            View on Polymarket
                          </a>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-3 text-sm text-gray-500">No matching prediction markets found.</div>
              )}
            </section>
            </div>
          ) : (
            <div className="rounded-xl border bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold">Results</h2>
              <p className="mt-2 text-sm text-gray-700">Run an analysis to see extracted entities, market context, sentiment, and a rewrite.</p>
            </div>
          )}
        </div>

        <footer className="mt-10 text-xs text-gray-500">
          Backend: <code className="rounded bg-gray-100 px-1 py-0.5">NEXT_PUBLIC_BACKEND_URL</code> (default <code className="rounded bg-gray-100 px-1 py-0.5">http://localhost:8000</code>)
        </footer>
      </div>
    </div>
  );
}
