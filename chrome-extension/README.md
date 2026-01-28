# Finance News Analyzer - Chrome Extension

A Chrome extension that analyzes financial news articles in real-time, detecting stock tickers, highlighting sensational claims, and showing interactive stock charts on hover.

## Features

- **📊 Ticker Detection**: Automatically identifies the primary stock ticker mentioned in an article
- **⚡ Sensational Claims**: Detects and highlights the top 3 most impactful claims (e.g., "stock dropped 10%")
- **📈 Hover Charts**: Hover over highlighted text to see an interactive stock price chart
- **🎯 Smart Highlighting**: Yellow highlights on key financial sentences in the article
- **🔗 Backend Integration**: Connects to the Finance News Analyzer backend for AI-powered analysis

## Installation

### Load as Unpacked Extension (Development)

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `chrome-extension` directory
5. The extension icon should appear in your toolbar

### Generate Proper Icons (Optional)

The extension includes placeholder icons. To generate proper icons from the SVG:

```bash
# Using ImageMagick
cd icons
convert -background none -resize 16x16 icon.svg icon16.png
convert -background none -resize 32x32 icon.svg icon32.png
convert -background none -resize 48x48 icon.svg icon48.png
convert -background none -resize 128x128 icon.svg icon128.png
```

Or use an online converter like [CloudConvert](https://cloudconvert.com/svg-to-png).

## Usage

1. **Start the Backend**: Make sure the Finance News Analyzer backend is running:
   ```bash
   cd ../backend
   uvicorn app.main:app --reload
   ```

2. **Navigate to a Financial Article**: Go to any news article about stocks/finance (e.g., CNBC, Bloomberg, Yahoo Finance)

3. **Click the Extension Icon**: Opens the analyzer popup

4. **Click "Analyze Article"**: The extension will:
   - Extract the article content
   - Send it to the backend for analysis
   - Display the primary ticker and price change
   - Highlight sensational claims in yellow

5. **Hover Over Highlights**: Move your mouse over any highlighted text to see an interactive stock chart

6. **Click Claims in Popup**: Clicking a claim in the popup scrolls to that text in the article

## Configuration

### Backend URL

By default, the extension connects to `http://localhost:8000`. You can change this in the popup footer.

For production, you might use:
- A deployed backend URL
- A cloud function endpoint

## File Structure

```
chrome-extension/
├── manifest.json          # Extension configuration
├── popup/
│   ├── popup.html         # Extension popup UI
│   ├── popup.css          # Popup styles
│   └── popup.js           # Popup logic
├── content/
│   ├── content.js         # Content script (runs on pages)
│   └── styles.css         # Highlight and tooltip styles
├── background/
│   └── service-worker.js  # Background service worker
├── icons/
│   ├── icon.svg           # Source icon
│   ├── icon16.png         # Toolbar icon
│   ├── icon32.png         # Extension list icon
│   ├── icon48.png         # Extension page icon
│   └── icon128.png        # Chrome Web Store icon
└── README.md              # This file
```

## Development

### Key Components

1. **Popup** (`popup/`): The UI that appears when clicking the extension icon
   - Shows analysis results
   - Manages state (initial, loading, results, error)
   - Draws mini stock chart

2. **Content Script** (`content/`): Injected into web pages
   - Extracts article content
   - Highlights claims in yellow
   - Shows stock chart on hover
   - Handles scroll-to-claim navigation

3. **Background Worker** (`background/`): Runs in the background
   - Handles installation
   - Can proxy API calls if needed

### Styling

- Uses a dark theme (slate/gray palette)
- Accent color: Green (#10B981) for positive, Red (#EF4444) for negative
- Highlight color: Yellow/Amber (#F59E0B)

### API Integration

The extension calls the backend `/analyze` endpoint with:
```json
{
  "text": "Article content...",
  "url": "https://example.com/article"
}
```

And expects a response with:
- `entities.primary_ticker`
- `market.price_series`
- `market.day_move_pct`
- `claims[]` with numbers

## Troubleshooting

### Extension Not Working

1. Check that the backend is running (`http://localhost:8000/docs`)
2. Look for errors in the browser console (F12 → Console)
3. Check extension errors at `chrome://extensions/`

### CORS Issues

If you get CORS errors, ensure the backend allows requests from Chrome extensions:
```python
# In backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific extension origin
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Highlights Not Appearing

- Some sites have complex DOM structures that make text matching difficult
- Try refreshing the page and analyzing again
- Check browser console for errors

## License

MIT
