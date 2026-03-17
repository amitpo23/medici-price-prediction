# Price Analysis Project — Claude Code Guide

## Project Overview

This project analyzes prices from Order Sales Office data and provides:

1. **Advanced price visualizations** — candlestick, trend lines with confidence bands, multi-office comparison, waterfall decomposition, heatmaps
2. **Price prediction** — forecasting whether prices will go up or down, using ARIMA, Exponential Smoothing, and Prophet models
3. **Clear signals** — a directional signal ("price expected to RISE/FALL") with confidence level (HIGH/MODERATE/LOW)

## CRITICAL RULES

### Work with REAL data only

Do NOT generate synthetic, mock, or dummy data. All analysis must run on actual data from one of these sources:

- **SQL query output** from the Order Sales Office database
- **CSV/Excel files** already filtered and provided by the user
- **Live database connection** if configured

If no data is available, **ask the user** where the data is. Do not proceed without real data.

### Do NOT modify existing project structure

The project already has a working set of skills from the `data` plugin:

- `data-visualization` — general charts (line, bar, histogram, heatmap, scatter)
- `statistical-analysis` — descriptive stats, trend analysis, outlier detection
- `interactive-dashboard-builder` — HTML dashboards with Chart.js
- `sql-queries` — SQL generation for all major dialects
- `data-exploration` — data profiling and quality checks

**Do not change, overwrite, or remove any of these.** The two new skills in this project ADD capabilities on top of what already exists.

### When to use which skill

| Task | Use This Skill |
|---|---|
| General line chart, bar chart, histogram | `data-visualization` (existing) |
| Candlestick, waterfall, price trend + bands | `price-visualization` (NEW) |
| Moving average, basic trend, outlier detection | `statistical-analysis` (existing) |
| ARIMA, Prophet, ETS forecast with signal | `price-prediction` (NEW) |
| Interactive HTML dashboard | `interactive-dashboard-builder` (existing) |
| SQL to extract price data | `sql-queries` (existing) |

Use multiple skills together. For example: use `sql-queries` to pull data, then `price-prediction` to forecast, then `price-visualization` to chart the results.

## New Skills — What They Add

### 1. price-visualization

**Location:** `skills/price-visualization/SKILL.md`

Adds these chart types (all plotly, interactive):

- **Candlestick (OHLC)** — standard price movement chart with open/high/low/close. Includes `aggregate_to_ohlc()` function to convert single-price data into OHLC format by week or month.
- **Trend + Confidence Bands** — smoothed trend line with shaded uncertainty range. Supports optional forward forecast with expanding confidence band.
- **Multi-Entity Comparison** — compare prices across offices, products, regions on one chart. Supports normalization (index to 100) for comparing entities with different price levels. Includes sparkline grid for many entities.
- **Waterfall Decomposition** — break down what caused a price change from period A to B (e.g., raw materials +$8, logistics +$5, discount -$2).
- **Price Heatmap** — two-dimensional view of prices (e.g., product x month), color-coded to highlight hot spots.
- **Box Plot Timeline** — monthly/weekly box plots showing price distribution and volatility over time.

**Key functions:**

```python
create_candlestick(df, date_col, open_col, high_col, low_col, close_col, ...)
aggregate_to_ohlc(df, date_col, price_col, period='W')
create_trend_with_bands(df, date_col, price_col, window=14, confidence=1.96, ...)
create_price_comparison(df, date_col, price_col, group_col, normalize=False, ...)
create_price_sparklines(df, date_col, price_col, group_col, ...)
create_price_waterfall(categories, values, ...)
create_price_heatmap(df, date_col, group_col, price_col, ...)
create_price_boxplot_timeline(df, date_col, price_col, period='M', ...)
```

All functions accept **generic column names** — map them to whatever columns exist in the actual data.

### 2. price-prediction

**Location:** `skills/price-prediction/SKILL.md`

Adds forecasting models and a signal system:

**Models (in order of complexity):**

1. **ETS (Exponential Smoothing)** — works with any data size (even 10+ points). Captures trend and optional seasonality. Always available via statsmodels.
2. **ARIMA/SARIMAX** — needs 30+ data points. Auto-tunes parameters via pmdarima. Captures autocorrelation patterns.
3. **Prophet** — needs 100+ data points. Best for daily data with holidays and complex seasonality. Optional dependency.

**Signal System:**

The `generate_price_signal()` function translates any forecast into:

```json
{
  "direction": "UP",
  "confidence": "HIGH",
  "confidence_score": 0.85,
  "current_price": 102.50,
  "forecast_avg": 108.30,
  "expected_change_pct": 5.7,
  "forecast_range": [104.20, 112.40],
  "model": "ARIMA(1,1,1)",
  "summary": "Price expected to go UP by ~5.7% (confidence: HIGH)..."
}
```

**Multi-Model Comparison:**

The `compare_models()` function runs all available models and produces a consensus:

```json
{
  "direction": "UP",
  "model_agreement": "2/3 models agree",
  "agreement_pct": 67,
  "individual_signals": { ... }
}
```

**Standard Workflow:**

1. `prepare_price_series(df, date_col, price_col, freq='W')` — clean and resample data
2. Choose model based on data size (see model selection guide in SKILL.md)
3. Run forecast → get forecast + confidence intervals
4. `generate_price_signal()` → get UP/DOWN signal with confidence
5. Visualize with `plot_forecast()` or use `price-visualization` skill

## Dependencies

Install before using the new skills:

```bash
# Core (required)
pip install plotly pandas numpy statsmodels scipy kaleido --break-system-packages

# For ARIMA auto-tuning (recommended)
pip install pmdarima --break-system-packages

# For Prophet (optional — only for complex daily seasonality)
pip install prophet --break-system-packages
```

## Data Flow

```
Order Sales Office DB
        |
        v
    SQL Query (use sql-queries skill)
        |
        v
    CSV / DataFrame with price data
        |
        +---> price-visualization skill ---> Interactive HTML charts
        |
        +---> price-prediction skill ---> Forecast + Signal JSON
        |
        +---> Both together ---> Forecast visualization with trend + bands
        |
        v
    interactive-dashboard-builder skill ---> Full dashboard with all charts
```

## Example Prompts for Claude Code

Here are example prompts to use with Claude Code. Replace with actual file paths and column names:

**Visualization:**
> "Read the file sales_data.csv (columns: order_date, office_name, unit_price) and create a candlestick chart for weekly prices of the Tel Aviv office, plus a comparison chart of all offices."

**Prediction:**
> "Load the monthly price averages from prices_monthly.csv and predict whether the price will go up or down in the next 6 months. Run multiple models and show me the consensus."

**Full pipeline:**
> "Connect to the sales database, pull the last 2 years of order prices grouped by week, create a trend chart with confidence bands, and predict the next quarter with a clear UP/DOWN signal."

## File Structure

```
price-analysis-project/
├── CLAUDE_CODE_GUIDE.md          ← This file (read first)
├── skills/
│   ├── price-visualization/
│   │   └── SKILL.md              ← Candlestick, waterfall, heatmap, etc.
│   └── price-prediction/
│       └── SKILL.md              ← ARIMA, ETS, Prophet, signals
```

These skills are designed to be placed in your Claude Code skills directory. They work alongside the existing `data` plugin skills without any conflicts.
