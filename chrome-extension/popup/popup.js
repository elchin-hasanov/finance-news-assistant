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
    // Get article content from content script
    const response = await chrome.tabs.sendMessage(currentTabId, { action: 'getArticleContent' });
    
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
      tickerChange.className = `ticker-change ${pct >= 0 ? 'positive' : 'negative'}`;
    } else {
      changeValue.textContent = '—';
      tickerChange.className = 'ticker-change neutral';
    }

    // Draw primary chart (rich)
    if (market.price_series && market.price_series.length > 0) {
      setupPrimaryRangeControls();
      updateRangePercentages(market.price_series);
      drawPrimaryChart(market.price_series, market.day_move_pct >= 0);
    }
  } else {
    tickerSymbol.textContent = '—';
    tickerName.textContent = 'No ticker detected';
    changeValue.textContent = '—';
    tickerChange.className = 'ticker-change neutral';
  miniChart.innerHTML = '';
  }

  // Update claims
  const claims = analysisResults.claims || [];
  
  // Filter to top 3 most "sensational" (those with numbers/percentages)
  const sensationalClaims = claims
    .filter(c => c.numbers && c.numbers.length > 0)
    .slice(0, 3);

  claimsCount.textContent = sensationalClaims.length;

  if (sensationalClaims.length > 0) {
    claimsList.innerHTML = sensationalClaims.map((claim, idx) => `
      <div class="claim-item" data-index="${idx}">
        <div class="claim-text">${escapeHtml(claim.claim)}</div>
        <div class="claim-numbers">
          ${claim.numbers.map(n => `
            <span class="claim-number">${n.value}${n.unit || ''}</span>
          `).join('')}
        </div>
      </div>
    `).join('');

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
    claimsList.innerHTML = '<p class="empty-state">No sensational claims with numbers found.</p>';
  }
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
        drawPrimaryChart(market.price_series, market.day_move_pct >= 0);
      }
    });
  });
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
