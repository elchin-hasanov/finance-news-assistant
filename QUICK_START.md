# 🚀 Quick Start Guide - v2.0

## What's New in v2.0?

Your Finance News Assistant now has **professional-grade market analytics** and **sentiment analysis**!

### ✨ New Features at a Glance

1. **📊 Enhanced Market Metrics**
   - 52-week high/low with visual range
   - Market cap, P/E ratio, Beta
   - RSI-14, Moving Averages (50d, 200d)
   - Unusual volume alerts
   - Sector vs. S&P 500 comparison

2. **💬 Sentiment Analysis**
   - -1.0 to +1.0 sentiment score
   - Finance-specific word detection
   - Visual sentiment breakdown

---

## 🎯 How to Use

### 1. **Analyze an Article**
Paste any financial news URL or text → Click "Analyze"

### 2. **View Market Context**
The app now shows comprehensive market data including:

#### **Company Overview**
- **Sector badge** (e.g., "Technology")
- **Industry badge** (e.g., "Software")
- **Market cap** ($XXB / $XXT)

#### **Performance Indicators**
- **Today's move** (green/red)
- **52W high/low** with progress bar
- **RSI-14** with overbought/oversold warnings
- **Moving averages** (50-day, 200-day)

#### **Market Context**
- **S&P 500 performance** today
- **Sector performance** today
- **Relative strength** (how stock performs vs. sector)

#### **Risk Indicators**
- **Volatility regime** (Low/Normal/High)
- **Unusual volume** alerts (⚡ badge if volume >2x average)
- **Near 52W high** badge (📈 if within 5%)

### 3. **Check Sentiment**
New dedicated section shows:
- **Sentiment label** (Very Positive → Very Negative)
- **Score visualization** (-1.0 to +1.0)
- **Word breakdown**: Positive vs. Negative vs. Neutral

---

## 📖 Understanding the Metrics

### **RSI (Relative Strength Index)**
- **Range**: 0-100
- **>70**: Overbought (may pull back) 🔴
- **<30**: Oversold (may bounce) 🟢
- **30-70**: Normal range

### **Beta**
- **β = 1.0**: Moves with market
- **β > 1.0**: More volatile (higher risk/reward)
- **β < 1.0**: Less volatile (defensive)

### **Moving Averages**
- **50-day MA**: Short-term trend
- **200-day MA**: Long-term trend
- Price above both MAs = bullish
- Price below both MAs = bearish

### **Volatility Regime**
- **Low (<1%)**: Stable stock, low risk
- **Normal (1-3%)**: Average fluctuation
- **High (>3%)**: High risk, large swings

### **Relative Strength**
- **Positive**: Outperforming sector
- **Negative**: Underperforming sector
- **Example**: Stock +3%, Sector +1% → Relative Strength: +2%

---

## 🎨 Visual Indicators

### **Color Coding**
- 🟢 **Green**: Positive (gains, good sentiment)
- 🔴 **Red**: Negative (losses, bad sentiment)
- 🟡 **Yellow/Orange**: Warnings (unusual volume, high volatility)
- 🔵 **Blue**: Informational (sector, near 52W high)

### **Badges**
- **Sector/Industry**: Blue/Purple rounded badges
- **Unusual Volume**: ⚡ Orange badge
- **Near 52W High**: 📈 Blue badge
- **Volatility**: Color-coded (Green=Low, Yellow=Normal, Red=High)

---

## 💡 Example Use Cases

### **For Day Traders**
1. Check **RSI** for entry/exit signals
2. Look for **unusual volume** (potential catalyst)
3. Monitor **relative strength** vs. sector

### **For Investors**
1. Review **52W range** (buying near lows?)
2. Check **P/E ratio** and **market cap** (valuation)
3. Assess **volatility regime** (risk tolerance)
4. Compare **sector performance** (rotation opportunity?)

### **For Analysts**
1. Use **sentiment** to gauge article tone
2. Cross-reference **claims** with market reaction
3. Track **relative strength** for sector analysis
4. Monitor **beta** for portfolio risk management

---

## 🔧 Tips & Tricks

### **Finding the Best Insights**
1. **Compare sentiment with price action**
   - Positive article + stock down = potential buying opportunity
   - Negative article + stock up = market doesn't care

2. **Watch for divergences**
   - High RSI + positive news = may be overbought
   - Low RSI + negative news = may be oversold

3. **Sector context matters**
   - Stock down 2% but sector down 5% = relative outperformance
   - Use sector comparison to find hidden strength

4. **Volume confirms moves**
   - Unusual volume + big move = legitimate catalyst
   - Small volume + big move = may reverse

### **Interpreting Sentiment**
- **Very Positive** (>0.5): Bullish article, may be hyped
- **Positive** (0.2-0.5): Optimistic tone
- **Neutral** (-0.2 to 0.2): Balanced reporting
- **Negative** (-0.5 to -0.2): Pessimistic tone
- **Very Negative** (<-0.5): Bearish article, may be overdone

### **Red Flags to Watch**
- ⚠️ **High hype score + very positive sentiment** = Be skeptical
- ⚠️ **RSI >70 + unusual volume** = Potential reversal
- ⚠️ **High volatility regime** = Higher risk
- ⚠️ **Large gap from 52W high** = May need catalyst to recover

---

## 🐛 Troubleshooting

### **"No market data available"**
- Stock may not be in S&P 500 or public markets
- Try using ticker directly in article
- Check if company is publicly traded

### **Empty sentiment scores**
- Article may be very short
- Text may be technical/numeric (few sentiment words)
- This is normal for press releases

### **Missing technical indicators**
- Stock may have limited trading history
- Some metrics need 50+ days of data
- Recent IPOs may not have full data

---

## 📚 Further Reading

### **Technical Analysis**
- [RSI Explained](https://www.investopedia.com/terms/r/rsi.asp)
- [Moving Averages](https://www.investopedia.com/terms/m/movingaverage.asp)
- [Beta](https://www.investopedia.com/terms/b/beta.asp)

### **Market Data**
- Data sourced from Yahoo Finance (yfinance)
- Sector ETFs: XLK, XLF, XLV, XLE, etc.
- S&P 500 index tracked via SPY ETF

### **Sentiment Analysis**
- Lexicon-based approach (not ML)
- Finance-specific terminology
- Future: May upgrade to FinBERT (ML model)

---

## 🎓 Educational Examples

### **Example 1: Tech Stock Analysis**
```
Article: "Apple beats earnings expectations with strong iPhone sales"

Expected Insights:
✓ Sector: Technology (Blue badge)
✓ Sentiment: Very Positive (profit, beat, strong = positive words)
✓ Hype: Low-Medium (factual claims about earnings)
✓ Market: Check if stock moved up on earnings day
✓ Volume: Likely unusual (earnings catalyst)
✓ Relative Strength: Compare to XLK (tech sector)
```

### **Example 2: Financial Crisis Article**
```
Article: "Bank faces bankruptcy concerns amid declining deposits"

Expected Insights:
✓ Sector: Financials (Blue badge)
✓ Sentiment: Very Negative (bankruptcy, declining = negative words)
✓ Hype: Low (serious factual reporting)
✓ Market: Likely down significantly
✓ Volatility: High regime
✓ RSI: Possibly <30 (oversold)
```

### **Example 3: Neutral Announcement**
```
Article: "Company announces board meeting scheduled for next month"

Expected Insights:
✓ Sentiment: Neutral (no positive/negative words)
✓ Hype: Low
✓ Market: Likely unchanged
✓ Claims: Few or none
```

---

## ⚡ Power User Features

### **Multi-Company Articles**
- App automatically detects all companies mentioned
- Click tabs to switch between company charts
- Each tab shows that company's market metrics

### **Cross-Referencing Data**
1. Check **sentiment** (article tone)
2. Compare with **market move** (did market agree?)
3. Look at **relative strength** (vs. peers)
4. Check **volume** (was move significant?)

### **Historical Context**
- **52W range** shows where stock is in annual cycle
- **Moving averages** reveal trend direction
- **Volatility regime** indicates current risk level

---

## 🔮 Coming Soon

- **Historical sentiment tracking** (sentiment over time)
- **Competitor comparison** (side-by-side metrics)
- **Event detection** (earnings, product launches)
- **ML-based sentiment** (FinBERT integration)
- **Watchlists** (save interesting analyses)
- **Email alerts** (new articles about followed tickers)

---

## 💬 Feedback

This is v2.0 with major enhancements! If you find bugs or have feature requests, please open an issue on GitHub.

**Repository**: https://github.com/elchin-hasanov/finance-news-assistant

---

**Happy Analyzing! 📈**
