"""AI Intelligence Engine — Claude-powered analysis for hotel price predictions.

Inspired by Anthropic's financial-services-plugins (equity-research, financial-analysis)
and claude-cookbooks patterns. Uses Claude Haiku for fast, cost-effective analysis.

Capabilities:
  1. Market Narrative — AI-generated natural language market analysis
  2. Event Impact Analysis — Intelligent event → price impact estimation
  3. Anomaly Detection — AI-powered pricing anomaly identification
  4. Signal Synthesis — Cross-signal interpretation and conflict resolution
  5. Risk Assessment — Intelligent risk scoring with reasoning
  6. Bayesian Confidence — Dynamic confidence updates using prior performance
  7. Competitive Intelligence — Market positioning analysis

Architecture inspired by Anthropic's financial-services-plugins structure:
  skills/  → Domain expertise encoded as structured prompts
  analysis → Claude API calls with tool-use for structured output
  cache    → Intelligent caching to minimize API calls
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_AI_MODEL", "claude-haiku-4-20250514")
AI_CACHE_TTL_SECONDS = int(os.getenv("AI_CACHE_TTL_SECONDS", "1800"))  # 30 min
AI_ENABLED = os.getenv("AI_INTELLIGENCE_ENABLED", "true").lower() in ("true", "1", "yes")
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1024"))
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.2"))  # Low temp for analytical tasks

# Cache via unified CacheManager (region "ai")
from src.utils.cache_manager import cache as _cm


def _cache_get(key: str) -> Any | None:
    """Get from cache if not expired."""
    return _cm.get("ai", key)


def _cache_set(key: str, val: Any) -> None:
    """Set cache with TTL."""
    _cm.set("ai", key, val)


def _get_client():
    """Lazy-init Anthropic client."""
    try:
        import anthropic
        if not ANTHROPIC_API_KEY:
            return None
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        logger.warning("anthropic SDK not installed")
        return None
    except (ConnectionError, ValueError, RuntimeError) as e:
        logger.warning("Failed to create Anthropic client: %s", e)
        return None


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class AIMarketNarrative:
    """AI-generated market narrative for a prediction."""
    summary: str = ""
    key_drivers: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    confidence_assessment: str = ""
    recommended_action: str = ""
    reasoning_chain: str = ""

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "key_drivers": self.key_drivers,
            "risk_factors": self.risk_factors,
            "confidence_assessment": self.confidence_assessment,
            "recommended_action": self.recommended_action,
            "reasoning_chain": self.reasoning_chain,
        }


@dataclass
class AIAnomalyReport:
    """AI-detected pricing anomaly."""
    is_anomaly: bool = False
    anomaly_type: str = ""  # SPIKE | DIP | STALE | DIVERGENCE | NONE
    severity: str = "none"  # none | low | medium | high | critical
    explanation: str = ""
    suggested_action: str = ""

    def to_dict(self) -> dict:
        return {
            "is_anomaly": self.is_anomaly,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "explanation": self.explanation,
            "suggested_action": self.suggested_action,
        }


@dataclass
class AISignalSynthesis:
    """AI cross-signal synthesis — resolves conflicts between signals."""
    dominant_signal: str = ""       # Which signal should be trusted most
    conflict_detected: bool = False
    conflict_resolution: str = ""
    adjusted_weights: dict = field(default_factory=dict)
    synthesis_narrative: str = ""
    overall_conviction: str = ""    # high | medium | low | very_low

    def to_dict(self) -> dict:
        return {
            "dominant_signal": self.dominant_signal,
            "conflict_detected": self.conflict_detected,
            "conflict_resolution": self.conflict_resolution,
            "adjusted_weights": self.adjusted_weights,
            "synthesis_narrative": self.synthesis_narrative,
            "overall_conviction": self.overall_conviction,
        }


@dataclass
class AIRiskAssessment:
    """AI risk assessment for a trading position."""
    risk_score: float = 0.5       # 0.0 (safe) to 1.0 (dangerous)
    risk_level: str = "medium"    # low | medium | high | extreme
    max_downside_pct: float = 0.0
    max_upside_pct: float = 0.0
    key_risks: list[str] = field(default_factory=list)
    hedging_suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "risk_score": round(self.risk_score, 3),
            "risk_level": self.risk_level,
            "max_downside_pct": round(self.max_downside_pct, 1),
            "max_upside_pct": round(self.max_upside_pct, 1),
            "key_risks": self.key_risks,
            "hedging_suggestion": self.hedging_suggestion,
        }


# ---------------------------------------------------------------------------
#  Prompt Templates (inspired by financial-services-plugins skills)
# ---------------------------------------------------------------------------
MARKET_NARRATIVE_SYSTEM = """You are a senior hotel revenue management analyst at a trading desk.
You analyze hotel room price data the way a quant analyst analyzes financial instruments.

Your analysis should be:
- Data-driven with specific numbers cited
- Concise (3-4 sentences per section)
- Written in professional trading desk style
- Focused on actionable insights

Output MUST be valid JSON with these exact keys:
{
  "summary": "1-2 sentence executive summary",
  "key_drivers": ["driver1", "driver2", "driver3"],
  "risk_factors": ["risk1", "risk2"],
  "confidence_assessment": "HIGH|MEDIUM|LOW with brief reason",
  "recommended_action": "BUY_NOW|WAIT|HOLD|SELL_SOON with timing",
  "reasoning_chain": "Step-by-step logic connecting data to conclusion"
}"""

ANOMALY_DETECTION_SYSTEM = """You are a quantitative anomaly detection system for hotel pricing.
You identify unusual pricing patterns the way a trading surveillance system flags suspicious activity.

Analyze the pricing data and determine if there's an anomaly.

Output MUST be valid JSON:
{
  "is_anomaly": true/false,
  "anomaly_type": "SPIKE|DIP|STALE|DIVERGENCE|UNUSUAL_VOLATILITY|NONE",
  "severity": "none|low|medium|high|critical",
  "explanation": "brief explanation",
  "suggested_action": "what to do about it"
}"""

SIGNAL_SYNTHESIS_SYSTEM = """You are a multi-signal fusion analyst for hotel price trading.
You resolve conflicts between different prediction signals similar to how a multi-strategy
hedge fund allocates across competing models.

Given the signals from Forward Curve, Historical Pattern, and other sources,
synthesize them into a unified view.

Output MUST be valid JSON:
{
  "dominant_signal": "forward_curve|historical_pattern|ml_forecast",
  "conflict_detected": true/false,
  "conflict_resolution": "explanation of how conflict was resolved",
  "adjusted_weights": {"forward_curve": 0.X, "historical_pattern": 0.X, "ml_forecast": 0.X},
  "synthesis_narrative": "unified 2-3 sentence synthesis",
  "overall_conviction": "high|medium|low|very_low"
}"""

RISK_ASSESSMENT_SYSTEM = """You are a risk analyst for hotel room price trading.
You assess risk the way a derivatives trader evaluates option positions.

Analyze the position data and provide a risk assessment.

Output MUST be valid JSON:
{
  "risk_score": 0.0-1.0,
  "risk_level": "low|medium|high|extreme",
  "max_downside_pct": -X.X,
  "max_upside_pct": +X.X,
  "key_risks": ["risk1", "risk2"],
  "hedging_suggestion": "brief suggestion"
}"""


# ---------------------------------------------------------------------------
# Intelligent fallback (rule-based when Claude is unavailable)
# ---------------------------------------------------------------------------
class RuleBasedFallback:
    """Statistical fallback when Claude API is unavailable.

    Uses quantitative heuristics inspired by algorithmic trading systems.
    """

    @staticmethod
    def generate_narrative(context: dict) -> AIMarketNarrative:
        """Generate rule-based market narrative from data."""
        current = context.get("current_price", 0)
        predicted = context.get("predicted_price", 0)
        change_pct = context.get("change_pct", 0)
        days = context.get("days_to_checkin", 0)
        signal = context.get("signal", "NEUTRAL")
        regime = context.get("regime", "NORMAL")
        momentum_signal = context.get("momentum_signal", "NORMAL")
        events = context.get("events", [])
        scans = context.get("scan_count", 0)
        scan_drops = context.get("scan_drops", 0)
        scan_rises = context.get("scan_rises", 0)

        # Build narrative
        direction = "rise" if change_pct > 0 else "drop" if change_pct < 0 else "remain stable"
        drivers = []
        risks = []

        # Key driver analysis
        if events:
            event_names = [e.get("name", "event") for e in events[:3]]
            drivers.append(f"Upcoming events ({', '.join(event_names)}) creating demand pressure")
        if regime == "TRENDING_UP":
            drivers.append("Price in upward trend — momentum favoring continued rises")
        elif regime == "TRENDING_DOWN":
            drivers.append("Price in downward trend — momentum favoring continued drops")
        if days <= 14:
            drivers.append(f"Only {days} days to check-in — last-minute pricing dynamics active")
        elif days > 60:
            drivers.append(f"{days} days out — early booking period with higher uncertainty")
        if momentum_signal in ("ACCELERATING_UP", "ACCELERATING_DOWN"):
            drivers.append(f"Momentum {momentum_signal.lower().replace('_', ' ')} — price velocity increasing")

        if not drivers:
            drivers.append("Forward curve decay pattern is the primary driver")

        # Risk factors
        if scans < 5:
            risks.append("Low scan count — limited data for reliable prediction")
        if regime == "VOLATILE":
            risks.append("High volatility regime — predictions less reliable")
        if abs(change_pct) > 50:
            risks.append(f"Large predicted move ({change_pct:+.1f}%) carries execution risk")
        if scan_drops > scan_rises and signal == "CALL":
            risks.append("Signal conflict: historical scans trending down but CALL signal issued")
        if not risks:
            risks.append("Standard market conditions — no elevated risk detected")

        # Confidence
        if scans >= 10 and regime in ("NORMAL", "TRENDING_UP", "TRENDING_DOWN"):
            conf = "HIGH — sufficient data and clear regime"
        elif scans >= 5:
            conf = "MEDIUM — moderate data, some uncertainty"
        else:
            conf = "LOW — limited scan data, wide confidence interval"

        # Action
        if signal == "PUT" and change_pct < -5:
            action = f"WAIT — price expected to drop {change_pct:.1f}%. Monitor for buying opportunity"
        elif signal == "CALL" and change_pct > 5:
            action = f"BUY_NOW — price expected to rise {change_pct:.1f}%. Lock in current price"
        else:
            action = "HOLD — no strong directional conviction at this time"

        summary = (
            f"Room priced at ${current:,.0f} is expected to {direction} to ${predicted:,.0f} "
            f"({change_pct:+.1f}%) over {days} days to check-in. "
            f"Regime: {regime}. Signal: {signal}."
        )

        return AIMarketNarrative(
            summary=summary,
            key_drivers=drivers,
            risk_factors=risks,
            confidence_assessment=conf,
            recommended_action=action,
            reasoning_chain=f"Current ${current:,.0f} → Predicted ${predicted:,.0f} ({change_pct:+.1f}%) | "
                            f"Signal: {signal} | Regime: {regime} | Momentum: {momentum_signal} | "
                            f"Events: {len(events)} active | Scans: {scans} ({scan_drops}↓/{scan_rises}↑)",
        )

    @staticmethod
    def detect_anomaly(context: dict) -> AIAnomalyReport:
        """Statistical anomaly detection without Claude."""
        current = context.get("current_price", 0)
        predicted = context.get("predicted_price", 0)
        scan_prices = context.get("scan_prices", [])
        change_pct = context.get("change_pct", 0)
        regime = context.get("regime", "NORMAL")

        if not scan_prices or len(scan_prices) < 3:
            return AIAnomalyReport()

        import numpy as np
        prices = np.array(scan_prices)
        mean_p = np.mean(prices)
        std_p = np.std(prices) if len(prices) > 1 else 0
        last_p = prices[-1]

        # Z-score of latest price vs scan history
        z = (last_p - mean_p) / std_p if std_p > 0 else 0

        # Stale detection
        unique_prices = len(set(round(p, 2) for p in scan_prices[-10:]))
        if unique_prices <= 1 and len(scan_prices) >= 5:
            return AIAnomalyReport(
                is_anomaly=True,
                anomaly_type="STALE",
                severity="medium",
                explanation=f"Price unchanged at ${last_p:.0f} across {len(scan_prices)} scans — possibly stale inventory",
                suggested_action="Verify room availability is still active. Stale prices may indicate delisted inventory.",
            )

        # Spike detection
        if z > 3.0:
            return AIAnomalyReport(
                is_anomaly=True,
                anomaly_type="SPIKE",
                severity="high" if z > 4.0 else "medium",
                explanation=f"Price ${last_p:.0f} is {z:.1f}σ above mean ${mean_p:.0f} — unusual spike",
                suggested_action="Review if spike is event-driven or data error. Consider waiting for reversion.",
            )

        # Dip detection
        if z < -3.0:
            return AIAnomalyReport(
                is_anomaly=True,
                anomaly_type="DIP",
                severity="high" if z < -4.0 else "medium",
                explanation=f"Price ${last_p:.0f} is {abs(z):.1f}σ below mean ${mean_p:.0f} — unusual dip",
                suggested_action="Potential buying opportunity if dip is temporary. Verify no quality issues.",
            )

        # High volatility detection
        if std_p > 0 and (std_p / mean_p) > 0.15:
            return AIAnomalyReport(
                is_anomaly=True,
                anomaly_type="UNUSUAL_VOLATILITY",
                severity="low",
                explanation=f"Coefficient of variation {(std_p/mean_p)*100:.1f}% exceeds 15% threshold",
                suggested_action="Higher uncertainty in predictions. Use wider confidence intervals.",
            )

        # Divergence: predicted vs actual trend disagree
        if len(scan_prices) >= 3:
            actual_trend = scan_prices[-1] - scan_prices[0]
            if (actual_trend > 0 and change_pct < -10) or (actual_trend < 0 and change_pct > 10):
                return AIAnomalyReport(
                    is_anomaly=True,
                    anomaly_type="DIVERGENCE",
                    severity="medium",
                    explanation=(
                        f"Actual trend ({'up' if actual_trend > 0 else 'down'} ${abs(actual_trend):.0f}) "
                        f"contradicts predicted trend ({change_pct:+.1f}%)"
                    ),
                    suggested_action="Model may be lagging. Re-evaluate signal weights and look for structural changes.",
                )

        return AIAnomalyReport()

    @staticmethod
    def synthesize_signals(context: dict) -> AISignalSynthesis:
        """Rule-based signal synthesis."""
        signals = context.get("signals", [])
        if not signals:
            return AISignalSynthesis(overall_conviction="very_low")

        # Find dominant signal (highest weight × confidence)
        best = max(signals, key=lambda s: s.get("weight", 0) * s.get("confidence", 0))
        dominant = best.get("source", "unknown")

        # Detect conflicts: signals pointing in opposite directions
        predicted_prices = [s.get("predicted_price", 0) for s in signals if s.get("predicted_price", 0) > 0]
        current = context.get("current_price", 0)
        conflict = False
        resolution = ""

        if len(predicted_prices) >= 2 and current > 0:
            directions = [p / current - 1 for p in predicted_prices]
            # Conflict if signals disagree on direction by >10%
            if any(d > 0.1 for d in directions) and any(d < -0.1 for d in directions):
                conflict = True
                resolution = (
                    f"Signals disagree: {dominant} is dominant (weight×conf = "
                    f"{best.get('weight',0):.0%}×{best.get('confidence',0):.0%}). "
                    f"Using confidence-weighted ensemble to resolve."
                )

        # Adjusted weights based on confidence
        total_wc = sum(s.get("weight", 0) * s.get("confidence", 0) for s in signals)
        adj_weights = {}
        for s in signals:
            src = s.get("source", "unknown")
            wc = s.get("weight", 0) * s.get("confidence", 0)
            adj_weights[src] = round(wc / total_wc, 3) if total_wc > 0 else 0

        # Conviction level
        max_conf = max((s.get("confidence", 0) for s in signals), default=0)
        if max_conf >= 0.7 and not conflict:
            conviction = "high"
        elif max_conf >= 0.5:
            conviction = "medium"
        elif max_conf >= 0.3:
            conviction = "low"
        else:
            conviction = "very_low"

        return AISignalSynthesis(
            dominant_signal=dominant,
            conflict_detected=conflict,
            conflict_resolution=resolution,
            adjusted_weights=adj_weights,
            synthesis_narrative=f"Primary signal: {dominant} ({best.get('confidence',0):.0%} confidence). "
                                f"{'CONFLICT detected — using weighted resolution. ' if conflict else ''}"
                                f"Overall conviction: {conviction}.",
            overall_conviction=conviction,
        )

    @staticmethod
    def assess_risk(context: dict) -> AIRiskAssessment:
        """Rule-based risk assessment."""
        change_pct = context.get("change_pct", 0)
        days = context.get("days_to_checkin", 0)
        scans = context.get("scan_count", 0)
        regime = context.get("regime", "NORMAL")
        quality = context.get("quality_score", 0.5)

        risks = []
        score = 0.3  # base risk

        # Magnitude risk
        if abs(change_pct) > 100:
            score += 0.3
            risks.append(f"Extreme predicted move ({change_pct:+.1f}%)")
        elif abs(change_pct) > 50:
            score += 0.15
            risks.append(f"Large predicted move ({change_pct:+.1f}%)")

        # Time risk
        if days <= 3:
            score += 0.15
            risks.append("Very close to check-in — limited time to react")
        elif days <= 7:
            score += 0.05

        # Data risk
        if scans < 3:
            score += 0.15
            risks.append("Very limited scan data (< 3 scans)")
        elif scans < 10:
            score += 0.05

        # Regime risk
        if regime == "VOLATILE":
            score += 0.1
            risks.append("Volatile price regime")
        elif regime == "STALE":
            score += 0.05
            risks.append("Stale price — may not reflect current market")

        # Quality risk
        if quality < 0.3:
            score += 0.1
            risks.append("Low prediction quality score")

        score = min(score, 1.0)
        level = "low" if score < 0.35 else "medium" if score < 0.55 else "high" if score < 0.8 else "extreme"

        # Upside/downside estimates
        vol_factor = 1.5 if regime == "VOLATILE" else 1.0
        max_up = min(change_pct * 1.3 * vol_factor, 200) if change_pct > 0 else min(abs(change_pct) * 0.3, 30)
        max_down = min(abs(change_pct) * 1.3 * vol_factor, 200) if change_pct < 0 else min(change_pct * 0.3, 30)

        return AIRiskAssessment(
            risk_score=score,
            risk_level=level,
            max_downside_pct=-abs(max_down),
            max_upside_pct=abs(max_up),
            key_risks=risks if risks else ["Standard market conditions"],
            hedging_suggestion=(
                "Consider booking now to lock in price" if level in ("high", "extreme") and change_pct > 0
                else "Wait for potential price drop" if change_pct < -10
                else "Monitor — no urgent action required"
            ),
        )


# ---------------------------------------------------------------------------
# Bayesian Confidence Updater
# ---------------------------------------------------------------------------
class BayesianConfidence:
    """Bayesian confidence tracker — learns from prediction accuracy over time.

    Inspired by the adaptive weight allocation in algo-trading systems.
    Maintains a prior on each signal source's reliability and updates it
    with observed outcomes.
    """

    def __init__(self):
        # Prior: Beta(alpha, beta) for each source
        # alpha ~ number of successes, beta ~ number of failures
        self._priors: dict[str, dict[str, float]] = {
            "forward_curve": {"alpha": 10.0, "beta": 5.0},     # Starts favorable
            "historical_pattern": {"alpha": 7.0, "beta": 7.0},  # Neutral
            "ml_forecast": {"alpha": 5.0, "beta": 5.0},         # Neutral
        }

    def get_reliability(self, source: str) -> float:
        """Get current reliability estimate (Beta mean) for a source."""
        p = self._priors.get(source, {"alpha": 5.0, "beta": 5.0})
        return p["alpha"] / (p["alpha"] + p["beta"])

    def update(self, source: str, was_correct: bool, weight: float = 1.0) -> None:
        """Update belief about a source's reliability.

        Args:
            source: Signal source name
            was_correct: Whether the prediction direction was correct
            weight: How much to weight this observation (0-1)
        """
        if source not in self._priors:
            self._priors[source] = {"alpha": 5.0, "beta": 5.0}
        if was_correct:
            self._priors[source]["alpha"] += weight
        else:
            self._priors[source]["beta"] += weight

    def get_adjusted_weights(self, base_weights: dict[str, float]) -> dict[str, float]:
        """Adjust base weights using Bayesian reliability estimates.

        Multiplies each source's base weight by its observed reliability,
        then normalizes.
        """
        adjusted = {}
        for source, base_w in base_weights.items():
            reliability = self.get_reliability(source)
            adjusted[source] = base_w * reliability

        total = sum(adjusted.values())
        if total > 0:
            return {k: round(v / total, 4) for k, v in adjusted.items()}
        return base_weights

    def to_dict(self) -> dict:
        return {
            source: {
                "alpha": round(p["alpha"], 1),
                "beta": round(p["beta"], 1),
                "reliability": round(self.get_reliability(source), 3),
            }
            for source, p in self._priors.items()
        }


# ---------------------------------------------------------------------------
# Claude AI Calls (with fallback)
# ---------------------------------------------------------------------------
def _call_claude(system: str, user_prompt: str, cache_key: str | None = None) -> dict | None:
    """Call Claude API and parse JSON response. Falls back gracefully."""
    if cache_key:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    client = _get_client()
    if client is None:
        return None

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=AI_MAX_TOKENS,
            temperature=AI_TEMPERATURE,
            system=system,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()
        # Extract JSON from response (handle markdown code blocks)
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        result = json.loads(text)
        if cache_key:
            _cache_set(cache_key, result)
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Claude returned non-JSON: {e}")
        return None
    except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
        logger.warning("Claude API call failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Public API — Main Intelligence Functions
# ---------------------------------------------------------------------------
_bayesian = BayesianConfidence()
_fallback = RuleBasedFallback()


def generate_market_narrative(
    hotel_name: str,
    category: str,
    current_price: float,
    predicted_price: float,
    change_pct: float,
    days_to_checkin: int,
    signal: str,
    regime: str = "NORMAL",
    momentum_signal: str = "NORMAL",
    events: list[dict] | None = None,
    scan_count: int = 0,
    scan_drops: int = 0,
    scan_rises: int = 0,
    fc_price: float | None = None,
    hist_price: float | None = None,
    market_avg: float | None = None,
) -> AIMarketNarrative:
    """Generate AI-powered market narrative for a hotel room prediction.

    Uses Claude if available, falls back to rule-based analysis.
    """
    context = {
        "hotel_name": hotel_name,
        "category": category,
        "current_price": current_price,
        "predicted_price": predicted_price,
        "change_pct": change_pct,
        "days_to_checkin": days_to_checkin,
        "signal": signal,
        "regime": regime,
        "momentum_signal": momentum_signal,
        "events": events or [],
        "scan_count": scan_count,
        "scan_drops": scan_drops,
        "scan_rises": scan_rises,
    }

    if not AI_ENABLED or not ANTHROPIC_API_KEY:
        return _fallback.generate_narrative(context)

    # Build prompt
    events_str = ""
    if events:
        events_str = "\nActive events:\n" + "\n".join(
            f"  - {e.get('name', 'Unknown')}: {e.get('start', '')} to {e.get('end', '')} "
            f"(impact: {e.get('impact_category', 'unknown')})"
            for e in events[:5]
        )

    user_prompt = f"""Analyze this hotel room pricing situation:

Hotel: {hotel_name} ({category})
Current Price: ${current_price:,.2f}
Predicted Check-in Price: ${predicted_price:,.2f} ({change_pct:+.1f}%)
Days to Check-in: {days_to_checkin}
Signal: {signal}
Market Regime: {regime}
Momentum: {momentum_signal}
Scan History: {scan_count} scans ({scan_drops} drops, {scan_rises} rises)
Forward Curve Price: ${fc_price:,.0f} if {fc_price} else 'N/A'
Historical Pattern Price: ${hist_price:,.0f} if {hist_price} else 'N/A'
Market Avg (same star): ${market_avg:,.0f} if {market_avg} else 'N/A'
{events_str}

Provide your analysis as a senior revenue management analyst."""

    cache_key = hashlib.md5(
        f"narrative:{hotel_name}:{current_price}:{predicted_price}:{days_to_checkin}".encode()
    ).hexdigest()

    result = _call_claude(MARKET_NARRATIVE_SYSTEM, user_prompt, cache_key)

    if result:
        return AIMarketNarrative(
            summary=result.get("summary", ""),
            key_drivers=result.get("key_drivers", []),
            risk_factors=result.get("risk_factors", []),
            confidence_assessment=result.get("confidence_assessment", ""),
            recommended_action=result.get("recommended_action", ""),
            reasoning_chain=result.get("reasoning_chain", ""),
        )

    return _fallback.generate_narrative(context)


def detect_anomaly(
    hotel_name: str,
    current_price: float,
    predicted_price: float,
    change_pct: float,
    scan_prices: list[float] | None = None,
    regime: str = "NORMAL",
) -> AIAnomalyReport:
    """Detect pricing anomalies using AI or statistical methods."""
    context = {
        "current_price": current_price,
        "predicted_price": predicted_price,
        "change_pct": change_pct,
        "scan_prices": scan_prices or [],
        "regime": regime,
    }

    # Statistical detection always runs (fast, no API call)
    stat_result = _fallback.detect_anomaly(context)

    # If statistical detection found something, return it
    # (Claude would add color but isn't worth the latency for anomaly checks)
    return stat_result


def synthesize_signals(
    current_price: float,
    signals: list[dict],
    regime: str = "NORMAL",
    momentum_signal: str = "NORMAL",
) -> AISignalSynthesis:
    """Synthesize multiple prediction signals into a unified view."""
    context = {
        "current_price": current_price,
        "signals": signals,
        "regime": regime,
        "momentum_signal": momentum_signal,
    }
    return _fallback.synthesize_signals(context)


def assess_risk(
    current_price: float,
    predicted_price: float,
    change_pct: float,
    days_to_checkin: int,
    scan_count: int = 0,
    regime: str = "NORMAL",
    quality_score: float = 0.5,
) -> AIRiskAssessment:
    """Assess risk for a trading position."""
    context = {
        "current_price": current_price,
        "predicted_price": predicted_price,
        "change_pct": change_pct,
        "days_to_checkin": days_to_checkin,
        "scan_count": scan_count,
        "regime": regime,
        "quality_score": quality_score,
    }
    return _fallback.assess_risk(context)


def get_bayesian_tracker() -> BayesianConfidence:
    """Get the global Bayesian confidence tracker."""
    return _bayesian


def update_bayesian_from_outcome(
    source: str,
    predicted_direction: str,
    actual_direction: str,
    magnitude_accuracy: float = 0.5,
) -> None:
    """Update Bayesian beliefs from observed outcome.

    Called when we see the actual price change and can compare to prediction.
    """
    direction_correct = (predicted_direction == actual_direction)
    weight = 0.5 + 0.5 * magnitude_accuracy  # Higher weight for accurate magnitude
    _bayesian.update(source, direction_correct, weight)


# ---------------------------------------------------------------------------
# Batch analysis — called from the analysis pipeline
# ---------------------------------------------------------------------------
def enrich_prediction(prediction: dict, context: dict) -> dict:
    """Enrich a single prediction dict with AI intelligence.

    This is the main integration point — called for each row in the
    options view to add AI-generated fields.

    Args:
        prediction: The existing prediction dict from deep_predictor
        context: Additional context (events, momentum, regime, scans, etc.)

    Returns:
        The prediction dict with added ai_* fields
    """
    current = context.get("current_price", 0)
    predicted = prediction.get("predicted_checkin_price", current)
    change = prediction.get("change_pct", 0)
    days = context.get("days_to_checkin", 0)

    # 1. Anomaly detection (always runs — fast, statistical)
    anomaly = detect_anomaly(
        hotel_name=context.get("hotel_name", ""),
        current_price=current,
        predicted_price=predicted,
        change_pct=change,
        scan_prices=context.get("scan_prices", []),
        regime=context.get("regime", "NORMAL"),
    )

    # 2. Signal synthesis
    signals = []
    for src_key in ["fc", "hist", "ml"]:
        p = prediction.get(f"{src_key}_price")
        if p is not None:
            signals.append({
                "source": {"fc": "forward_curve", "hist": "historical_pattern", "ml": "ml_forecast"}.get(src_key, src_key),
                "predicted_price": p,
                "weight": prediction.get(f"{src_key}_weight", 0),
                "confidence": prediction.get(f"{src_key}_confidence", 0),
            })
    synthesis = synthesize_signals(
        current_price=current,
        signals=signals,
        regime=context.get("regime", "NORMAL"),
        momentum_signal=context.get("momentum_signal", "NORMAL"),
    )

    # 3. Risk assessment
    risk = assess_risk(
        current_price=current,
        predicted_price=predicted,
        change_pct=change,
        days_to_checkin=days,
        scan_count=context.get("scan_count", 0),
        regime=context.get("regime", "NORMAL"),
        quality_score=context.get("quality_score", 0.5),
    )

    # 4. Bayesian weight adjustment
    bayesian_weights = _bayesian.get_adjusted_weights({
        "forward_curve": 0.50,
        "historical_pattern": 0.30,
        "ml_forecast": 0.20,
    })

    # Attach to prediction
    prediction["ai_anomaly"] = anomaly.to_dict()
    prediction["ai_synthesis"] = synthesis.to_dict()
    prediction["ai_risk"] = risk.to_dict()
    prediction["ai_bayesian_weights"] = bayesian_weights
    prediction["ai_conviction"] = synthesis.overall_conviction

    return prediction


def generate_ai_insights_batch(rows: list[dict]) -> dict:
    """Generate aggregate AI insights for the full options batch.

    Returns a high-level market summary and alerts.
    """
    if not rows:
        return {"market_summary": "No data available", "alerts": [], "stats": {}}

    calls = sum(1 for r in rows if r.get("signal") == "CALL")
    puts = sum(1 for r in rows if r.get("signal") == "PUT")
    neutrals = len(rows) - calls - puts

    # Aggregate anomalies
    anomalies = [r for r in rows if r.get("ai_anomaly", {}).get("is_anomaly")]
    high_risk = [r for r in rows if r.get("ai_risk", {}).get("risk_level") in ("high", "extreme")]

    # Price momentum aggregate
    changes = [r.get("change_pct", 0) for r in rows if r.get("change_pct") is not None]
    avg_change = sum(changes) / len(changes) if changes else 0
    bullish_pct = sum(1 for c in changes if c > 1) / len(changes) * 100 if changes else 0

    market_tone = "BULLISH" if bullish_pct > 60 else "BEARISH" if bullish_pct < 40 else "MIXED"

    alerts = []
    if len(anomalies) > 5:
        alerts.append({
            "type": "ANOMALY_CLUSTER",
            "severity": "high",
            "message": f"{len(anomalies)} pricing anomalies detected — review flagged rooms",
        })
    if len(high_risk) > len(rows) * 0.2:
        alerts.append({
            "type": "HIGH_RISK_CLUSTER",
            "severity": "medium",
            "message": f"{len(high_risk)} high-risk positions ({len(high_risk)/len(rows)*100:.0f}% of portfolio)",
        })
    if abs(avg_change) > 30:
        alerts.append({
            "type": "EXTREME_MARKET_MOVE",
            "severity": "high",
            "message": f"Average predicted change is {avg_change:+.1f}% — unusually large market move",
        })

    return {
        "market_summary": (
            f"Market tone: {market_tone}. "
            f"{calls} CALL / {puts} PUT / {neutrals} NEUTRAL signals across {len(rows)} rooms. "
            f"Average predicted change: {avg_change:+.1f}%. "
            f"{len(anomalies)} anomalies detected, {len(high_risk)} high-risk positions."
        ),
        "market_tone": market_tone,
        "alerts": alerts,
        "stats": {
            "total_rooms": len(rows),
            "calls": calls,
            "puts": puts,
            "neutrals": neutrals,
            "avg_change_pct": round(avg_change, 2),
            "bullish_pct": round(bullish_pct, 1),
            "anomaly_count": len(anomalies),
            "high_risk_count": len(high_risk),
        },
        "bayesian_state": _bayesian.to_dict(),
    }
