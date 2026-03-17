---
name: price-prediction
description: "Predict whether prices will go up or down using time-series forecasting models (ARIMA, Exponential Smoothing, Prophet). Produces forecasts with confidence intervals and a clear signal: 'price expected to rise/fall' with confidence level. Use this skill whenever the user asks to predict, forecast, or project future prices, or asks 'will the price go up or down?', 'what will the price be next month?', or needs price forecasting from order/sales data. This skill ADDS to the existing statistical-analysis skill — it provides advanced forecasting beyond moving averages and linear trends. Triggers: price prediction, price forecast, will price go up, will price rise, will price fall, future price, price projection, expected price, price outlook, trend prediction."
---

# Price Prediction Skill

Advanced time-series forecasting for price data from order/sales systems. This skill builds on top of the `statistical-analysis` skill by adding models that capture seasonality, trends, and autocorrelation patterns that simple moving averages miss.

The goal is always the same: given historical price data, produce a forecast with a clear directional signal ("price expected to rise/fall") and a confidence level, along with a visualization showing the forecast range.

## Model Selection Guide

Don't overthink model selection. The right model depends on how much data you have and whether there's seasonality:

| Data Available | Seasonality? | Recommended Model | Fallback |
|---|---|---|---|
| < 30 data points | Any | Exponential Smoothing (ETS) | Moving Average (from statistical-analysis skill) |
| 30-100 data points | No | ARIMA | ETS |
| 30-100 data points | Yes | SARIMAX | ETS with seasonal |
| 100+ data points | Yes | Prophet | SARIMAX |
| 100+ data points | No | ARIMA | ETS |

In practice, for most sales office price data (weekly/monthly aggregates), **ETS or ARIMA will be your workhorse**. Prophet is best when you have daily data with holidays and multiple seasonalities.

## Standard Workflow

Every price prediction follows this flow:

1. **Prepare data**: ensure sorted by date, handle missing periods, aggregate if needed
2. **Explore**: plot the series, check for trend and seasonality
3. **Fit model**: run the appropriate model
4. **Forecast**: generate predictions with confidence intervals
5. **Produce signal**: translate the forecast into a clear up/down signal with confidence
6. **Visualize**: plot actual + forecast + confidence band

## Data Preparation

Price data from sales systems often needs preparation before forecasting. The key issues are: irregular time intervals, missing periods, and multiple prices per period that need aggregation.

```python
import pandas as pd
import numpy as np

def prepare_price_series(df, date_col, price_col, freq='W',
                          agg_func='mean', fill_method='ffill'):
    """
    Prepare a clean, regular time series from raw order data.

    Args:
        df: DataFrame with price data
        date_col: date column name
        price_col: price column name
        freq: target frequency ('D', 'W', 'M', 'Q')
        agg_func: how to aggregate multiple prices per period
        fill_method: how to handle missing periods ('ffill', 'interpolate', None)

    Returns:
        Series with DatetimeIndex at regular frequency
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()

    # Aggregate to target frequency
    series = df[price_col].resample(freq).agg(agg_func)

    # Handle missing periods
    if fill_method == 'ffill':
        series = series.ffill()
    elif fill_method == 'interpolate':
        series = series.interpolate(method='linear')

    series = series.dropna()
    return series
```

## Model 1: Exponential Smoothing (ETS)

The simplest "real" forecasting model. Works well even with limited data. Captures trend and optional seasonality through exponentially weighted averages — recent data matters more than old data.

```python
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import pandas as pd
import numpy as np

def forecast_ets(series, periods=12, seasonal_periods=None, confidence=0.95):
    """
    Exponential Smoothing forecast.

    Args:
        series: pd.Series with DatetimeIndex (from prepare_price_series)
        periods: number of periods to forecast
        seasonal_periods: number of periods in one seasonal cycle
                         (e.g., 12 for monthly data with annual seasonality,
                          52 for weekly data with annual seasonality)
                         None = no seasonality
        confidence: confidence level for prediction interval

    Returns:
        dict with forecast, lower_bound, upper_bound, model_info
    """
    # Choose model specification
    trend = 'add'  # additive trend
    seasonal = 'add' if seasonal_periods else None

    model = ExponentialSmoothing(
        series,
        trend=trend,
        seasonal=seasonal,
        seasonal_periods=seasonal_periods,
        initialization_method='estimated',
    ).fit(optimized=True)

    # Forecast
    forecast = model.forecast(periods)

    # Prediction intervals (ETS doesn't give native PI, so we estimate from residuals)
    residuals = model.resid.dropna()
    residual_std = residuals.std()
    from scipy.stats import norm
    z = norm.ppf((1 + confidence) / 2)

    # Expanding uncertainty for future periods
    lower = pd.Series(
        [forecast.iloc[i] - z * residual_std * np.sqrt(i + 1) for i in range(periods)],
        index=forecast.index
    )
    upper = pd.Series(
        [forecast.iloc[i] + z * residual_std * np.sqrt(i + 1) for i in range(periods)],
        index=forecast.index
    )

    return {
        'forecast': forecast,
        'lower': lower,
        'upper': upper,
        'model_type': 'ETS',
        'aic': model.aic,
        'residual_std': residual_std,
    }
```

## Model 2: ARIMA / SARIMAX

ARIMA captures autocorrelation patterns (today's price is related to yesterday's price) and can handle trends. SARIMAX adds seasonal patterns. The `auto_arima` from pmdarima automatically finds the best parameters — this saves a lot of manual tuning.

```python
def forecast_arima(series, periods=12, seasonal_periods=None, confidence=0.95):
    """
    ARIMA/SARIMAX forecast with automatic parameter selection.

    Args:
        series: pd.Series with DatetimeIndex
        periods: number of periods to forecast
        seasonal_periods: seasonal cycle length (None = no seasonality)
        confidence: confidence level

    Returns:
        dict with forecast, lower_bound, upper_bound, model_info
    """
    import pmdarima as pm

    model = pm.auto_arima(
        series,
        seasonal=seasonal_periods is not None,
        m=seasonal_periods or 1,
        stepwise=True,
        suppress_warnings=True,
        error_action='ignore',
        max_p=3, max_q=3,
        max_P=2, max_Q=2,
    )

    # Forecast with confidence intervals
    fc, conf_int = model.predict(
        n_periods=periods,
        return_conf_int=True,
        alpha=1 - confidence,
    )

    # Create proper index
    last_date = series.index[-1]
    freq = pd.infer_freq(series.index) or 'D'
    future_index = pd.date_range(start=last_date, periods=periods + 1, freq=freq)[1:]

    forecast = pd.Series(fc, index=future_index)
    lower = pd.Series(conf_int[:, 0], index=future_index)
    upper = pd.Series(conf_int[:, 1], index=future_index)

    return {
        'forecast': forecast,
        'lower': lower,
        'upper': upper,
        'model_type': f'ARIMA{model.order}',
        'seasonal_order': model.seasonal_order if seasonal_periods else None,
        'aic': model.aic(),
    }
```

### Installing pmdarima
```bash
pip install pmdarima --break-system-packages
```

## Model 3: Prophet

Facebook's Prophet handles daily data with holidays, multiple seasonalities (weekly + annual), and trend changepoints. Best for when you have a lot of data (100+ points) and complex patterns.

```python
def forecast_prophet(series, periods=30, confidence=0.95):
    """
    Prophet forecast — best for daily data with complex seasonality.

    Args:
        series: pd.Series with DatetimeIndex
        periods: number of periods to forecast
        confidence: confidence level

    Returns:
        dict with forecast, lower_bound, upper_bound, model_info
    """
    from prophet import Prophet

    # Prophet expects a DataFrame with 'ds' (date) and 'y' (value) columns
    prophet_df = pd.DataFrame({
        'ds': series.index,
        'y': series.values,
    })

    model = Prophet(
        interval_width=confidence,
        daily_seasonality=False,  # set True if sub-daily data
        yearly_seasonality='auto',
        weekly_seasonality='auto',
        changepoint_prior_scale=0.05,  # default; increase for more flexible trend
    )
    model.fit(prophet_df)

    future = model.make_future_dataframe(periods=periods, freq=pd.infer_freq(series.index) or 'D')
    prediction = model.predict(future)

    # Extract only the forecast part (future periods)
    forecast_part = prediction.iloc[-periods:]

    forecast = pd.Series(forecast_part['yhat'].values,
                         index=pd.to_datetime(forecast_part['ds'].values))
    lower = pd.Series(forecast_part['yhat_lower'].values, index=forecast.index)
    upper = pd.Series(forecast_part['yhat_upper'].values, index=forecast.index)

    return {
        'forecast': forecast,
        'lower': lower,
        'upper': upper,
        'model_type': 'Prophet',
        'components': model.plot_components,  # callable for decomposition plot
    }
```

### Installing Prophet
```bash
pip install prophet --break-system-packages
```
Prophet can be slow to install. If it fails or isn't available, fall back to ARIMA or ETS.

## Generating the Price Signal

This is the key deliverable for the user: a clear, actionable signal based on the forecast. Don't just show a chart — tell them what it means.

```python
def generate_price_signal(series, forecast_result, lookback_periods=4):
    """
    Generate a directional signal from the forecast.

    Args:
        series: historical price series
        forecast_result: dict from any forecast function above
        lookback_periods: how many recent periods to compare against

    Returns:
        dict with signal details
    """
    forecast = forecast_result['forecast']
    lower = forecast_result['lower']
    upper = forecast_result['upper']

    current_price = series.iloc[-1]
    recent_avg = series.iloc[-lookback_periods:].mean()
    forecast_end = forecast.iloc[-1]
    forecast_avg = forecast.mean()

    # Direction
    pct_change = (forecast_avg - current_price) / current_price * 100
    direction = 'UP' if pct_change > 0 else 'DOWN'

    # Confidence: how much of the forecast band is on one side of current price?
    # If both lower and upper bounds are above current price, we're very confident it's going up
    forecast_above_current = (lower > current_price).mean()
    forecast_below_current = (upper < current_price).mean()

    if direction == 'UP':
        confidence_score = forecast_above_current
    else:
        confidence_score = forecast_below_current

    # Classify confidence
    if confidence_score > 0.8:
        confidence_label = 'HIGH'
    elif confidence_score > 0.5:
        confidence_label = 'MODERATE'
    else:
        confidence_label = 'LOW'

    # Range at forecast end
    forecast_range = (lower.iloc[-1], upper.iloc[-1])

    signal = {
        'direction': direction,
        'confidence': confidence_label,
        'confidence_score': round(confidence_score, 2),
        'current_price': round(current_price, 2),
        'forecast_avg': round(forecast_avg, 2),
        'expected_change_pct': round(pct_change, 1),
        'forecast_range': (round(forecast_range[0], 2), round(forecast_range[1], 2)),
        'model': forecast_result['model_type'],
        'summary': f"Price expected to go {direction} by ~{abs(pct_change):.1f}% "
                   f"(confidence: {confidence_label}). "
                   f"Current: {current_price:.2f}, "
                   f"Forecast range: {forecast_range[0]:.2f} - {forecast_range[1]:.2f}"
    }

    return signal
```

### How to present the signal

When presenting results to the user, always include:

1. **The signal summary** (one sentence): "Price is expected to **rise by ~5.2%** over the next 3 months (confidence: HIGH)"
2. **The forecast chart** (from price-visualization skill — use `create_trend_with_bands`)
3. **Key numbers**: current price, forecast average, forecast range
4. **Caveats**: what could invalidate the forecast (e.g., "this assumes no major supply chain disruptions or policy changes")

## Visualization of Forecasts

Use the `create_trend_with_bands` function from the `price-visualization` skill, or build a custom plotly chart:

```python
import plotly.graph_objects as go

def plot_forecast(series, forecast_result, title="Price Forecast"):
    """
    Plot historical data + forecast with confidence bands.
    """
    forecast = forecast_result['forecast']
    lower = forecast_result['lower']
    upper = forecast_result['upper']

    fig = go.Figure()

    # Historical
    fig.add_trace(go.Scatter(
        x=series.index, y=series.values,
        mode='lines', name='Historical',
        line=dict(color='#4C72B0', width=2),
    ))

    # Forecast confidence band
    fig.add_trace(go.Scatter(
        x=list(forecast.index) + list(forecast.index[::-1]),
        y=list(upper) + list(lower[::-1]),
        fill='toself',
        fillcolor='rgba(255, 152, 0, 0.15)',
        line=dict(color='rgba(255,255,255,0)'),
        name='Confidence Band',
    ))

    # Forecast line
    fig.add_trace(go.Scatter(
        x=forecast.index, y=forecast.values,
        mode='lines', name='Forecast',
        line=dict(color='#FF9800', width=2, dash='dash'),
    ))

    # Vertical line at forecast start
    fig.add_vline(
        x=series.index[-1],
        line_dash='dot', line_color='gray',
        annotation_text='Forecast Start',
    )

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

## Running Multiple Models for Comparison

When data allows, run 2-3 models and compare. This gives the user more confidence in the result if models agree, or flags uncertainty if they disagree.

```python
def compare_models(series, periods=12, seasonal_periods=None):
    """
    Run multiple models and compare forecasts.
    Returns a summary with all forecasts and a consensus signal.
    """
    results = {}

    # Always try ETS (works with any data size)
    try:
        results['ETS'] = forecast_ets(series, periods, seasonal_periods)
    except Exception as e:
        results['ETS'] = {'error': str(e)}

    # Try ARIMA if enough data
    if len(series) >= 30:
        try:
            results['ARIMA'] = forecast_arima(series, periods, seasonal_periods)
        except Exception as e:
            results['ARIMA'] = {'error': str(e)}

    # Try Prophet if enough data and it's installed
    if len(series) >= 100:
        try:
            results['Prophet'] = forecast_prophet(series, periods)
        except ImportError:
            results['Prophet'] = {'error': 'Prophet not installed'}
        except Exception as e:
            results['Prophet'] = {'error': str(e)}

    # Generate signals for successful models
    signals = {}
    for name, result in results.items():
        if 'error' not in result:
            signals[name] = generate_price_signal(series, result)

    # Consensus: majority direction wins
    if signals:
        directions = [s['direction'] for s in signals.values()]
        consensus_direction = max(set(directions), key=directions.count)
        agreement = directions.count(consensus_direction) / len(directions)

        consensus = {
            'direction': consensus_direction,
            'model_agreement': f"{directions.count(consensus_direction)}/{len(directions)} models agree",
            'agreement_pct': round(agreement * 100),
            'individual_signals': signals,
        }
    else:
        consensus = {'error': 'No models succeeded'}

    return {
        'model_results': results,
        'consensus': consensus,
    }
```

## Dependencies

Core (always needed):
```bash
pip install statsmodels pandas numpy scipy plotly --break-system-packages
```

For ARIMA with auto-tuning:
```bash
pip install pmdarima --break-system-packages
```

For Prophet (optional, for complex daily seasonality):
```bash
pip install prophet --break-system-packages
```

If a package fails to install, fall back to the models that don't need it. ETS from statsmodels is always available and is a solid default.
