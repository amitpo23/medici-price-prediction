---
name: price-visualization
description: "Advanced price visualization charts for sales and trading data: candlestick (OHLC), trend lines with confidence bands, multi-entity price comparison, waterfall decomposition, and price heatmaps. Built on plotly for full interactivity. Use this skill whenever the user needs to visualize price data, price trends, price comparisons between offices/products/regions, or any chart specifically about pricing, cost, or revenue per unit. Triggers: price chart, candlestick, OHLC, price trend, price comparison, price movement, price analysis chart, sales office pricing, waterfall price. This skill ADDS to the existing data-visualization skill — use both together when needed."
---

# Price Visualization Skill

Specialized chart patterns for visualizing price data from order/sales systems. This skill complements the general `data-visualization` skill by adding chart types that are specifically designed for price analysis: candlestick (OHLC), trend lines with confidence bands, multi-entity comparisons, waterfall decomposition, and price heatmaps.

All charts use **plotly** for interactivity (zoom, pan, hover tooltips) — this matters for price data because users need to inspect specific dates and values closely.

## When to Use Which Chart

| Question | Chart Type | Section |
|---|---|---|
| How did the price move day-by-day? (open/high/low/close) | Candlestick | Candlestick Charts |
| Is the price trending up or down? What's the forecast range? | Trend + Confidence Bands | Trend with Confidence Bands |
| How do prices compare across offices/products/regions? | Multi-Line Comparison | Multi-Entity Price Comparison |
| What caused the price change from period A to period B? | Waterfall | Waterfall Decomposition |
| Where are prices high/low across two dimensions? | Price Heatmap | Price Heatmap |
| What's the distribution of prices over time? | Box Plot Timeline | Box Plot Over Time |

## Data Expectations

This skill is designed to work with any DataFrame that has price data. The column names below are examples — Claude should map them to whatever columns exist in the actual data. The key concept is:

- **date/time column**: when the price was recorded
- **price column(s)**: the numeric value(s) — could be a single price, or open/high/low/close
- **grouping column(s)**: optional — office, product, region, supplier, etc.

## Candlestick Charts (OHLC)

Candlestick charts show price movement over time with four values per period: open, high, low, close. They're the standard in financial and trading contexts because they pack a lot of information into a compact visual. Green candles mean the price went up (close > open), red means it went down.

```python
import plotly.graph_objects as go
import pandas as pd

def create_candlestick(df, date_col, open_col, high_col, low_col, close_col,
                        title="Price Movement (OHLC)",
                        ma_periods=None):
    """
    Create an interactive candlestick chart.

    Args:
        df: DataFrame with OHLC data
        date_col: column name for dates
        open_col, high_col, low_col, close_col: column names for OHLC values
        title: chart title
        ma_periods: list of moving average periods to overlay, e.g. [7, 30]
    """
    fig = go.Figure()

    # Candlestick trace
    fig.add_trace(go.Candlestick(
        x=df[date_col],
        open=df[open_col],
        high=df[high_col],
        low=df[low_col],
        close=df[close_col],
        name='Price',
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350',
    ))

    # Optional moving averages overlay
    if ma_periods:
        colors = ['#FF9800', '#2196F3', '#9C27B0']
        for i, period in enumerate(ma_periods):
            ma = df[close_col].rolling(window=period, min_periods=1).mean()
            fig.add_trace(go.Scatter(
                x=df[date_col], y=ma,
                mode='lines',
                name=f'MA-{period}',
                line=dict(color=colors[i % len(colors)], width=1.5),
            ))

    fig.update_layout(
        title=title,
        yaxis_title='Price',
        xaxis_title='Date',
        template='plotly_white',
        xaxis_rangeslider_visible=True,  # range slider for zoom
        height=500,
        hovermode='x unified',
    )

    return fig


# If data only has a single price per period (no OHLC), aggregate to create OHLC:
def aggregate_to_ohlc(df, date_col, price_col, period='W'):
    """
    Convert a single price column into OHLC by resampling.
    period: 'D' (daily), 'W' (weekly), 'M' (monthly)
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)

    ohlc = df[price_col].resample(period).agg(
        open='first', high='max', low='min', close='last'
    ).dropna().reset_index()

    return ohlc
```

### When to aggregate to OHLC
If the data has one price per row (common in sales order data), aggregate by week or month before creating the candlestick. Daily data with many transactions works well as weekly OHLC. Monthly summaries work well as monthly OHLC.

## Trend with Confidence Bands

This chart shows the actual price line, a smoothed trend, and a shaded confidence band that communicates uncertainty. It's the go-to chart for answering "is the price going up or down, and how confident are we?"

```python
import plotly.graph_objects as go
import numpy as np
import pandas as pd

def create_trend_with_bands(df, date_col, price_col,
                             window=14, confidence=1.96,
                             title="Price Trend with Confidence Band",
                             forecast_periods=0):
    """
    Create a trend line with confidence bands.

    Args:
        df: DataFrame with price data
        date_col: date column
        price_col: price column
        window: rolling window for trend smoothing
        confidence: z-score for band width (1.96 = 95%, 1.0 = 68%)
        title: chart title
        forecast_periods: number of periods to forecast ahead (0 = no forecast)
    """
    df = df.copy().sort_values(date_col)

    # Compute trend (moving average)
    df['trend'] = df[price_col].rolling(window=window, min_periods=1).mean()
    df['std'] = df[price_col].rolling(window=window, min_periods=1).std().fillna(0)
    df['upper'] = df['trend'] + confidence * df['std']
    df['lower'] = df['trend'] - confidence * df['std']

    fig = go.Figure()

    # Confidence band (shaded area)
    fig.add_trace(go.Scatter(
        x=pd.concat([df[date_col], df[date_col][::-1]]),
        y=pd.concat([df['upper'], df['lower'][::-1]]),
        fill='toself',
        fillcolor='rgba(76, 114, 176, 0.15)',
        line=dict(color='rgba(255,255,255,0)'),
        name=f'{int(confidence*100/1.96*50)}% Confidence Band',
        showlegend=True,
    ))

    # Actual price
    fig.add_trace(go.Scatter(
        x=df[date_col], y=df[price_col],
        mode='lines',
        name='Actual Price',
        line=dict(color='#6c757d', width=1),
        opacity=0.6,
    ))

    # Trend line
    fig.add_trace(go.Scatter(
        x=df[date_col], y=df['trend'],
        mode='lines',
        name=f'Trend (MA-{window})',
        line=dict(color='#4C72B0', width=2.5),
    ))

    # Optional: simple linear forecast
    if forecast_periods > 0:
        last_date = pd.to_datetime(df[date_col].iloc[-1])
        freq = pd.infer_freq(pd.to_datetime(df[date_col]))
        if freq is None:
            freq = 'D'
        future_dates = pd.date_range(start=last_date, periods=forecast_periods + 1, freq=freq)[1:]

        # Linear extrapolation from trend
        recent = df['trend'].dropna().values[-window:]
        slope = np.polyfit(range(len(recent)), recent, 1)[0]
        forecast = [df['trend'].iloc[-1] + slope * i for i in range(1, forecast_periods + 1)]

        # Expanding confidence for forecast
        last_std = df['std'].iloc[-1]
        forecast_upper = [f + confidence * last_std * np.sqrt(i) for i, f in enumerate(forecast, 1)]
        forecast_lower = [f - confidence * last_std * np.sqrt(i) for i, f in enumerate(forecast, 1)]

        # Forecast band
        fig.add_trace(go.Scatter(
            x=pd.concat([pd.Series(future_dates), pd.Series(future_dates[::-1])]),
            y=forecast_upper + forecast_lower[::-1],
            fill='toself',
            fillcolor='rgba(255, 152, 0, 0.15)',
            line=dict(color='rgba(255,255,255,0)'),
            name='Forecast Range',
        ))

        # Forecast line
        fig.add_trace(go.Scatter(
            x=future_dates, y=forecast,
            mode='lines',
            name='Forecast',
            line=dict(color='#FF9800', width=2, dash='dash'),
        ))

    fig.update_layout(
        title=title,
        yaxis_title='Price',
        xaxis_title='Date',
        template='plotly_white',
        height=450,
        hovermode='x unified',
    )

    return fig
```

## Multi-Entity Price Comparison

For comparing prices across offices, products, regions, or suppliers on the same timeline. This is critical for answering "which office has the best pricing?" or "are all regions moving in the same direction?"

```python
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

def create_price_comparison(df, date_col, price_col, group_col,
                             normalize=False,
                             title="Price Comparison by Entity"):
    """
    Multi-line chart comparing price across groups.

    Args:
        df: DataFrame
        date_col: date column
        price_col: price column
        group_col: grouping column (office, product, region, etc.)
        normalize: if True, index all series to 100 at start date (useful when
                   absolute price levels differ a lot between groups)
        title: chart title
    """
    df = df.copy().sort_values(date_col)

    if normalize:
        # Index to 100 at first observation per group
        def index_to_100(group):
            group = group.copy()
            first_val = group[price_col].iloc[0]
            if first_val != 0:
                group[price_col] = (group[price_col] / first_val) * 100
            return group
        df = df.groupby(group_col, group_keys=False).apply(index_to_100)
        title += " (Indexed to 100)"

    fig = px.line(
        df, x=date_col, y=price_col, color=group_col,
        title=title,
        labels={price_col: 'Price' if not normalize else 'Index (base=100)'},
        template='plotly_white',
    )

    fig.update_layout(
        height=450,
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )

    fig.update_traces(line=dict(width=2))

    return fig


def create_price_sparklines(df, date_col, price_col, group_col,
                             title="Price Overview by Entity"):
    """
    Small multiples (sparkline grid) — one mini-chart per entity.
    Great when there are many groups (>6) and a single chart gets cluttered.
    """
    fig = px.line(
        df, x=date_col, y=price_col,
        facet_col=group_col, facet_col_wrap=3,
        title=title,
        template='plotly_white',
    )

    fig.update_layout(height=250 * ((df[group_col].nunique() + 2) // 3))
    fig.update_yaxes(matches=None, showticklabels=True)
    fig.update_traces(line=dict(width=1.5))

    return fig
```

## Waterfall Decomposition

Waterfall charts break down what caused a price to change from one period to another. For example: "The average price went from $120 to $135 — here's why: +$8 from raw material costs, +$5 from shipping, +$4 from margin increase, -$2 from volume discount."

```python
import plotly.graph_objects as go

def create_price_waterfall(categories, values,
                            title="Price Change Decomposition",
                            currency_symbol="$"):
    """
    Waterfall chart showing what drives a price change.

    Args:
        categories: list of factor names, e.g.
                    ['Starting Price', 'Raw Materials', 'Shipping', 'Margin', 'Discount', 'Final Price']
        values: list of values — first and last are absolute totals, middle are relative changes
                e.g. [120, 8, 5, 4, -2, 135]
        title: chart title
        currency_symbol: prefix for values
    """
    # Determine measure type: first and last are 'absolute', rest are 'relative'
    measures = ['absolute'] + ['relative'] * (len(categories) - 2) + ['absolute']

    # Color: positive changes green, negative red, totals blue
    colors = []
    for i, (m, v) in enumerate(zip(measures, values)):
        if m == 'absolute':
            colors.append('#4C72B0')
        elif v >= 0:
            colors.append('#26a69a')
        else:
            colors.append('#ef5350')

    fig = go.Figure(go.Waterfall(
        name='Price',
        orientation='v',
        measure=measures,
        x=categories,
        textposition='outside',
        text=[f'{currency_symbol}{v:+,.0f}' if m == 'relative'
              else f'{currency_symbol}{v:,.0f}'
              for m, v in zip(measures, values)],
        y=values,
        connector=dict(line=dict(color='#9e9e9e', width=1, dash='dot')),
        increasing=dict(marker=dict(color='#26a69a')),
        decreasing=dict(marker=dict(color='#ef5350')),
        totals=dict(marker=dict(color='#4C72B0')),
    ))

    fig.update_layout(
        title=title,
        yaxis_title=f'Price ({currency_symbol})',
        template='plotly_white',
        height=450,
        showlegend=False,
    )

    return fig
```

### How to prepare waterfall data from raw orders
The waterfall needs pre-computed factors. Typically you:
1. Calculate the average price in period A and period B
2. Decompose the difference by factors (product mix, cost changes, volume effects, etc.)
3. Pass the decomposed values to the chart

This decomposition is business-logic specific — Claude should work with the user to identify which factors matter for their sales office context.

## Price Heatmap

Shows price levels across two dimensions (e.g., product x month, office x week). Hot spots jump out visually — much faster than scanning a table.

```python
import plotly.express as px
import pandas as pd

def create_price_heatmap(df, date_col, group_col, price_col,
                          agg_func='mean', date_period='M',
                          title="Price Heatmap"):
    """
    Heatmap of prices across a time dimension and a category dimension.

    Args:
        df: DataFrame
        date_col: date column (will be resampled to date_period)
        group_col: category column (office, product, etc.)
        price_col: price column
        agg_func: how to aggregate prices ('mean', 'median', 'max', 'min')
        date_period: 'W' for weekly, 'M' for monthly, 'Q' for quarterly
        title: chart title
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df['period'] = df[date_col].dt.to_period(date_period).astype(str)

    pivot = df.pivot_table(
        index=group_col, columns='period',
        values=price_col, aggfunc=agg_func
    )

    fig = px.imshow(
        pivot,
        title=title,
        labels=dict(x='Period', y=group_col, color=f'{agg_func.title()} Price'),
        color_continuous_scale='RdYlGn_r',  # red = expensive, green = cheap
        aspect='auto',
    )

    fig.update_layout(
        template='plotly_white',
        height=max(300, 40 * len(pivot)),
    )

    return fig
```

## Box Plot Over Time

Shows price distribution (median, quartiles, outliers) for each time period. Useful for seeing not just average price movement but also how spread-out the prices are — are all orders priced similarly, or is there high variance?

```python
import plotly.express as px
import pandas as pd

def create_price_boxplot_timeline(df, date_col, price_col,
                                   period='M',
                                   title="Price Distribution Over Time"):
    """
    Box plots showing price distribution per time period.
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df['period'] = df[date_col].dt.to_period(period).astype(str)

    fig = px.box(
        df, x='period', y=price_col,
        title=title,
        template='plotly_white',
    )

    fig.update_layout(
        xaxis_title='Period',
        yaxis_title='Price',
        height=400,
    )

    return fig
```

## Saving and Exporting

All plotly figures support:
```python
# Interactive HTML (best for exploration)
fig.write_html('price_chart.html')

# Static image (best for reports/presentations)
fig.write_image('price_chart.png', scale=2)  # needs kaleido: pip install kaleido

# Show inline
fig.show()
```

For dashboards that combine multiple price charts, see the `interactive-dashboard-builder` skill — it handles layout, filters, and KPI cards. This skill focuses on individual chart components.

## Dependencies

```bash
pip install plotly pandas numpy kaleido --break-system-packages
```
