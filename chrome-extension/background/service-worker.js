/**
 * Finance News Analyzer - Background Service Worker
 * Handles background tasks, message passing, and dynamic icon updates
 */

// Listen for extension icon click (as backup to popup)
chrome.action.onClicked.addListener((tab) => {
  // Popup handles this, but we can add fallback behavior here
});

// Handle extension installation
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    // Set default API URL
    chrome.storage.local.set({ apiUrl: 'http://localhost:8000' });
    
    console.log('Finance News Analyzer installed!');
  }
});

// Handle messages from content script or popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'fetchData') {
    // Proxy API calls through background to avoid CORS issues
    fetchFromAPI(message.url, message.options)
      .then(data => sendResponse({ success: true, data }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true; // Keep channel open for async response
  }

  if (message.action === 'setReliabilityIcon') {
    const { tabId, score } = message;
    setDynamicIcon(tabId, score);
    sendResponse({ success: true });
    return false;
  }
});

/**
 * Draw a coloured icon on an OffscreenCanvas and set it as the extension icon.
 * Green (reliable) → Yellow (mixed) → Red (unreliable).
 */
function setDynamicIcon(tabId, score) {
  const sizes = [16, 32, 48, 128];
  const imageData = {};

  for (const size of sizes) {
    const canvas = new OffscreenCanvas(size, size);
    const ctx = canvas.getContext('2d');

    // Background rounded rect
    const r = Math.round(size * 0.1875); // ~24/128
    ctx.beginPath();
    roundRect(ctx, 0, 0, size, size, r);
    ctx.fillStyle = '#0F172A';
    ctx.fill();

    // Pick colour based on score — binary green/red
    let color;
    if (score >= 50) {
      color = '#10B981'; // green — reliable
    } else {
      color = '#EF4444'; // red — unreliable
    }

    // Draw chart line (same shape as original icon, scaled)
    const s = size / 128;
    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(2, 8 * s);
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    ctx.beginPath();
    ctx.moveTo(24 * s, 80 * s);
    ctx.lineTo(48 * s, 56 * s);
    ctx.lineTo(64 * s, 72 * s);
    ctx.lineTo(104 * s, 32 * s);
    ctx.stroke();

    // Arrow tip
    ctx.beginPath();
    ctx.moveTo(80 * s, 32 * s);
    ctx.lineTo(104 * s, 32 * s);
    ctx.lineTo(104 * s, 56 * s);
    ctx.stroke();

    // Bar chart at bottom
    const barColor1 = '#334155';
    const bars = [
      { x: 24, y: 88, w: 16, h: 24 },
      { x: 48, y: 80, w: 16, h: 32 },
    ];
    const barsColored = [
      { x: 72, y: 72, w: 16, h: 40 },
      { x: 96, y: 64, w: 16, h: 48 },
    ];

    for (const b of bars) {
      roundedBar(ctx, b.x * s, b.y * s, b.w * s, b.h * s, 2 * s, barColor1);
    }
    for (const b of barsColored) {
      roundedBar(ctx, b.x * s, b.y * s, b.w * s, b.h * s, 2 * s, color);
    }

    imageData[size] = ctx.getImageData(0, 0, size, size);
  }

  chrome.action.setIcon({ tabId, imageData });

  // Clear any old badge — the icon colour itself conveys the signal
  chrome.action.setBadgeText({ tabId, text: '' });
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function roundedBar(ctx, x, y, w, h, r, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  roundRect(ctx, x, y, w, h, r);
  ctx.fill();
}

/**
 * Fetch data from API (can be used to bypass CORS if needed)
 */
async function fetchFromAPI(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    }
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return response.json();
}
