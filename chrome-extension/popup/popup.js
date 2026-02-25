/**
 * Finance News Analyzer - Popup Script
 * Handles UI interactions and communicates with content script
 */

const DEFAULT_API_URL = 'http://localhost:8000';

// State
let currentTabId = null;
let analysisResults = null;

// DOM Elements
const initialState = document.getElementById('initial-state');
const loadingState = document.getElementById('loading-state');
const resultsState = document.getElementById('results-state');
const errorState = document.getElementById('error-state');

const analyzeBtn = document.getElementById('analyze-btn');
const clearBtn = document.getElementById('clear-btn');
const retryBtn = document.getElementById('retry-btn');
const apiUrlInput = document.getElementById('api-url');
const errorMessage = document.getElementById('error-message');

// Ticker elements
const tickerSymbol = document.getElementById('ticker-symbol');
const tickerName = document.getElementById('ticker-name');
const tickerChange = document.getElementById('ticker-change');
const changeValue = document.getElementById('change-value');
const miniChart = document.getElementById('mini-chart');
const primaryChartCanvas = document.getElementById('primaryChart');
const primaryHover = document.getElementById('primaryHover');

let primaryRange = '1M';

// Claims elements
const claimsCount = document.getElementById('claims-count');
const claimsList = document.getElementById('claims-list');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  // Load saved API URL
  const stored = await chrome.storage.local.get(['apiUrl']);
  apiUrlInput.value = stored.apiUrl || DEFAULT_API_URL;

  // Get current tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTabId = tab.id;

  // Check if we have existing results for this tab
  const tabResults = await chrome.storage.session.get([`results_${currentTabId}`]);
  if (tabResults[`results_${currentTabId}`]) {
    analysisResults = tabResults[`results_${currentTabId}`];
    showResults();
  }
});

// Save API URL on change
apiUrlInput.addEventListener('change', () => {
  chrome.storage.local.set({ apiUrl: apiUrlInput.value });
});

// Analyze button click
analyzeBtn.addEventListener('click', analyzeArticle);
retryBtn.addEventListener('click', analyzeArticle);

// Clear button click
clearBtn.addEventListener('click', async () => {
  await chrome.tabs.sendMessage(currentTabId, { action: 'clearHighlights' });
  await chrome.storage.session.remove([`results_${currentTabId}`]);
  analysisResults = null;
  showState('initial');
});

// Show specific state
function showState(state) {
  initialState.classList.add('hidden');
  loadingState.classList.add('hidden');
  resultsState.classList.add('hidden');
  errorState.classList.add('hidden');

  switch (state) {
    case 'initial':
      initialState.classList.remove('hidden');
      break;
    case 'loading':
      loadingState.classList.remove('hidden');
      break;
    case 'results':
      resultsState.classList.remove('hidden');
      break;
    case 'error':
      errorState.classList.remove('hidden');
      break;
  }
}

// Analyze article
async function analyzeArticle() {
  showState('loading');

  try {
    // Get article content from content script.
    // If the content script isn't injected yet (extension reload, restricted page, etc.)
    // we programmatically inject it first.
    let response;
    try {
      response = await chrome.tabs.sendMessage(currentTabId, { action: 'getArticleContent' });
    } catch (_connErr) {
      // Content script not loaded — inject it, then retry.
      try {
        await chrome.scripting.executeScript({
          target: { tabId: currentTabId },
          files: ['content/companyMapping.js', 'content/content.js']
        });
        // Brief delay to let script initialise
        await new Promise(r => setTimeout(r, 200));
        response = await chrome.tabs.sendMessage(currentTabId, { action: 'getArticleContent' });
      } catch (injectErr) {
        throw new Error('Cannot analyze this page. Please navigate to a news article and try again.');
      }
    }
    
    if (!response || !response.text) {
      throw new Error('Could not extract article content from this page.');
    }

    const apiUrl = apiUrlInput.value || DEFAULT_API_URL;
    
    // Call backend API
    const apiResponse = await fetch(`${apiUrl}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: response.text, url: response.url })
    });

    if (!apiResponse.ok) {
      const errorData = await apiResponse.json().catch(() => ({}));
      throw new Error(errorData.error?.message || `API error: ${apiResponse.status}`);
    }

    analysisResults = await apiResponse.json();
    
    // Store results for this tab
    await chrome.storage.session.set({ [`results_${currentTabId}`]: analysisResults });

    // Send highlights to content script
    const markets = analysisResults.markets || [];
    const tickerPriceSeries = {};
    markets.forEach(m => {
      if (m?.ticker && Array.isArray(m.price_series)) {
        tickerPriceSeries[m.ticker] = m.price_series;
      }
    });

    await chrome.tabs.sendMessage(currentTabId, {
      action: 'highlightClaims',
      data: {
        claims: analysisResults.claims || [],
        primaryTicker: analysisResults.entities?.primary_ticker,
        priceSeries: analysisResults.market?.price_series || [],
        allTickers: analysisResults.entities?.tickers || [],
        tickerPriceSeries
      }
    });

    showResults();
  } catch (error) {
    console.error('Analysis failed:', error);
    errorMessage.textContent = error.message || 'Could not analyze the article. Please try again.';
    showState('error');
  }
}

// Show results
function showResults() {
  if (!analysisResults) {
    showState('initial');
    return;
  }

  showState('results');

  // ── Dynamic toolbar icon based on reliability ──
  const reliability = analysisResults.reliability;
  if (reliability && currentTabId) {
    chrome.runtime.sendMessage({
      action: 'setReliabilityIcon',
      tabId: currentTabId,
      score: reliability.reliability_score,
    }).catch(() => {});
  }

  // Update ticker info
  const entities = analysisResults.entities || {};
  const market = analysisResults.market || {};

  if (entities.primary_ticker) {
    tickerSymbol.textContent = entities.primary_ticker;
    tickerName.textContent = entities.primary_sector || 'Stock';
    
    if (market.day_move_pct !== null && market.day_move_pct !== undefined) {
      const pct = market.day_move_pct;
      const sign = pct >= 0 ? '+' : '';
      changeValue.textContent = `${sign}${pct.toFixed(2)}%`;
      // Use range-based color so badge matches the chart line
      const rangePos = (market.price_series && market.price_series.length > 1)
        ? isRangePositive(market.price_series, primaryRange)
        : pct >= 0;
      tickerChange.className = `ticker-change ${rangePos ? 'positive' : 'negative'}`;
    } else {
      changeValue.textContent = '—';
      tickerChange.className = 'ticker-change neutral';
    }

    // Draw primary chart (rich)
    if (market.price_series && market.price_series.length > 0) {
      setupPrimaryRangeControls();
      updateRangePercentages(market.price_series);
      // Determine color from the *displayed range*, not the daily move
      const rangePositive = isRangePositive(market.price_series, primaryRange);
      drawPrimaryChart(market.price_series, rangePositive);
    }

    // --- S&P 500 Market Comparison ---
    populateMarketComparison(entities.primary_ticker, market.price_series);

  } else {
    tickerSymbol.textContent = '—';
    tickerName.textContent = 'No ticker detected';
    changeValue.textContent = '—';
    tickerChange.className = 'ticker-change neutral';
  miniChart.innerHTML = '';
  }

  // Update claims
  const claims = analysisResults.claims || [];
  
  // Sort by sensational_score (backend already does this, but be safe),
  // then take top 5.
  const sensationalClaims = claims
    .filter(c => (c.sensational_score || 0) >= 2.0)
    .sort((a, b) => (b.sensational_score || 0) - (a.sensational_score || 0))
    .slice(0, 5);

  claimsCount.textContent = sensationalClaims.length;

  if (sensationalClaims.length > 0) {
    claimsList.innerHTML = sensationalClaims.map((claim, idx) => {
      const score = (claim.sensational_score || 0).toFixed(1);
      const cat = escapeHtml(claim.category || 'Claim');
      const catClass = (claim.category || '')
        .toLowerCase().replace(/[^a-z]/g, '-').replace(/-+/g, '-');
      const numbersHtml = (claim.numbers || []).map(n =>
        `<span class="claim-number">${n.value}${n.unit || ''}</span>`
      ).join('');

      return `
        <div class="claim-item" data-index="${idx}">
          <div class="claim-header">
            <span class="claim-category cat-${catClass}">${cat}</span>
            <span class="claim-score" title="Sensationalism score">${score}</span>
          </div>
          <div class="claim-text">${escapeHtml(claim.claim)}</div>
          ${numbersHtml ? `<div class="claim-numbers">${numbersHtml}</div>` : ''}
        </div>
      `;
    }).join('');

    // Add click handlers to scroll to claim in article
    document.querySelectorAll('.claim-item').forEach(item => {
      item.addEventListener('click', async () => {
        const idx = parseInt(item.dataset.index);
        await chrome.tabs.sendMessage(currentTabId, {
          action: 'scrollToClaim',
          claimIndex: idx
        });
      });
    });
  } else {
    claimsList.innerHTML = '<p class="empty-state">No sensational claims detected.</p>';
  }

  // ── Reliability section ──
  populateReliability();
}

function populateReliability() {
  const section = document.getElementById('reliability-section');
  if (!section) return;

  const rel = analysisResults?.reliability;
  if (!rel) {
    section.style.display = 'none';
    return;
  }

  section.style.display = '';

  const score = rel.reliability_score ?? 0;
  const label = rel.reliability_label || '—';
  const signals = rel.signals || {};

  // Score number
  const scoreEl = document.getElementById('reliability-score');
  if (scoreEl) scoreEl.textContent = `${score}/100`;

  // Label
  const labelEl = document.getElementById('reliability-label');
  if (labelEl) {
    labelEl.textContent = label;
    labelEl.className = 'reliability-label ' + (
      score >= 50 ? 'rel-good' : 'rel-bad'
    );
  }

  // Gauge arc (stroke-dashoffset drives the fill)
  // The arc path length is ~157. Full fill = offset 0; empty = offset 157.
  const gaugeFill = document.getElementById('gauge-fill');
  if (gaugeFill) {
    const pct = Math.max(0, Math.min(100, score)) / 100;
    const offset = 157 * (1 - pct);
    gaugeFill.style.strokeDashoffset = offset;
    gaugeFill.style.stroke = score >= 50 ? '#10B981' : '#EF4444';
  }

  // Signal breakdown
  const container = document.getElementById('reliability-signals');
  if (!container) return;

  // Nice names for signals
  const signalNames = {
    source_attribution: { label: 'Source Attribution', icon: '📄', max: 15 },
    numerical_evidence: { label: 'Numerical Evidence', icon: '🔢', max: 10 },
    hedging_language: { label: 'Hedging & Nuance', icon: '⚖️', max: 8 },
    balanced_perspective: { label: 'Balanced Perspective', icon: '�', max: 10 },
    factual_density: { label: 'Factual Density', icon: '�', max: 7 },
    article_length: { label: 'Article Length', icon: '�', max: 5 },
    hype_penalty: { label: 'Hype Language', icon: '📢', max: -20 },
    claims_penalty: { label: 'Sensational Claims', icon: '⚡', max: -15 },
    sentiment_extreme: { label: 'Sentiment Extreme', icon: '🎭', max: -10 },
    urgency_penalty: { label: 'Urgency / Pressure', icon: '⏰', max: -10 },
    formatting_penalty: { label: 'Formatting (!!!/CAPS)', icon: '🔤', max: -10 },
    neutral_ratio_penalty: { label: 'Low Neutrality', icon: '😐', max: -5 },
  };

  container.innerHTML = Object.entries(signals)
    .filter(([, value]) => value !== 0)
    .map(([key, value]) => {
    const info = signalNames[key] || { label: key, icon: '•', max: 10 };
    const isPositive = value >= 0;
    const absVal = Math.abs(value);
    const absMax = Math.abs(info.max);
    const pct = Math.min(100, (absVal / absMax) * 100);
    const barClass = isPositive ? 'signal-bar-positive' : 'signal-bar-negative';
    return `
      <div class="signal-row">
        <span class="signal-icon">${info.icon}</span>
        <span class="signal-name">${info.label}</span>
        <div class="signal-bar-track">
          <div class="signal-bar-fill ${barClass}" style="width:${pct}%"></div>
        </div>
        <span class="signal-value ${isPositive ? 'positive' : 'negative'}">${value > 0 ? '+' : ''}${value}</span>
      </div>
    `;
  }).join('');
}

function setupPrimaryRangeControls() {
  const buttons = document.querySelectorAll('.primary-range .rangeBtn');
  if (!buttons.length) return;

  // Ensure idempotent binding.
  if (buttons[0].dataset._bound === '1') return;
  buttons.forEach(btn => {
    btn.dataset._bound = '1';
    btn.addEventListener('click', () => {
      const r = btn.dataset.range;
      if (!r) return;
      primaryRange = r;
      buttons.forEach(b => b.classList.toggle('active', b.dataset.range === r));
      const market = analysisResults?.market;
      if (market?.price_series?.length) {
        const rangePos = isRangePositive(market.price_series, r);
        drawPrimaryChart(market.price_series, rangePos);
      }
    });
  });
}

/**
 * Determine whether the price went up or down over the given range.
 * Used to pick green (up) vs red (down) for chart line + fill.
 */
function isRangePositive(series, range) {
  const sliced = sliceSeriesByRange(series, range);
  if (sliced.length < 2) return true; // default green if insufficient data
  const first = sliced[0].close;
  const last = sliced[sliced.length - 1].close;
  return last >= first;
}

function sliceSeriesByRange(series, range) {
  if (!Array.isArray(series) || series.length === 0) return [];
  const n = series.length;
  switch (range) {
    case '5D':
      return series.slice(Math.max(0, n - 6));
    case '1M':
      return series.slice(Math.max(0, n - 22));
    case '6M':
      return series.slice(Math.max(0, n - 132));
    default:
      return series;
  }
}

function calcRangePercentage(series, range) {
  const sliced = sliceSeriesByRange(series, range);
  if (sliced.length < 2) return null;
  const first = sliced[0].close;
  const last = sliced[sliced.length - 1].close;
  if (!first || first === 0) return null;
  return ((last - first) / first) * 100;
}

function updateRangePercentages(series) {
  const ranges = ['5D', '1M', '6M'];
  for (const r of ranges) {
    const el = document.getElementById(`pct-${r}`);
    if (!el) continue;
    const pct = calcRangePercentage(series, r);
    if (pct === null) {
      el.textContent = '';
      el.className = 'range-pct';
    } else {
      const sign = pct >= 0 ? '+' : '';
      el.textContent = `${sign}${pct.toFixed(1)}%`;
      el.className = `range-pct ${pct >= 0 ? 'positive' : 'negative'}`;
    }
  }
}

function fmtDate(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString(undefined, { month: 'short', day: '2-digit' });
}

function drawPrimaryChart(fullSeries, isPositive) {
  if (!primaryChartCanvas) return;
  const series = sliceSeriesByRange(fullSeries, primaryRange);
  const ctx = primaryChartCanvas.getContext('2d');
  const w = primaryChartCanvas.width;
  const h = primaryChartCanvas.height;
  ctx.clearRect(0, 0, w, h);

  const prices = series.map(p => p.close).filter(v => typeof v === 'number');
  if (prices.length < 2) return;

  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;

  const pad = { l: 34, r: 10, t: 10, b: 18 };
  const gw = w - pad.l - pad.r;
  const gh = h - pad.t - pad.b;

  // Y-axis labels
  ctx.font = '11px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
  ctx.fillStyle = 'rgba(203, 213, 225, 0.9)';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  const yTop = pad.t;
  const yBot = pad.t + gh;
  ctx.fillText(max.toFixed(2), 6, yTop + 2);
  ctx.fillText(min.toFixed(2), 6, yBot - 2);

  // Price line
  ctx.beginPath();
  ctx.strokeStyle = isPositive ? '#10B981' : '#EF4444';
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  series.forEach((p, i) => {
    const x = pad.l + (i / (series.length - 1)) * gw;
    const y = pad.t + gh - ((p.close - min) / range) * gh;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Fill
  const gradient = ctx.createLinearGradient(0, pad.t, 0, pad.t + gh);
  gradient.addColorStop(0, isPositive ? 'rgba(16, 185, 129, 0.18)' : 'rgba(239, 68, 68, 0.18)');
  gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
  ctx.lineTo(pad.l + gw, pad.t + gh);
  ctx.lineTo(pad.l, pad.t + gh);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  // Hover (crosshair + label)
  const onMove = (ev) => {
    const rect = primaryChartCanvas.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    if (x < pad.l || x > pad.l + gw || y < pad.t || y > pad.t + gh) {
      primaryHover.style.display = 'none';
      drawPrimaryChart(fullSeries, isPositive);
      return;
    }

    const rel = (x - pad.l) / gw;
    const idx = Math.min(series.length - 1, Math.max(0, Math.round(rel * (series.length - 1))));
    const point = series[idx];
    const px = pad.l + (idx / (series.length - 1)) * gw;
    const py = pad.t + gh - ((point.close - min) / range) * gh;

    // redraw base
    ctx.clearRect(0, 0, w, h);
    // draw again without recursion to avoid listeners churn
    // (call the same routine pieces inline)
    ctx.font = '11px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
    ctx.fillStyle = 'rgba(203, 213, 225, 0.9)';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(max.toFixed(2), 6, yTop + 2);
    ctx.fillText(min.toFixed(2), 6, yBot - 2);

    ctx.beginPath();
    ctx.strokeStyle = isPositive ? '#10B981' : '#EF4444';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    series.forEach((p, i) => {
      const xx = pad.l + (i / (series.length - 1)) * gw;
      const yy = pad.t + gh - ((p.close - min) / range) * gh;
      if (i === 0) ctx.moveTo(xx, yy);
      else ctx.lineTo(xx, yy);
    });
    ctx.stroke();
    const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + gh);
    grad.addColorStop(0, isPositive ? 'rgba(16, 185, 129, 0.18)' : 'rgba(239, 68, 68, 0.18)');
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.lineTo(pad.l + gw, pad.t + gh);
    ctx.lineTo(pad.l, pad.t + gh);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // crosshair
    ctx.save();
    ctx.strokeStyle = 'rgba(226, 232, 240, 0.35)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(px, pad.t);
    ctx.lineTo(px, pad.t + gh);
    ctx.stroke();
    ctx.restore();

    // point
    ctx.beginPath();
    ctx.fillStyle = '#e2e8f0';
    ctx.arc(px, py, 3, 0, Math.PI * 2);
    ctx.fill();

    // label
    const dateStr = fmtDate(point.date || point.timestamp || point.t);
    primaryHover.textContent = `${dateStr}  $${point.close.toFixed(2)}`;
    primaryHover.style.display = 'block';
  };

  const onLeave = () => {
    primaryHover.style.display = 'none';
    drawPrimaryChart(fullSeries, isPositive);
  };

  // Ensure we don't stack listeners by clearing existing references
  primaryChartCanvas.onmousemove = onMove;
  primaryChartCanvas.onmouseleave = onLeave;
}

// Helper: escape HTML
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// -------------------------------------------------------------------
// S&P 500 Market Comparison
// -------------------------------------------------------------------

/**
 * Populate the "vs S&P 500" comparison section.
 * Pulls the SPY series from analysisResults.markets and compares range %
 * against the primary ticker's series.
 */
function populateMarketComparison(primaryTicker, tickerSeries) {
  const compSection = document.getElementById('market-comparison');
  if (!compSection) return;

  // Find SPY in the markets array
  const markets = analysisResults?.markets || [];
  const spyData = markets.find(m => m.ticker && m.ticker.toUpperCase() === 'SPY');
  const spySeries = spyData?.price_series;

  if (!spySeries || spySeries.length < 2 || !tickerSeries || tickerSeries.length < 2) {
    compSection.style.display = 'none';
    return;
  }

  compSection.style.display = '';

  const ranges = ['5D', '1M', '6M'];

  // Set ticker labels
  for (const r of ranges) {
    const lbl = document.getElementById(`comp-ticker-label-${r}`);
    if (lbl) lbl.textContent = primaryTicker || 'TICK';
  }

  let tickerWins = 0;
  let spyWins = 0;

  for (const r of ranges) {
    const tickerPct = calcRangePercentage(tickerSeries, r);
    const spyPct = calcRangePercentage(spySeries, r);

    const tickerEl = document.getElementById(`comp-ticker-${r}`);
    const spyEl = document.getElementById(`comp-spy-${r}`);

    if (tickerEl) {
      if (tickerPct !== null) {
        const sign = tickerPct >= 0 ? '+' : '';
        tickerEl.textContent = `${sign}${tickerPct.toFixed(1)}%`;
        tickerEl.className = `comp-value ${tickerPct >= 0 ? 'positive' : 'negative'}`;
      } else {
        tickerEl.textContent = '—';
        tickerEl.className = 'comp-value';
      }
    }

    if (spyEl) {
      if (spyPct !== null) {
        const sign = spyPct >= 0 ? '+' : '';
        spyEl.textContent = `${sign}${spyPct.toFixed(1)}%`;
        spyEl.className = `comp-value ${spyPct >= 0 ? 'positive' : 'negative'}`;
      } else {
        spyEl.textContent = '—';
        spyEl.className = 'comp-value';
      }
    }

    // Track who's outperforming
    if (tickerPct !== null && spyPct !== null) {
      if (tickerPct > spyPct) tickerWins++;
      else if (spyPct > tickerPct) spyWins++;
    }
  }

  // Verdict
  const verdictEl = document.getElementById('comparison-verdict');
  if (verdictEl) {
    if (tickerWins > spyWins) {
      verdictEl.textContent = '▲ Outperforming market';
      verdictEl.className = 'comparison-verdict outperform';
    } else if (spyWins > tickerWins) {
      verdictEl.textContent = '▼ Underperforming market';
      verdictEl.className = 'comparison-verdict underperform';
    } else {
      verdictEl.textContent = '● Tracking market';
      verdictEl.className = 'comparison-verdict tracking';
    }
  }
}
