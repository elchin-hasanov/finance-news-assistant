/**
 * Finance News Analyzer - Content Script
 * Handles article extraction, highlighting, and hover charts
 */

(function() {
  'use strict';

  // State
  let highlightedElements = [];
  let chartTooltip = null;
  let currentPriceSeries = [];
  let currentTicker = null;
  let allTickerData = {};

  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.action) {
      case 'getArticleContent':
        sendResponse(extractArticleContent());
        break;
      
      case 'highlightClaims':
        highlightClaims(message.data);
        sendResponse({ success: true });
        break;
      
      case 'clearHighlights':
        clearHighlights();
        sendResponse({ success: true });
        break;
      
      case 'scrollToClaim':
        scrollToClaim(message.claimIndex);
        sendResponse({ success: true });
        break;
    }
    return true;
  });

  /**
   * Extract article content from the page
   */
  function extractArticleContent() {
    const url = window.location.href;
    
    // Try to find article content using common selectors
    const selectors = [
      'article',
      '[role="article"]',
      '.article-content',
      '.article-body',
      '.post-content',
      '.entry-content',
      '.story-content',
      '.story-body',
      'main article',
      '.main-content article',
      '#article-body',
      '.article__body',
      '.ArticleBody-articleBody',
      '[data-component="text-block"]',
      '.caas-body',
    ];

    let articleElement = null;
    for (const selector of selectors) {
      articleElement = document.querySelector(selector);
      if (articleElement && articleElement.textContent.trim().length > 200) {
        break;
      }
    }

    // Fallback: use body but try to filter out nav/footer
    if (!articleElement) {
      articleElement = document.body;
    }

    // Get text content, cleaning up whitespace
    let text = '';
    const walker = document.createTreeWalker(
      articleElement,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode: (node) => {
          const parent = node.parentElement;
          if (!parent) return NodeFilter.FILTER_REJECT;
          
          const tag = parent.tagName.toLowerCase();
          const excludeTags = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript'];
          if (excludeTags.includes(tag)) return NodeFilter.FILTER_REJECT;
          
          // Check if hidden
          const style = window.getComputedStyle(parent);
          if (style.display === 'none' || style.visibility === 'hidden') {
            return NodeFilter.FILTER_REJECT;
          }
          
          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );

    let node;
    while (node = walker.nextNode()) {
      const trimmed = node.textContent.trim();
      if (trimmed) {
        text += trimmed + ' ';
      }
    }

    // Clean up text
    text = text
      .replace(/\s+/g, ' ')
      .replace(/\n+/g, '\n')
      .trim();

    // Limit length
    if (text.length > 50000) {
      text = text.slice(0, 50000);
    }

    return { text, url };
  }

  /**
   * Highlight claims in the article
   * Now highlights BOTH ticker symbols AND company names across the article
   */
  function highlightClaims(data) {
    clearHighlights();
    
    const { claims, primaryTicker, priceSeries, allTickers, tickerPriceSeries } = data;
    currentPriceSeries = priceSeries || [];
    currentTicker = primaryTicker;
    
    // Store all ticker data for hover charts
    allTickerData = tickerPriceSeries || {};

    // Create tooltip element
    createChartTooltip();

    // NEW APPROACH: Highlight all company names and tickers in the document
    // that we have data for (or can map to a ticker)
    highlightCompaniesAndTickers(primaryTicker);
  }

  /**
   * Find the most likely text nodes containing the evidence sentence.
   * Returns a small list to avoid over-highlighting.
   */
  function findEvidenceTextNodes(searchText, limit = 2) {
    if (!searchText || searchText.length < 10) return [];

    const normalizedSearch = searchText.toLowerCase().replace(/\s+/g, ' ').trim();
    const searchWords = normalizedSearch.split(' ').filter(w => w.length > 3);

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    const scored = [];

    let node;
    while (node = walker.nextNode()) {
      const parent = node.parentElement;
      if (!parent) continue;
      const tag = parent.tagName.toLowerCase();
      if (['script', 'style', 'noscript'].includes(tag)) continue;
      if (parent.closest('#fna-chart-tooltip')) continue;
      if (parent.closest('.fna-highlight')) continue;

      const nodeText = (node.textContent || '').toLowerCase();
      if (!nodeText || nodeText.length < 20) continue;

      const matchCount = searchWords.filter(w => nodeText.includes(w)).length;
      const threshold = Math.min(4, Math.ceil(searchWords.length * 0.6));
      if (matchCount >= threshold) {
        scored.push({ node, score: matchCount });
      }
    }

    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, limit).map(s => s.node);
  }

  /**
   * NEW: Highlight all company names and tickers across the entire document.
   * This scans for both explicit tickers (AMZN, MSFT) and company names (Amazon, Microsoft).
   */
  function highlightCompaniesAndTickers(primaryTicker) {
    const primaryUpper = primaryTicker ? String(primaryTicker).toUpperCase() : null;
    
    // Build list of all highlightable patterns: company names + tickers
    const patterns = [];
    
    // Add company names from our mapping
    for (const [name, ticker] of Object.entries(COMPANY_TO_TICKER)) {
      // Skip primary ticker's company name to avoid over-highlighting the main subject
      if (primaryUpper && ticker === primaryUpper) continue;
      patterns.push({ pattern: name, ticker, isCompanyName: true });
    }
    
    // Add explicit tickers we have data for
    const knownTickers = Object.keys(allTickerData || {}).filter(Boolean);
    for (const t of knownTickers) {
      if (primaryUpper && t === primaryUpper) continue;
      patterns.push({ pattern: t, ticker: t, isCompanyName: false });
    }
    
    // Also add tickers found in parens like (AMZN)
    // These will be matched via regex in the text node processor
    
    if (!patterns.length) return;

    // Walk through all text nodes in the document
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    const nodesToProcess = [];
    
    let node;
    while (node = walker.nextNode()) {
      const parent = node.parentElement;
      if (!parent) continue;
      const tag = parent.tagName.toLowerCase();
      if (['script', 'style', 'noscript', 'code', 'pre'].includes(tag)) continue;
      if (parent.closest('#fna-chart-tooltip')) continue;
      if (parent.closest('.fna-highlight')) continue;
      
      const text = node.textContent || '';
      if (text.length < 3) continue;
      
      // Quick check: does this node contain any of our patterns?
      const lowerText = text.toLowerCase();
      const hasMatch = patterns.some(p => lowerText.includes(p.pattern.toLowerCase()));
      
      // Also check for ticker patterns like (AMZN), $MSFT etc
      const hasTickerPattern = /\([A-Z]{1,5}\)|\$[A-Z]{1,5}\b|\b[A-Z]{2,5}\b/.test(text);
      
      if (hasMatch || hasTickerPattern) {
        nodesToProcess.push(node);
      }
    }
    
    // Process each node (in reverse to avoid DOM mutation issues)
    for (let i = nodesToProcess.length - 1; i >= 0; i--) {
      highlightPatternInTextNode(nodesToProcess[i], patterns, primaryUpper);
    }
  }

  /**
   * Highlight company names and tickers within a single text node.
   */
  function highlightPatternInTextNode(textNode, patterns, primaryUpper) {
    const parent = textNode?.parentElement;
    if (!parent) return;
    
    const original = textNode.textContent || '';
    if (!original.trim()) return;
    
    // Build a combined regex for all patterns
    // Sort by length (longest first) to match "General Motors" before "GM"
    const sortedPatterns = [...patterns].sort((a, b) => b.pattern.length - a.pattern.length);
    
    // Escape patterns for regex
    const patternParts = sortedPatterns.map(p => _escapeRegExp(p.pattern));
    
    // Also match ticker formats: (AMZN), $MSFT, NASDAQ:MSFT, plain MSFT
    // We'll handle these specially
    const tickerRx = /\(([A-Z]{1,5})\)|\$([A-Z]{1,5})\b|\b(NASDAQ|NYSE|AMEX):([A-Z]{1,5})\b|\b([A-Z]{2,5})\b/g;
    
    // Find all matches (both company names and tickers)
    const matches = [];
    
    // Find company name matches
    for (const p of sortedPatterns) {
      const rx = new RegExp(`\\b${_escapeRegExp(p.pattern)}\\b`, 'gi');
      let m;
      while ((m = rx.exec(original)) !== null) {
        matches.push({
          start: m.index,
          end: m.index + m[0].length,
          text: m[0],
          ticker: p.ticker,
        });
      }
    }
    
    // Find ticker matches
    let tm;
    while ((tm = tickerRx.exec(original)) !== null) {
      const ticker = (tm[1] || tm[2] || tm[4] || tm[5] || '').toUpperCase();
      if (!ticker || ticker.length < 2) continue;
      
      // Skip common false positives
      const stopWords = new Set([
        'CEO','CFO','EPS','ETF','SEC','FED','FOMC','USD','EUR','GDP','CPI','IPO','AI','API',
        'Q1','Q2','Q3','Q4','FY','YOY','YTD','ETFs','THE','AND','FOR','ARE','BUT','NOT','YOU',
        'ALL','CAN','HER','WAS','ONE','OUR','OUT','HAS','HIS','HOW','ITS','MAY','NEW','NOW',
        'OLD','SEE','WAY','WHO','BOY','DID','GET','HIM','HIS','LET','PUT','SAY','SHE','TOO',
        'USE'
      ]);
      if (stopWords.has(ticker)) continue;
      
      // Skip primary ticker
      if (primaryUpper && ticker === primaryUpper) continue;
      
      // Only highlight if we have data for this ticker OR it's a known company ticker
      const knownTickers = Object.keys(allTickerData || {});
      const mappedTickers = Object.values(COMPANY_TO_TICKER);
      if (!knownTickers.includes(ticker) && !mappedTickers.includes(ticker)) continue;
      
      matches.push({
        start: tm.index,
        end: tm.index + tm[0].length,
        text: tm[0],
        ticker: ticker,
      });
    }
    
    if (!matches.length) return;
    
    // Sort by position and remove overlaps (keep first/longest)
    matches.sort((a, b) => a.start - b.start);
    const filtered = [];
    for (const m of matches) {
      const last = filtered[filtered.length - 1];
      if (!last || m.start >= last.end) {
        filtered.push(m);
      }
    }
    
    if (!filtered.length) return;
    
    // Build the new fragment
    const frag = document.createDocumentFragment();
    let last = 0;
    
    for (const m of filtered) {
      if (m.start > last) {
        frag.appendChild(document.createTextNode(original.slice(last, m.start)));
      }
      
      const span = document.createElement('span');
      span.className = 'fna-highlight fna-highlight-ticker';
      span.dataset.ticker = m.ticker;
      span.textContent = m.text;
      
      span.addEventListener('mouseenter', handleHighlightHover);
      span.addEventListener('mouseleave', handleHighlightLeave);
      span.addEventListener('mousemove', handleHighlightMove);
      
      frag.appendChild(span);
      highlightedElements.push(span);
      last = m.end;
    }
    
    if (last < original.length) {
      frag.appendChild(document.createTextNode(original.slice(last)));
    }
    
    parent.replaceChild(frag, textNode);
  }

  function _escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function _tickersFromAllData() {
    const fromData = Object.keys(allTickerData || {}).filter(Boolean);
    if (fromData.length) return fromData;
    // Fallback: if backend didn't return `markets`, still attempt highlights from the page text.
    // (Hover charts will fall back to the primary series in that case.)
    const fallback = new Set();
    if (currentTicker) fallback.add(String(currentTicker).toUpperCase());
    // Scan for explicit ticker formats in the document.
    const text = (document.body?.innerText || '').slice(0, 200000);
  const rx = /\b(?:NASDAQ|NYSE|AMEX)\s*:\s*([A-Z]{1,5}(?:-[A-Z])?)\b|\$([A-Z]{1,5}(?:-[A-Z])?)\b|\(([A-Z]{1,5}(?:-[A-Z])?)\)/g;
    let m;
    while ((m = rx.exec(text)) !== null) {
  const t = (m[1] || m[2] || m[3] || '').toUpperCase();
      if (t && t.length >= 2) fallback.add(t);
    }
    return Array.from(fallback);
  }

  /**
   * Replace occurrences of known tickers in a single text node with individual highlight spans.
   * This allows multiple tickers in a paragraph to be highlighted separately.
   */
  function highlightTickersInTextNode(textNode, claimIndex, primaryTicker) {
    const parent = textNode?.parentElement;
    if (!parent) return;

    const original = textNode.textContent || '';
    if (!original.trim()) return;

  // Candidate tickers are the ones we actually have chart data for.
  // If we don't have per-ticker data, `_tickersFromAllData` returns a small best-effort list.
  const known = _tickersFromAllData();
    if (!known.length) return;

    // Build regex for known tickers only (avoid highlighting random ALLCAPS tokens).
    const parts = known
      .filter(t => t && t.length >= 1)
      .map(t => _escapeRegExp(t))
      .sort((a, b) => b.length - a.length);

    // Match bare tickers plus common wrappers like (MSFT), $MSFT, NASDAQ:MSFT.
    // We avoid strict \b boundaries on the left to allow "(" or "$".
    const rx = new RegExp(
      `(?:\\$|\\b(?:NASDAQ|NYSE|AMEX)\\s*:\\s*)?` +
      `(?:\\(|\\[)?` +
      `(${parts.join('|')})` +
      `(?:\\)|\\])?`,
      'g'
    );
    if (!rx.test(original)) return;

    rx.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0;
    let m;

    while ((m = rx.exec(original)) !== null) {
      const start = m.index;
      const end = rx.lastIndex;
      if (start > last) frag.appendChild(document.createTextNode(original.slice(last, start)));

      const ticker = (m[1] || '').toUpperCase();
      if (!ticker) {
        frag.appendChild(document.createTextNode(original.slice(start, end)));
        last = end;
        continue;
      }

      // Don't highlight primary ticker inside the claim evidence if there are other tickers
      // in the same node. If it's the only ticker, allow it so the user sees something.
      const primaryUpper = primaryTicker ? String(primaryTicker).toUpperCase() : null;
      if (primaryUpper && ticker === primaryUpper) {
        // If this node contains any other known ticker, skip the primary highlight.
        const otherParts = parts.filter(p => p !== _escapeRegExp(primaryUpper));
        if (otherParts.length) {
          const othersRx = new RegExp(`(?:\\$|\\b(?:NASDAQ|NYSE|AMEX)\\s*:\\s*)?(?:\\(|\\[)?(?:${otherParts.join('|')})(?:\\)|\\])?`);
          if (othersRx.test(original)) {
            frag.appendChild(document.createTextNode(original.slice(start, end)));
            last = end;
            continue;
          }
        }
      }

      const span = document.createElement('span');
      span.className = 'fna-highlight fna-highlight-ticker';
      span.dataset.claimIndex = String(claimIndex);
      span.dataset.ticker = ticker;
      span.textContent = original.slice(start, end);

      span.addEventListener('mouseenter', handleHighlightHover);
      span.addEventListener('mouseleave', handleHighlightLeave);
      span.addEventListener('mousemove', handleHighlightMove);

      frag.appendChild(span);
      highlightedElements.push(span);
      last = end;
    }

    if (last < original.length) frag.appendChild(document.createTextNode(original.slice(last)));
    parent.replaceChild(frag, textNode);
  }
  
  // Get common names for the primary ticker
  function getPrimaryCompanyNames(ticker) {
    const names = [ticker];
    const tickerNames = {
      'AAPL': ['apple', 'aapl'],
      'TSLA': ['tesla', 'tsla'],
      'NVDA': ['nvidia', 'nvda'],
      'MSFT': ['microsoft', 'msft'],
      'GOOGL': ['google', 'alphabet', 'googl', 'goog'],
      'AMZN': ['amazon', 'amzn'],
      'META': ['meta', 'facebook', 'fb'],
      'NFLX': ['netflix', 'nflx'],
      'JPM': ['jpmorgan', 'jp morgan', 'chase', 'jpm'],
      'BA': ['boeing', 'ba'],
      'DIS': ['disney', 'dis'],
      'AMD': ['amd', 'advanced micro'],
      'INTC': ['intel', 'intc'],
      'CRM': ['salesforce', 'crm'],
      'PYPL': ['paypal', 'pypl'],
      'UBER': ['uber'],
      'COIN': ['coinbase', 'coin'],
      'F': ['ford'],
      'GM': ['general motors', 'gm'],
    };
    return tickerNames[ticker?.toUpperCase()] || [ticker?.toLowerCase()].filter(Boolean);
  }

  // COMPANY_TO_TICKER is now loaded from companyMapping.js (1000+ entries)
  // It maps company names and aliases to ticker symbols
  
  // Extract ticker symbol from text
  function extractTickerFromText(text) {
    if (!text) return null;
    // Prefer explicit formats: $TSLA or NASDAQ:TSLA
    const explicit = text.match(/\b(?:NASDAQ|NYSE|AMEX)\s*:\s*([A-Z]{1,5}(?:-[A-Z])?)\b|\$([A-Z]{1,5}(?:-[A-Z])?)\b/);
    if (explicit) return (explicit[1] || explicit[2] || null);

    // Otherwise, match a bare ticker but only if it looks like a real equity ticker.
    // Avoid common false positives.
    const stop = new Set([
      'CEO','CFO','EPS','ETF','SEC','FED','FOMC','USD','EUR','GDP','CPI','IPO','AI','API',
      'Q1','Q2','Q3','Q4','FY','YOY','YTD','ETFs'
    ]);
    const m = text.match(/\b([A-Z]{2,5})\b/);
    if (!m) return null;
    const t = m[1];
    if (stop.has(t)) return null;
    return t;
  }

  /**
   * Create the chart tooltip element
   */
  function createChartTooltip() {
    if (chartTooltip) return;

    chartTooltip = document.createElement('div');
    chartTooltip.id = 'fna-chart-tooltip';
    chartTooltip.innerHTML = `
      <div class="fna-tooltip-header">
        <span class="fna-tooltip-ticker">STOCK</span>
        <span class="fna-tooltip-change">0.00%</span>
      </div>
      <div class="fna-tooltip-subheader">
        <span class="fna-tooltip-price">—</span>
        <div class="fna-range" role="tablist" aria-label="Range">
          <button class="fna-range-btn" data-range="5D" type="button">5D</button>
          <button class="fna-range-btn active" data-range="1M" type="button">1M</button>
          <button class="fna-range-btn" data-range="6M" type="button">6M</button>
        </div>
      </div>
      <div class="fna-chart-container">
        <canvas class="fna-tooltip-chart" width="300" height="140"></canvas>
        <div class="fna-yaxis">
          <div class="fna-yaxis-max">—</div>
          <div class="fna-yaxis-mid">—</div>
          <div class="fna-yaxis-min">—</div>
        </div>
        <div class="fna-chart-crosshair"></div>
        <div class="fna-chart-hover-info">
          <span class="fna-hover-date"></span>: <span class="fna-hover-price"></span>
        </div>
      </div>
      <div class="fna-tooltip-footer">
        <div class="fna-tooltip-dates">
          <span class="fna-tooltip-start-date"></span>
          <span class="fna-tooltip-end-date"></span>
        </div>
        <span class="fna-tooltip-period"></span>
      </div>
    `;
    document.body.appendChild(chartTooltip);
    
    // Add mousemove listener to chart for interactive crosshair
    const chartContainer = chartTooltip.querySelector('.fna-chart-container');
    chartContainer.addEventListener('mousemove', handleChartHover);
    chartContainer.addEventListener('mouseleave', handleChartLeave);

    // Range selection
    chartTooltip.querySelectorAll('.fna-range-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        chartTooltip.querySelectorAll('.fna-range-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        chartTooltip.dataset.range = btn.dataset.range;
        // Redraw using current series but filtered for the chosen range.
        drawTooltipChart();
      });
    });

  chartTooltip.dataset.range = '1M';
  }
  
  // Handle hovering over the chart for crosshair and point info
  function handleChartHover(e) {
  const series = getDisplayedSeries();
  if (!series.length) return;
    
    const canvas = chartTooltip.querySelector('.fna-tooltip-chart');
    const crosshair = chartTooltip.querySelector('.fna-chart-crosshair');
    const hoverInfo = chartTooltip.querySelector('.fna-chart-hover-info');
    const hoverDate = chartTooltip.querySelector('.fna-hover-date');
    const hoverPrice = chartTooltip.querySelector('.fna-hover-price');
    
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const padding = 30;
    const chartWidth = canvas.width - padding * 2;
    
    // Calculate which data point we're hovering over
    const relX = Math.max(0, Math.min(chartWidth, x - padding));
  const dataIndex = Math.round((relX / chartWidth) * (series.length - 1));
  const dataPoint = series[dataIndex];
    
    if (dataPoint) {
      // Position crosshair
  const pointX = padding + (dataIndex / (series.length - 1 || 1)) * chartWidth;
      crosshair.style.left = `${pointX}px`;
      crosshair.style.display = 'block';
      
      // Show hover info
      const date = new Date(dataPoint.date);
      const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      hoverDate.textContent = dateStr;
      hoverPrice.textContent = `$${dataPoint.close.toFixed(2)}`;
      hoverInfo.style.display = 'flex';
      
      // Redraw chart with highlighted point
      drawTooltipChart(dataIndex);
    }
  }
  
  function handleChartLeave() {
    const crosshair = chartTooltip.querySelector('.fna-chart-crosshair');
    const hoverInfo = chartTooltip.querySelector('.fna-chart-hover-info');
    if (crosshair) crosshair.style.display = 'none';
    if (hoverInfo) hoverInfo.style.display = 'none';
    drawTooltipChart(); // Redraw without highlight
  }

  // Legacy API – kept for compatibility but now unused.
  function highlightTextInPage() {}

  /**
   * Handle hover on highlighted text
   */
  function handleHighlightHover(e) {
    if (!chartTooltip) return;

    // Get ticker for this specific highlight (may differ from primary)
    const highlightTicker = (e.target.dataset.ticker || currentTicker || '').toUpperCase();

    // Swap series based on highlighted ticker.
    // If we don't have a series for that ticker, fall back to primary.
    const seriesForHighlight = allTickerData?.[highlightTicker];
    const seriesForPrimary = allTickerData?.[(currentTicker || '').toUpperCase()];
    const nextSeries = (Array.isArray(seriesForHighlight) && seriesForHighlight.length)
      ? seriesForHighlight
      : (Array.isArray(seriesForPrimary) && seriesForPrimary.length)
        ? seriesForPrimary
        : currentPriceSeries;

    currentPriceSeries = nextSeries || [];
    if (!currentPriceSeries.length) return;

    // Update tooltip content
    const tickerEl = chartTooltip.querySelector('.fna-tooltip-ticker');
    const changeEl = chartTooltip.querySelector('.fna-tooltip-change');
    const periodEl = chartTooltip.querySelector('.fna-tooltip-period');
    const startDateEl = chartTooltip.querySelector('.fna-tooltip-start-date');
    const endDateEl = chartTooltip.querySelector('.fna-tooltip-end-date');

  tickerEl.textContent = highlightTicker || 'Stock';
    
    const displayed = getDisplayedSeries();
    if (displayed.length >= 2) {
      const first = displayed[0].close;
      const last = displayed[displayed.length - 1].close;
      const change = ((last - first) / first) * 100;
      const sign = change >= 0 ? '+' : '';
      changeEl.textContent = `${sign}${change.toFixed(2)}%`;
      changeEl.className = `fna-tooltip-change ${change >= 0 ? 'positive' : 'negative'}`;
      
      // Show date range
      const startDate = new Date(displayed[0].date);
      const endDate = new Date(displayed[displayed.length - 1].date);
      startDateEl.textContent = startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      endDateEl.textContent = endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    periodEl.textContent = `${displayed.length} days`;

    const priceEl = chartTooltip.querySelector('.fna-tooltip-price');
    const lastClose = displayed.at(-1)?.close;
    if (priceEl) priceEl.textContent = (lastClose != null) ? `$${lastClose.toFixed(2)}` : '—';

    // Draw chart
    drawTooltipChart();

    // Show tooltip
    chartTooltip.classList.add('visible');
    positionTooltip(e);
  }

  function getDisplayedSeries() {
    if (!chartTooltip) return currentPriceSeries || [];
    const range = chartTooltip.dataset.range || '1M';
    const series = currentPriceSeries || [];
    if (!series.length) return [];

    // Series is daily points. We'll approximate ranges by number of trading days.
    const byRange = {
      '5D': 6,
      '1M': 22,
      '6M': 22 * 6,
    };
    const n = byRange[range] || 22;
    return series.slice(Math.max(0, series.length - n));
  }

  /**
   * Handle mouse leave on highlighted text
   */
  function handleHighlightLeave() {
    if (chartTooltip) {
      chartTooltip.classList.remove('visible');
    }
  }

  /**
   * Handle mouse move on highlighted text
   */
  function handleHighlightMove(e) {
    positionTooltip(e);
  }

  /**
   * Position the tooltip near the cursor
   */
  function positionTooltip(e) {
    if (!chartTooltip) return;

    const padding = 15;
    const tooltipRect = chartTooltip.getBoundingClientRect();
    
    let x = e.clientX + padding;
    let y = e.clientY + padding;

    // Keep within viewport
    if (x + tooltipRect.width > window.innerWidth) {
      x = e.clientX - tooltipRect.width - padding;
    }
    if (y + tooltipRect.height > window.innerHeight) {
      y = e.clientY - tooltipRect.height - padding;
    }

    chartTooltip.style.left = `${x}px`;
    chartTooltip.style.top = `${y}px`;
  }

  /**
   * Draw the chart in the tooltip
   */
  // Store chart points for hover interaction
  let chartPoints = [];

  function drawTooltipChart(highlightIndex = -1) {
    const canvas = chartTooltip.querySelector('.fna-tooltip-chart');
  if (!canvas) return;

  const series = getDisplayedSeries();
  if (!series.length) return;

  const ctx = canvas.getContext('2d');
  const prices = series.map(p => p.close);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;

  // Update y-axis labels
  const yMax = chartTooltip.querySelector('.fna-yaxis-max');
  const yMid = chartTooltip.querySelector('.fna-yaxis-mid');
  const yMin = chartTooltip.querySelector('.fna-yaxis-min');
  if (yMax) yMax.textContent = max.toFixed(0);
  if (yMid) yMid.textContent = ((max + min) / 2).toFixed(0);
  if (yMin) yMin.textContent = min.toFixed(0);

  const padding = 8;
    const width = canvas.width - padding * 2;
    const height = canvas.height - padding * 2;

    // Clear canvas and points
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    chartPoints = [];

    // Determine color based on trend
    const isPositive = prices[prices.length - 1] >= prices[0];
    const lineColor = isPositive ? '#10B981' : '#EF4444';
    const fillColor = isPositive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)';

    // Draw grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding + (height / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(padding + width, y);
      ctx.stroke();
    }

    // Draw price line and store points
    ctx.beginPath();
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

  prices.forEach((price, i) => {
      const x = padding + (i / (prices.length - 1 || 1)) * width;
      const y = padding + height - ((price - min) / range) * height;
      
      // Store point data for hover
      chartPoints.push({
        x,
        y,
        price,
  date: series[i].date,
        index: i
      });
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.stroke();

    // Fill area under line
    ctx.lineTo(padding + width, padding + height);
    ctx.lineTo(padding, padding + height);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();

    // Draw current price dot (last point)
  const lastPoint = chartPoints[chartPoints.length - 1];
    if (lastPoint) {
      ctx.beginPath();
      ctx.arc(lastPoint.x, lastPoint.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = lineColor;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    
    // Draw highlighted point when hovering over chart
  if (highlightIndex >= 0 && highlightIndex < chartPoints.length) {
      const point = chartPoints[highlightIndex];
      // Draw vertical line at hover position
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.moveTo(point.x, padding);
      ctx.lineTo(point.x, padding + height);
      ctx.stroke();
      ctx.setLineDash([]);
      
      // Draw larger dot at hover position
      ctx.beginPath();
      ctx.arc(point.x, point.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = '#fff';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = lineColor;
      ctx.fill();
    }
  }

  /**
   * Clear all highlights
   */
  function clearHighlights() {
    highlightedElements.forEach(el => {
      const text = document.createTextNode(el.textContent);
      el.parentNode.replaceChild(text, el);
    });
    highlightedElements = [];

    if (chartTooltip) {
      chartTooltip.remove();
      chartTooltip = null;
    }
  }

  /**
   * Scroll to a specific claim
   */
  function scrollToClaim(claimIndex) {
    const el = highlightedElements.find(e => e.dataset.claimIndex === String(claimIndex));
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      
      // Flash highlight
      el.classList.add('fna-flash');
      setTimeout(() => el.classList.remove('fna-flash'), 1000);
    }
  }

})();
