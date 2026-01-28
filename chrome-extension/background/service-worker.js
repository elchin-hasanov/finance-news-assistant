/**
 * Finance News Analyzer - Background Service Worker
 * Handles background tasks and message passing
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
});

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
