"""Claude Analyst — Interactive AI-powered data analysis and market intelligence.

Provides Claude as an intelligent analyst tool for:
  1. **Ask** — Natural language Q&A about portfolio data (chat/query)
  2. **Brief** — Auto-generated market briefs / executive summaries
  3. **Metadata** — Smart enrichment (tags, insights, action items per room)
  4. **Explain** — Deep-dive explanation of any prediction or anomaly

Uses the full analysis context (2800+ rooms, 12 data sources, scan history,
forward curves, events, benchmarks) to answer questions with precision.

Architecture:
  - System prompt encodes full domain knowledge
  - Analysis data is serialized into a compact context window
  - Claude Haiku for speed; Sonnet for deep analysis if requested
  - Response caching to minimize API costs
  - Graceful fallback when API key not set
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_ANALYST_MODEL = os.getenv("CLAUDE_AI_MODEL", "claude-haiku-4-20250514")
CLAUDE_DEEP_MODEL = os.getenv("CLAUDE_DEEP_MODEL", "claude-sonnet-4-20250514")
ANALYST_MAX_TOKENS = int(os.getenv("ANALYST_MAX_TOKENS", "2048"))
ANALYST_CACHE_TTL = int(os.getenv("ANALYST_CACHE_TTL", "600"))  # 10 min

# Cache via unified CacheManager (region "analyst")
from src.utils.cache_manager import cache as _cm


def _cache_get(key: str) -> Any | None:
    return _cm.get("analyst", key)


def _cache_set(key: str, val: Any) -> None:
    _cm.set("analyst", key, val)


# ---------------------------------------------------------------------------
# Domain Knowledge — System Prompts
# ---------------------------------------------------------------------------

ANALYST_SYSTEM_PROMPT = """You are an expert hotel revenue management analyst working for SalesOffice — a hotel room options trading system that monitors Miami hotel pricing.

## Your Role
You are the AI analyst embedded in the trading dashboard. Users ask you questions about their hotel room portfolio, market conditions, predictions, and trading signals. You answer with precision, using the actual data provided.

## System Overview
- SalesOffice tracks ~2,800+ hotel room options across 10 Miami hotels
- Each room has a CALL (price expected to rise) or PUT (price expected to drop) or NEUTRAL signal
- Predictions use a weighted ensemble: Forward Curve (50%), Historical Patterns (30%), ML Forecast (20%)
- Confidence is adjusted via Bayesian learning from observed outcomes
- Prices are scanned every 3 hours from the medici-db trading database
- Forward curves project daily prices from now until check-in date

## Data Sources (12 total)
1. **Forward Curve** — Proprietary decay/growth curve fitted from historical scan data
2. **Historical Patterns** — Year-over-year same-month/category patterns from past bookings
3. **ML Forecast** — Machine learning model (when available)
4. **Scan History** — Actual observed price series (3-hourly snapshots from medici-db)
5. **Events** — Ticketmaster + SeatGeek events near Miami (concerts, sports, conferences)
6. **Flight Demand** — Incoming flight prices/volume to Miami as demand proxy
7. **Market Benchmarks** — Same-star competitor hotel pricing comparison
8. **Weather** — Seasonal weather impact estimation
9. **Seasonality** — Monthly/weekly seasonal adjustment factors
10. **Momentum** — Short-term price velocity and acceleration
11. **Regime Detection** — Market regime classification (Normal/Trending/Volatile/Stale)
12. **Booking Benchmarks** — CBS/booking.com benchmark comparisons

## Key Metrics You Understand
- **Option Signal**: CALL (buy opportunity, price will rise), PUT (sell/avoid, price will drop), NEUTRAL
- **Option Level (L1-L10)**: Conviction strength. L1-L3=weak, L4-L6=moderate, L7-L8=strong, L9-L10=very strong
- **Expected Change %**: Predicted price move from now to check-in
- **Quality Score**: 0-1 rating of prediction data quality (HIGH≥0.75, MEDIUM≥0.5, LOW<0.5)
- **Scan History**: Actual price movements observed since tracking started
- **Forward Curve**: Daily predicted price path with uncertainty bands
- **Market Benchmark**: How this hotel prices vs same-star competitors
- **Momentum Signal**: ACCELERATING_UP, ACCELERATING_DOWN, NORMAL, INSUFFICIENT_DATA
- **Regime**: NORMAL, TRENDING_UP, TRENDING_DOWN, VOLATILE, STALE

## Board Types
- RO = Room Only, BB = Bed & Breakfast, HB = Half Board, FB = Full Board, AI = All Inclusive

## Response Style
- Be direct and analytical — like a trading floor analyst
- Use specific numbers from the data (prices, percentages, counts)
- When asked about a specific hotel/room, reference actual data values
- Highlight risks and opportunities
- Use Hebrew if the user writes in Hebrew (you are bilingual EN/HE)
- Keep responses focused and actionable
- Format with markdown for readability
- Currency is USD ($) for Miami hotels"""

BRIEF_SYSTEM_PROMPT = """You are a hotel revenue management AI generating a concise executive market brief.

Write a 3-5 paragraph market summary suitable for a trading team morning briefing.

Structure:
1. **Market Pulse** — Overall tone (bullish/bearish/mixed), key numbers
2. **Top Opportunities** — Best CALL signals, strongest conviction
3. **Risk Alerts** — PUT signals, anomalies, high-risk positions
4. **Events & External Factors** — Upcoming events, demand signals
5. **Action Items** — Specific recommendations

Style: Professional, data-driven, concise. Use actual numbers from the data.
If writing in Hebrew, use business Hebrew with technical terms in English.
Currency: USD ($)."""

METADATA_SYSTEM_PROMPT = """You are an AI enrichment engine. For each hotel room, generate structured metadata:

Return a JSON object with these fields:
{
  "tag": "one of: 'hot_deal' | 'watch' | 'risky' | 'stable' | 'momentum_play' | 'contrarian' | 'premium_opportunity'",
  "one_liner": "1-sentence insight about this specific room (20 words max)",
  "action": "one of: 'BUY_NOW' | 'WAIT' | 'AVOID' | 'MONITOR' | 'REVIEW'",
  "confidence_emoji": "one of: 🟢 | 🟡 | 🔴 based on prediction confidence",
  "key_factor": "the single most important factor driving this prediction"
}

Be precise. Use actual numbers. Tag based on the data, not guesses."""

EXPLAIN_SYSTEM_PROMPT = """You are explaining a hotel price prediction in detail.

The user wants to understand WHY a specific room has its current prediction.
Walk through each contributing factor:

1. Forward Curve signal — what does the decay/growth curve predict?
2. Historical Pattern — what happened same-month in prior years?
3. Scan History — what's actually been happening to the price?
4. Events — any upcoming events that affect demand?
5. Market Position — how does this hotel compare to competitors?
6. Momentum & Regime — is the price accelerating? In what regime?

End with a synthesis: overall confidence and key risk factors.
Be specific with numbers. Use the data provided."""


# ---------------------------------------------------------------------------
# Data Serialization — Compact Context Building
# ---------------------------------------------------------------------------

def _build_portfolio_summary(analysis: dict) -> str:
    """Build a compact text summary of the full portfolio for Claude's context."""
    stats = analysis.get("statistics", {})
    predictions = analysis.get("predictions", {})
    events = analysis.get("events", {})
    demand = analysis.get("flight_demand", {})
    hotels = analysis.get("hotels", [])
    changes = analysis.get("price_changes", {})
    booking = analysis.get("booking_window", {})

    # Aggregate signals
    calls, puts, neutrals = 0, 0, 0
    total_change = 0
    high_quality = 0
    regimes: dict[str, int] = {}
    momentums: dict[str, int] = {}

    for pid, pred in predictions.items():
        chg = float(pred.get("expected_change_pct", 0) or 0)
        total_change += chg
        if chg > 2:
            calls += 1
        elif chg < -2:
            puts += 1
        else:
            neutrals += 1

        q = pred.get("confidence_quality", "low")
        if q == "high":
            high_quality += 1

        regime = pred.get("regime", {})
        if isinstance(regime, dict):
            r = regime.get("regime", "NORMAL")
        else:
            r = str(regime)
        regimes[r] = regimes.get(r, 0) + 1

        mom = pred.get("momentum", {})
        if isinstance(mom, dict):
            m = mom.get("signal", "NORMAL")
        else:
            m = str(mom)
        momentums[m] = momentums.get(m, 0) + 1

    n = len(predictions)
    avg_change = total_change / n if n else 0

    lines = [
        f"## Portfolio Snapshot ({analysis.get('run_ts', 'now')})",
        f"- Total rooms: {n} across {stats.get('total_hotels', 0)} hotels",
        f"- Signals: {calls} CALL / {puts} PUT / {neutrals} NEUTRAL",
        f"- Avg predicted change: {avg_change:+.1f}%",
        f"- Price range: ${stats.get('price_min', 0):.0f} – ${stats.get('price_max', 0):.0f} "
        f"(mean ${stats.get('price_mean', 0):.0f}, median ${stats.get('price_median', 0):.0f})",
        f"- Total inventory value: ${stats.get('total_inventory_value', 0):,.0f}",
        f"- High confidence predictions: {high_quality}/{n}",
        f"- Snapshots collected: {analysis.get('total_snapshots', 0)}",
        "",
        "## Regimes: " + ", ".join(f"{k}={v}" for k, v in sorted(regimes.items(), key=lambda x: -x[1])),
        "## Momentum: " + ", ".join(f"{k}={v}" for k, v in sorted(momentums.items(), key=lambda x: -x[1])),
    ]

    # Hotels summary
    if hotels:
        lines.append("\n## Hotels:")
        for h in hotels:
            lines.append(
                f"  - {h.get('hotel_name', '?')} (ID {h.get('hotel_id')}): "
                f"{h.get('total_rooms', 0)} rooms, "
                f"${h.get('price_min', 0):.0f}-${h.get('price_max', 0):.0f} "
                f"(avg ${h.get('price_mean', 0):.0f}), "
                f"categories: {', '.join(h.get('categories', []))}"
            )

    # Events
    next_events = events.get("next_events", [])
    if next_events:
        lines.append(f"\n## Upcoming Events ({events.get('upcoming_events', 0)} total):")
        for e in next_events[:8]:
            lines.append(
                f"  - {e.get('name', '?')}: {e.get('start_date', '?')} to {e.get('end_date', '?')} "
                f"(impact: {e.get('hotel_impact', '?')}, attendance: {e.get('expected_attendance', '?')})"
            )

    # Flight demand
    if demand:
        lines.append(
            f"\n## Flight Demand: {demand.get('indicator', 'N/A')} "
            f"(avg ${demand.get('avg_flight_price', 0):.0f}, {demand.get('total_flights', 0)} flights)"
        )

    # Price changes
    if changes and changes.get("total_changes"):
        lines.append(
            f"\n## Recent Price Changes: {changes.get('total_changes', 0)} total "
            f"({changes.get('price_increases', 0)} up, {changes.get('price_decreases', 0)} down)"
        )
        for c in (changes.get("changes") or [])[:5]:
            lines.append(
                f"  - {c.get('hotel_name', '?')} {c.get('date_from', '?')}: "
                f"${c.get('old_price', 0):.0f}→${c.get('new_price', 0):.0f} "
                f"({c.get('change_pct', 0):+.1f}%)"
            )

    # Booking window
    if booking and booking.get("windows"):
        lines.append("\n## Booking Windows:")
        for w in booking["windows"]:
            lines.append(
                f"  - {w.get('window', '?')}: {w.get('rooms', 0)} rooms, "
                f"avg ${w.get('avg_price', 0):.0f}"
            )

    # By category
    by_cat = stats.get("by_category", {})
    if by_cat:
        lines.append("\n## By Category:")
        for cat, info in sorted(by_cat.items()):
            if isinstance(info, dict):
                lines.append(f"  - {cat}: {info.get('count', 0)} rooms, avg ${info.get('avg_price', 0):.0f}")

    return "\n".join(lines)


def _build_room_detail(pred: dict, detail_id: int | str) -> str:
    """Build detailed text for a single room."""
    lines = [
        f"## Room Detail: {pred.get('hotel_name', '?')} — {pred.get('category', '?')} ({pred.get('board', '?')})",
        f"Detail ID: {detail_id}",
        f"Check-in: {pred.get('date_from', '?')} ({pred.get('days_to_checkin', '?')} days away)",
        f"Current Price: ${float(pred.get('current_price', 0) or 0):.2f}",
        f"Predicted Check-in Price: ${float(pred.get('predicted_checkin_price', 0) or 0):.2f}",
        f"Expected Change: {float(pred.get('expected_change_pct', 0) or 0):+.2f}%",
        f"Model: {pred.get('prediction_method', pred.get('model_type', '?'))}",
        f"Confidence: {pred.get('confidence_quality', '?')}",
    ]

    # Probability
    prob = pred.get("probability", {})
    if prob and isinstance(prob, dict):
        lines.append(f"Probability: up={prob.get('up', 0):.0%}, down={prob.get('down', 0):.0%}, stable={prob.get('stable', 0):.0%}")

    # Signals
    sigs = pred.get("signals", [])
    if sigs:
        lines.append("\nSignals:")
        for s in sigs:
            lines.append(
                f"  - {s.get('source', '?')}: ${s.get('predicted_price', 0):.2f} "
                f"(conf={s.get('confidence', 0):.2f}, weight={s.get('weight', 0):.3f}) "
                f"— {s.get('reasoning', '')}"
            )

    # Momentum
    mom = pred.get("momentum", {})
    if mom and isinstance(mom, dict):
        lines.append(
            f"\nMomentum: {mom.get('signal', '?')} (strength={mom.get('strength', 0):.2f}, "
            f"v3h={mom.get('velocity_3h', 0):.2f}%, v24h={mom.get('velocity_24h', 0):.2f}%, "
            f"v72h={mom.get('velocity_72h', 0):.2f}%)"
        )

    # Regime
    regime = pred.get("regime", {})
    if regime and isinstance(regime, dict):
        lines.append(
            f"Regime: {regime.get('regime', '?')} (z={regime.get('z_score', 0):.2f}, "
            f"div={regime.get('divergence_pct', 0):.1f}%, alert={regime.get('alert_level', 'none')})"
        )

    # Scan history
    scan = pred.get("scan_history", {})
    if scan and isinstance(scan, dict) and scan.get("scan_snapshots", 0) > 0:
        lines.append(
            f"\nScan History: {scan.get('scan_snapshots', 0)} scans, "
            f"trend={scan.get('scan_trend', '?')}, "
            f"change={scan.get('scan_price_change_pct', 0):+.1f}% "
            f"(${scan.get('first_scan_price', 0):.0f}→${scan.get('latest_scan_price', 0):.0f}), "
            f"drops={scan.get('scan_actual_drops', 0)}, rises={scan.get('scan_actual_rises', 0)}"
        )

    # Market benchmark
    bench = pred.get("market_benchmark", {})
    if bench and isinstance(bench, dict) and bench.get("competitor_hotels"):
        lines.append(
            f"\nMarket: vs {bench.get('competitor_hotels', 0)} competitors "
            f"(avg ${bench.get('market_avg_price', 0):.0f}, "
            f"range ${bench.get('market_min_price', 0):.0f}-${bench.get('market_max_price', 0):.0f}), "
            f"pressure={bench.get('pressure', 0):.2f}"
        )

    # YoY
    yoy = pred.get("yoy_comparison")
    if yoy and isinstance(yoy, dict):
        lines.append(
            f"\nYoY ({yoy.get('period', '?')}): prior avg ${yoy.get('prior_avg_price', 0):.0f}, "
            f"current ${yoy.get('current_price', 0):.0f}, "
            f"change {yoy.get('yoy_change_pct', 0):+.1f}%"
        )

    # AI enrichment
    ai_risk = pred.get("ai_risk", {})
    if ai_risk:
        lines.append(f"\nAI Risk: {ai_risk.get('risk_level', '?')} (score={ai_risk.get('risk_score', 0):.2f})")

    ai_anomaly = pred.get("ai_anomaly", {})
    if ai_anomaly and ai_anomaly.get("is_anomaly"):
        lines.append(f"AI Anomaly: {ai_anomaly.get('anomaly_type')} (severity={ai_anomaly.get('severity')})")

    # Explanation
    expl = pred.get("explanation", {})
    if expl and isinstance(expl, dict):
        lines.append(f"\nExplanation: {expl.get('summary', '')}")
        for f in expl.get("factors", []):
            lines.append(f"  - {f.get('factor', '?')}: {f.get('effect', '?')} — {f.get('detail', '')}")

    return "\n".join(lines)


def _build_top_movers(predictions: dict, n: int = 15) -> str:
    """Build top movers summary — biggest predicted changes."""
    items = []
    for pid, pred in predictions.items():
        chg = float(pred.get("expected_change_pct", 0) or 0)
        items.append((pid, pred, abs(chg), chg))

    items.sort(key=lambda x: x[2], reverse=True)
    lines = [f"\n## Top {n} Movers (by predicted change):"]
    for pid, pred, _, chg in items[:n]:
        signal = "CALL" if chg > 2 else "PUT" if chg < -2 else "NEUT"
        q = pred.get("confidence_quality", "?")[0].upper()
        lines.append(
            f"  {signal} {pid} {pred.get('hotel_name', '?')[:25]:25s} "
            f"{pred.get('category', '?')[:12]:12s} "
            f"${float(pred.get('current_price', 0) or 0):>7.0f} → "
            f"${float(pred.get('predicted_checkin_price', 0) or 0):>7.0f} "
            f"({chg:+6.1f}%) Q={q} "
            f"D={pred.get('days_to_checkin', '?')}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude API Interaction
# ---------------------------------------------------------------------------

def _call_claude(
    system_prompt: str,
    user_message: str,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.3,
) -> str | None:
    """Call Claude API and return text response."""
    if not ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=model or CLAUDE_ANALYST_MODEL,
            max_tokens=max_tokens or ANALYST_MAX_TOKENS,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text if response.content else None
    except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
        logger.warning("Claude analyst call failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Public API — Analyst Functions
# ---------------------------------------------------------------------------

@dataclass
class AnalystResponse:
    """Response from the Claude analyst."""
    answer: str
    source: str = "claude"  # "claude" | "fallback"
    model: str = ""
    cached: bool = False
    tokens_used: int = 0
    processing_time_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "source": self.source,
            "model": self.model,
            "cached": self.cached,
            "tokens_used": self.tokens_used,
            "processing_time_ms": self.processing_time_ms,
        }


def ask_analyst(
    question: str,
    analysis: dict,
    detail_id: int | str | None = None,
    deep: bool = False,
) -> AnalystResponse:
    """Ask Claude a question about the portfolio data.

    Args:
        question: Natural language question from the user
        analysis: The full analysis dict from _get_or_run_analysis()
        detail_id: Optional — focus on a specific room
        deep: Use Sonnet for deeper analysis (slower, more expensive)

    Returns:
        AnalystResponse with the answer
    """
    start_ms = time.time()

    # Check cache
    cache_key = hashlib.md5(f"{question}:{detail_id}:{deep}".encode()).hexdigest()
    cached = _cache_get(cache_key)
    if cached:
        cached["cached"] = True
        return AnalystResponse(**cached)

    predictions = analysis.get("predictions", {})

    # Build context
    context_parts = [_build_portfolio_summary(analysis)]

    if detail_id is not None:
        # Focus on specific room
        pred = predictions.get(str(detail_id)) or predictions.get(int(detail_id), {})
        if pred:
            context_parts.append(_build_room_detail(pred, detail_id))
    else:
        # Add top movers
        context_parts.append(_build_top_movers(predictions))

    context = "\n\n".join(context_parts)
    user_message = f"## Current Data\n{context}\n\n## Question\n{question}"

    model = CLAUDE_DEEP_MODEL if deep else CLAUDE_ANALYST_MODEL
    response_text = _call_claude(
        system_prompt=ANALYST_SYSTEM_PROMPT,
        user_message=user_message,
        model=model,
        max_tokens=ANALYST_MAX_TOKENS if not deep else 4096,
    )

    elapsed_ms = int((time.time() - start_ms) * 1000)

    if response_text:
        result = AnalystResponse(
            answer=response_text,
            source="claude",
            model=model,
            processing_time_ms=elapsed_ms,
        )
    else:
        # Fallback — generate stats-based response
        result = _fallback_answer(question, analysis, detail_id)
        result.processing_time_ms = elapsed_ms

    _cache_set(cache_key, {
        "answer": result.answer,
        "source": result.source,
        "model": result.model,
        "tokens_used": result.tokens_used,
        "processing_time_ms": result.processing_time_ms,
    })

    return result


def generate_market_brief(
    analysis: dict,
    language: str = "en",
) -> AnalystResponse:
    """Generate an executive market brief.

    Args:
        analysis: Full analysis dict
        language: "en" for English, "he" for Hebrew

    Returns:
        AnalystResponse with the brief
    """
    start_ms = time.time()

    cache_key = hashlib.md5(f"brief:{language}:{analysis.get('run_ts', '')}".encode()).hexdigest()
    cached = _cache_get(cache_key)
    if cached:
        cached["cached"] = True
        return AnalystResponse(**cached)

    predictions = analysis.get("predictions", {})
    context = _build_portfolio_summary(analysis) + "\n\n" + _build_top_movers(predictions, 20)

    lang_instruction = ""
    if language == "he":
        lang_instruction = "\n\nPlease write the brief in Hebrew (עברית). Use business Hebrew with technical terms in English where needed."

    user_message = f"## Current Data\n{context}\n\nGenerate a market brief for the trading team.{lang_instruction}"

    response_text = _call_claude(
        system_prompt=BRIEF_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=3000,
        temperature=0.4,
    )

    elapsed_ms = int((time.time() - start_ms) * 1000)

    if response_text:
        result = AnalystResponse(
            answer=response_text,
            source="claude",
            model=CLAUDE_ANALYST_MODEL,
            processing_time_ms=elapsed_ms,
        )
    else:
        result = _fallback_brief(analysis, language)
        result.processing_time_ms = elapsed_ms

    _cache_set(cache_key, {
        "answer": result.answer,
        "source": result.source,
        "model": result.model,
        "tokens_used": result.tokens_used,
        "processing_time_ms": result.processing_time_ms,
    })

    return result


def enrich_room_metadata(
    pred: dict,
    detail_id: int | str,
    analysis: dict | None = None,
) -> dict:
    """Generate smart AI metadata tags for a single room.

    Returns dict with: tag, one_liner, action, confidence_emoji, key_factor
    """
    cache_key = hashlib.md5(f"meta:{detail_id}:{pred.get('current_price')}:{pred.get('expected_change_pct')}".encode()).hexdigest()
    cached = _cache_get(cache_key)
    if cached:
        return cached

    room_context = _build_room_detail(pred, detail_id)

    response_text = _call_claude(
        system_prompt=METADATA_SYSTEM_PROMPT,
        user_message=f"Generate metadata for this room:\n\n{room_context}",
        max_tokens=300,
        temperature=0.2,
    )

    if response_text:
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]+\}', response_text, re.DOTALL)
            if json_match:
                meta = json.loads(json_match.group())
                _cache_set(cache_key, meta)
                return meta
        except (json.JSONDecodeError, AttributeError):
            pass

    # Fallback — rule-based metadata
    meta = _fallback_metadata(pred, detail_id)
    _cache_set(cache_key, meta)
    return meta


def explain_prediction(
    pred: dict,
    detail_id: int | str,
    analysis: dict | None = None,
) -> AnalystResponse:
    """Generate a deep explanation of a specific prediction."""
    start_ms = time.time()

    cache_key = hashlib.md5(f"explain:{detail_id}:{pred.get('current_price')}".encode()).hexdigest()
    cached = _cache_get(cache_key)
    if cached:
        cached["cached"] = True
        return AnalystResponse(**cached)

    room_context = _build_room_detail(pred, detail_id)

    # Add events if available
    events_context = ""
    if analysis:
        next_events = analysis.get("events", {}).get("next_events", [])
        if next_events:
            events_context = "\n\nUpcoming Events:\n" + "\n".join(
                f"  - {e.get('name', '?')}: {e.get('start_date', '?')} (impact: {e.get('hotel_impact', '?')})"
                for e in next_events[:5]
            )

    user_message = (
        f"Explain this prediction in detail:\n\n{room_context}{events_context}\n\n"
        f"Walk through each factor and explain why the model predicts "
        f"${float(pred.get('predicted_checkin_price', 0) or 0):.2f} "
        f"({float(pred.get('expected_change_pct', 0) or 0):+.1f}%) for this room."
    )

    response_text = _call_claude(
        system_prompt=EXPLAIN_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=2048,
    )

    elapsed_ms = int((time.time() - start_ms) * 1000)

    if response_text:
        result = AnalystResponse(
            answer=response_text,
            source="claude",
            model=CLAUDE_ANALYST_MODEL,
            processing_time_ms=elapsed_ms,
        )
    else:
        result = _fallback_explain(pred, detail_id)
        result.processing_time_ms = elapsed_ms

    _cache_set(cache_key, {
        "answer": result.answer,
        "source": result.source,
        "model": result.model,
        "tokens_used": result.tokens_used,
        "processing_time_ms": result.processing_time_ms,
    })

    return result


def batch_enrich_metadata(
    predictions: dict,
    limit: int = 50,
) -> dict[str, dict]:
    """Enrich top rooms with AI metadata. Returns {detail_id: metadata}."""
    # Prioritize rooms with strongest signals
    items = []
    for pid, pred in predictions.items():
        chg = abs(float(pred.get("expected_change_pct", 0) or 0))
        items.append((pid, pred, chg))
    items.sort(key=lambda x: x[2], reverse=True)

    results = {}
    for pid, pred, _ in items[:limit]:
        try:
            results[str(pid)] = enrich_room_metadata(pred, pid)
        except (KeyError, ValueError, TypeError, ConnectionError) as e:
            logger.debug("Metadata enrichment failed for %s: %s", pid, e)
            results[str(pid)] = _fallback_metadata(pred, pid)

    return results


# ---------------------------------------------------------------------------
# Fallback Responses (when Claude API is not available)
# ---------------------------------------------------------------------------

def _fallback_answer(question: str, analysis: dict, detail_id=None) -> AnalystResponse:
    """Generate a data-driven answer without Claude."""
    predictions = analysis.get("predictions", {})
    stats = analysis.get("statistics", {})
    q_lower = question.lower()

    answer_parts = []

    if detail_id:
        pred = predictions.get(str(detail_id)) or predictions.get(int(detail_id))
        if pred:
            chg = float(pred.get("expected_change_pct", 0) or 0)
            signal = "CALL" if chg > 2 else "PUT" if chg < -2 else "NEUTRAL"
            answer_parts.append(
                f"**{pred.get('hotel_name')}** — {pred.get('category')} ({pred.get('board')})\n"
                f"- Current: ${float(pred.get('current_price', 0)):.2f}\n"
                f"- Predicted: ${float(pred.get('predicted_checkin_price', 0)):.2f} ({chg:+.1f}%)\n"
                f"- Signal: {signal} | Confidence: {pred.get('confidence_quality', '?')}\n"
                f"- Days to check-in: {pred.get('days_to_checkin')}"
            )
        else:
            answer_parts.append(f"Room {detail_id} not found in current analysis.")

    elif any(w in q_lower for w in ["summary", "overview", "status", "סיכום", "סטטוס"]):
        n = len(predictions)
        calls = sum(1 for p in predictions.values() if float(p.get("expected_change_pct", 0) or 0) > 2)
        puts = sum(1 for p in predictions.values() if float(p.get("expected_change_pct", 0) or 0) < -2)
        answer_parts.append(
            f"**Portfolio Summary**\n"
            f"- {n} rooms across {stats.get('total_hotels', 0)} hotels\n"
            f"- {calls} CALL / {puts} PUT / {n-calls-puts} NEUTRAL\n"
            f"- Price range: ${stats.get('price_min', 0):.0f} – ${stats.get('price_max', 0):.0f}\n"
            f"- Mean price: ${stats.get('price_mean', 0):.0f}"
        )

    elif any(w in q_lower for w in ["risk", "danger", "put", "avoid", "worst", "drop", "decline", "סיכון", "מסוכן"]):
        top_puts = sorted(
            [(pid, p) for pid, p in predictions.items() if float(p.get("expected_change_pct", 0) or 0) < -2],
            key=lambda x: float(x[1].get("expected_change_pct", 0) or 0),
        )[:5]
        if top_puts:
            answer_parts.append("**Highest Risk (PUT) Positions:**")
            for pid, p in top_puts:
                chg = float(p.get("expected_change_pct", 0) or 0)
                answer_parts.append(
                    f"- {p.get('hotel_name')[:30]} ({p.get('category')}): "
                    f"${float(p.get('current_price', 0)):.0f} → {chg:+.1f}%"
                )
        else:
            answer_parts.append("No significant PUT signals detected.")

    elif any(w in q_lower for w in ["best", "top", "opportunity", "call", "הזדמנות", "הכי טוב", "buy"]):
        top_calls = sorted(
            [(pid, p) for pid, p in predictions.items() if float(p.get("expected_change_pct", 0) or 0) > 2],
            key=lambda x: float(x[1].get("expected_change_pct", 0) or 0),
            reverse=True,
        )[:5]
        if top_calls:
            answer_parts.append("**Top CALL Opportunities:**")
            for pid, p in top_calls:
                chg = float(p.get("expected_change_pct", 0) or 0)
                answer_parts.append(
                    f"- {p.get('hotel_name')[:30]} ({p.get('category')}): "
                    f"${float(p.get('current_price', 0)):.0f} → +{chg:.1f}%"
                )
        else:
            answer_parts.append("No strong CALL signals in current portfolio.")

    elif any(w in q_lower for w in ["hotel", "מלון", "hilton", "breakwater", "sls", "citizenm", "marriott", "embassy", "hyatt"]):
        # Search for hotel name in question
        hotels = analysis.get("hotels", [])
        matched = None
        for h in hotels:
            if h.get("hotel_name", "").lower() in q_lower:
                matched = h
                break
        if not matched:
            # Try partial match
            for h in hotels:
                name_parts = h.get("hotel_name", "").lower().split()
                if any(p in q_lower for p in name_parts if len(p) > 3):
                    matched = h
                    break

        if matched:
            # Find rooms for this hotel
            hotel_rooms = [(pid, p) for pid, p in predictions.items()
                          if p.get("hotel_name") == matched.get("hotel_name")]
            hotel_calls = sum(1 for _, p in hotel_rooms if float(p.get("expected_change_pct", 0) or 0) > 2)
            hotel_puts = sum(1 for _, p in hotel_rooms if float(p.get("expected_change_pct", 0) or 0) < -2)
            answer_parts.append(
                f"**{matched.get('hotel_name')}**\n"
                f"- {matched.get('total_rooms')} rooms\n"
                f"- Price: ${matched.get('price_min', 0):.0f}–${matched.get('price_max', 0):.0f} "
                f"(avg ${matched.get('price_mean', 0):.0f})\n"
                f"- Signals: {hotel_calls} CALL / {hotel_puts} PUT / {len(hotel_rooms)-hotel_calls-hotel_puts} NEUTRAL\n"
                f"- Categories: {', '.join(matched.get('categories', []))}\n"
                f"- Check-in range: {matched.get('date_range', '?')}"
            )
        else:
            answer_parts.append("Hotels in portfolio: " + ", ".join(
                h.get("hotel_name", "?") for h in hotels
            ))

    elif any(w in q_lower for w in ["event", "events", "concert", "game", "אירוע"]):
        events_data = analysis.get("events", {})
        next_events = events_data.get("next_events", [])
        if next_events:
            answer_parts.append(f"**Upcoming Events ({events_data.get('upcoming_events', 0)} total):**")
            for e in next_events[:8]:
                answer_parts.append(
                    f"- **{e.get('name', '?')}**: {e.get('start_date', '?')} to {e.get('end_date', '?')} "
                    f"(impact: {e.get('hotel_impact', '?')}, attendance: {e.get('expected_attendance', '?')})"
                )
        else:
            answer_parts.append("No upcoming events data available.")

    elif any(w in q_lower for w in ["momentum", "accelerat", "velocity", "מומנטום"]):
        accel_rooms = [(pid, p) for pid, p in predictions.items()
                       if isinstance(p.get("momentum"), dict) and "ACCELERATING" in p["momentum"].get("signal", "")]
        if accel_rooms:
            answer_parts.append(f"**Rooms with Momentum Signals ({len(accel_rooms)}):**")
            for pid, p in accel_rooms[:10]:
                mom = p.get("momentum", {})
                answer_parts.append(
                    f"- {p.get('hotel_name', '?')[:25]} ({p.get('category')}): "
                    f"{mom.get('signal')} (v24h={mom.get('velocity_24h', 0):.1f}%, "
                    f"strength={mom.get('strength', 0):.2f})"
                )
        else:
            answer_parts.append("No rooms with active momentum signals.")

    elif any(w in q_lower for w in ["regime", "volatile", "trending", "stale"]):
        regime_counts: dict[str, int] = {}
        for p in predictions.values():
            r = p.get("regime", {})
            regime_name = r.get("regime", "NORMAL") if isinstance(r, dict) else "NORMAL"
            regime_counts[regime_name] = regime_counts.get(regime_name, 0) + 1
        answer_parts.append("**Market Regime Distribution:**")
        for regime_name, count in sorted(regime_counts.items(), key=lambda x: -x[1]):
            answer_parts.append(f"- {regime_name}: {count} rooms")

    else:
        answer_parts.append(
            f"I have data on {len(predictions)} rooms across {stats.get('total_hotels', 0)} hotels. "
            f"Ask me about specific hotels, top opportunities, risks, market summary, or any room by ID. "
            f"(Claude API not configured — using statistical fallback.)"
        )

    return AnalystResponse(
        answer="\n".join(answer_parts),
        source="fallback",
        model="rule_based",
    )


def _fallback_brief(analysis: dict, language: str = "en") -> AnalystResponse:
    """Generate a rule-based market brief."""
    predictions = analysis.get("predictions", {})
    stats = analysis.get("statistics", {})
    events = analysis.get("events", {})

    n = len(predictions)
    calls = sum(1 for p in predictions.values() if float(p.get("expected_change_pct", 0) or 0) > 2)
    puts = sum(1 for p in predictions.values() if float(p.get("expected_change_pct", 0) or 0) < -2)
    neutrals = n - calls - puts

    changes = [float(p.get("expected_change_pct", 0) or 0) for p in predictions.values()]
    avg_change = sum(changes) / len(changes) if changes else 0
    tone = "BULLISH" if calls > puts * 1.5 else "BEARISH" if puts > calls * 1.5 else "MIXED"

    next_events = events.get("next_events", [])
    event_str = ""
    if next_events:
        event_str = (
            f"\n\n**Events:** {len(next_events)} upcoming events, "
            f"including {next_events[0].get('name', '?')} "
            f"({next_events[0].get('start_date', '?')}, impact: {next_events[0].get('hotel_impact', '?')})."
        )

    if language == "he":
        brief = (
            f"# סיכום שוק יומי\n\n"
            f"**מצב שוק: {tone}** — {n} חדרים ב-{stats.get('total_hotels', 0)} מלונות\n"
            f"- {calls} אותות CALL / {puts} אותות PUT / {neutrals} NEUTRAL\n"
            f"- שינוי ממוצע צפוי: {avg_change:+.1f}%\n"
            f"- טווח מחירים: ${stats.get('price_min', 0):.0f} – ${stats.get('price_max', 0):.0f}\n"
            f"- ערך מלאי כולל: ${stats.get('total_inventory_value', 0):,.0f}"
            f"{event_str}\n\n"
            f"*נוצר אוטומטית — Claude API לא מוגדר, משתמש בניתוח סטטיסטי.*"
        )
    else:
        brief = (
            f"# Daily Market Brief\n\n"
            f"**Market Tone: {tone}** — {n} rooms across {stats.get('total_hotels', 0)} hotels\n"
            f"- {calls} CALL / {puts} PUT / {neutrals} NEUTRAL signals\n"
            f"- Average predicted change: {avg_change:+.1f}%\n"
            f"- Price range: ${stats.get('price_min', 0):.0f} – ${stats.get('price_max', 0):.0f}\n"
            f"- Total inventory value: ${stats.get('total_inventory_value', 0):,.0f}"
            f"{event_str}\n\n"
            f"*Auto-generated — Claude API not configured, using statistical analysis.*"
        )

    return AnalystResponse(answer=brief, source="fallback", model="rule_based")


def _fallback_metadata(pred: dict, detail_id) -> dict:
    """Rule-based metadata enrichment."""
    chg = float(pred.get("expected_change_pct", 0) or 0)
    quality = pred.get("confidence_quality", "low")
    mom = pred.get("momentum", {})
    mom_signal = mom.get("signal", "NORMAL") if isinstance(mom, dict) else "NORMAL"

    # Tag
    if chg > 15 and quality == "high":
        tag = "hot_deal"
    elif abs(chg) > 20:
        tag = "risky"
    elif "ACCELERATING" in mom_signal:
        tag = "momentum_play"
    elif chg > 5:
        tag = "watch"
    elif chg < -10:
        tag = "contrarian"
    elif abs(chg) < 3:
        tag = "stable"
    else:
        tag = "watch"

    # Action
    if chg > 10 and quality in ("high", "medium"):
        action = "BUY_NOW"
    elif chg > 3:
        action = "MONITOR"
    elif chg < -10:
        action = "AVOID"
    elif quality == "low":
        action = "REVIEW"
    else:
        action = "WAIT"

    # Emoji
    emoji = "🟢" if quality == "high" else "🟡" if quality == "medium" else "🔴"

    # Key factor
    sigs = pred.get("signals", [])
    if sigs:
        top_sig = max(sigs, key=lambda s: s.get("weight", 0))
        key_factor = f"{top_sig.get('source', '?')} ({top_sig.get('weight', 0):.0%} weight)"
    else:
        key_factor = "forward_curve (default)"

    # One-liner
    signal_word = "rise" if chg > 2 else "drop" if chg < -2 else "hold steady"
    one_liner = (
        f"Expected to {signal_word} {abs(chg):.1f}% — "
        f"{quality} confidence, {pred.get('days_to_checkin', '?')}d to check-in"
    )

    return {
        "tag": tag,
        "one_liner": one_liner,
        "action": action,
        "confidence_emoji": emoji,
        "key_factor": key_factor,
    }


def _fallback_explain(pred: dict, detail_id) -> AnalystResponse:
    """Rule-based prediction explanation."""
    lines = [f"## Prediction Explanation — Room {detail_id}\n"]

    sigs = pred.get("signals", [])
    for s in sigs:
        lines.append(
            f"### {s.get('source', '?').replace('_', ' ').title()}\n"
            f"- Predicted: ${s.get('predicted_price', 0):.2f}\n"
            f"- Weight: {s.get('weight', 0):.0%}\n"
            f"- Confidence: {s.get('confidence', 0):.2f}\n"
            f"- Reasoning: {s.get('reasoning', 'N/A')}\n"
        )

    scan = pred.get("scan_history", {})
    if scan and isinstance(scan, dict) and scan.get("scan_snapshots", 0) > 0:
        lines.append(
            f"### Actual Price History\n"
            f"- {scan.get('scan_snapshots', 0)} observations\n"
            f"- Trend: {scan.get('scan_trend', '?')}\n"
            f"- Change: {scan.get('scan_price_change_pct', 0):+.1f}%\n"
        )

    quality = pred.get("confidence_quality", "?")
    lines.append(
        f"\n**Overall Confidence: {quality}** — "
        f"Based on {len(sigs)} signals with {pred.get('prediction_method', '?')} method."
    )

    return AnalystResponse(
        answer="\n".join(lines),
        source="fallback",
        model="rule_based",
    )
