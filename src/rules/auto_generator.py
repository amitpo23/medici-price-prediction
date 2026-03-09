"""Auto-generate pricing rules from Forward Curve predictions.

The predictor's intelligence feeds into actionable rules:
  - Predicted price drop  → target_price (wait for cheaper entry)
  - Predicted price rise  → markup_pct (capture margin)
  - High volatility       → price_ceiling (cap risk)
  - Strong demand         → markup_pct (market will bear more)
  - Seasonal peak         → markup_pct (peak pricing)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Optional

from src.rules.models import PricingRuleCreate, RuleSource, RuleType
from src.rules.store import RulesStore

logger = logging.getLogger(__name__)


class RulesAutoGenerator:
    """Generate pricing rules automatically from Forward Curve and market data."""

    def __init__(self, store: Optional[RulesStore] = None):
        self._store = store or RulesStore()

    def generate_from_forward_curve(
        self,
        hotel_id: int,
        current_price: float,
        forward_points: list[dict],
        deactivate_old: bool = True,
    ) -> list[dict]:
        """Generate rules from a forward curve prediction.

        Args:
            hotel_id: Target hotel.
            current_price:  Current market price (from latest scan).
            forward_points: List of dicts with keys:
                - predicted_price, t, cumulative_change_pct,
                  volatility_at_t, demand_adj_pct, event_adj_pct,
                  season_adj_pct, momentum_adj_pct
            deactivate_old: If True, deactivate previous auto_fc rules first.

        Returns:
            List of created rule summaries.
        """
        if not forward_points or current_price <= 0:
            return []

        if deactivate_old:
            self._store.deactivate_hotel_rules(
                hotel_id, source=RuleSource.AUTO_FC.value,
            )

        rules_to_create: list[PricingRuleCreate] = []
        now_str = datetime.now(timezone.utc).isoformat()

        # ── Analysis: next 7 days and full horizon ───────────────
        short_term = forward_points[:7]   # next 7 days
        full = forward_points

        if not short_term:
            return []

        min_price_pt = min(full, key=lambda p: p.get("predicted_price", 9999))
        max_price_short = max(short_term, key=lambda p: p.get("predicted_price", 0))
        min_price = min_price_pt.get("predicted_price", current_price)
        max_price = max_price_short.get("predicted_price", current_price)

        avg_vol = mean(p.get("volatility_at_t", 0) for p in short_term)
        avg_demand = mean(p.get("demand_adj_pct", 0) for p in short_term)
        avg_event = mean(p.get("event_adj_pct", 0) for p in short_term)
        avg_season = mean(p.get("season_adj_pct", 0) for p in short_term)
        avg_momentum = mean(p.get("momentum_adj_pct", 0) for p in short_term)

        min_change_pct = (min_price / current_price - 1) * 100 if current_price > 0 else 0
        max_change_pct = (max_price / current_price - 1) * 100 if current_price > 0 else 0

        # ── Rule 1: Price predicted to DROP > 5% → target_price ──
        if min_change_pct < -5.0:
            target = round(min_price * 1.01, 2)  # target slightly above predicted min
            t_min = min_price_pt.get("t", 7)
            expires = datetime.now(timezone.utc) + timedelta(days=max(t_min, 3))

            rules_to_create.append(PricingRuleCreate(
                hotel_id=hotel_id,
                rule_type=RuleType.TARGET_PRICE,
                rule_value=target,
                priority=80,
                source=RuleSource.AUTO_FC,
                reason=f"FC predicts {min_change_pct:.1f}% drop to ${min_price:.2f} by T={t_min}",
                confidence=min(0.9, 0.6 + abs(min_change_pct) / 50),
                expires_at=expires.isoformat(),
                created_by="auto_fc",
            ))

        # ── Rule 2: Price predicted to RISE > 3% → markup_pct ───
        if max_change_pct > 3.0:
            # Capture some of the predicted upside
            markup = min(round((max_change_pct / 2), 1), 10.0)  # half the predicted rise, max 10%
            markup = max(markup, 2.0)  # minimum 2%

            rules_to_create.append(PricingRuleCreate(
                hotel_id=hotel_id,
                rule_type=RuleType.MARKUP_PCT,
                rule_value=markup,
                priority=50,
                source=RuleSource.AUTO_FC,
                reason=f"FC predicts {max_change_pct:.1f}% rise — capture {markup:.1f}% margin",
                confidence=min(0.85, 0.5 + max_change_pct / 30),
                expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                created_by="auto_fc",
            ))

        # ── Rule 3: High volatility → conservative price_ceiling ─
        if avg_vol > 3.0:
            ceiling = round(current_price * (1 + min(avg_vol, 15) / 100), 2)
            rules_to_create.append(PricingRuleCreate(
                hotel_id=hotel_id,
                rule_type=RuleType.PRICE_CEILING,
                rule_value=ceiling,
                priority=70,
                source=RuleSource.AUTO_FC,
                reason=f"High volatility ({avg_vol:.1f}%/day) — cap risk at ${ceiling:.0f}",
                confidence=0.7,
                expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                created_by="auto_fc",
            ))

        # ── Rule 4: Strong demand signal → increase markup ───────
        if avg_demand > 0.10:
            demand_markup = max(3.0, round(avg_demand * 15, 1))
            demand_markup = min(demand_markup, 12.0)

            rules_to_create.append(PricingRuleCreate(
                hotel_id=hotel_id,
                rule_type=RuleType.MARKUP_PCT,
                rule_value=demand_markup,
                priority=60,
                source=RuleSource.AUTO_FC,
                reason=f"Strong demand signal ({avg_demand:.2f}%/day) — market can bear {demand_markup:.1f}%",
                confidence=min(0.8, 0.5 + avg_demand),
                expires_at=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
                created_by="auto_fc",
            ))

        # ── Rule 5: Strong event effect → markup boost ───────────
        if avg_event > 0.15:
            event_markup = max(4.0, round(avg_event * 10, 1))
            event_markup = min(event_markup, 15.0)

            rules_to_create.append(PricingRuleCreate(
                hotel_id=hotel_id,
                rule_type=RuleType.MARKUP_PCT,
                rule_value=event_markup,
                priority=65,
                source=RuleSource.AUTO_FC,
                reason=f"Event boost ({avg_event:.2f}%/day) — premium pricing",
                confidence=0.75,
                expires_at=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
                created_by="auto_fc",
            ))

        # ── Rule 6: Seasonal high → markup ───────────────────────
        if avg_season > 0.10:
            season_markup = max(3.0, round(avg_season * 8, 1))
            season_markup = min(season_markup, 10.0)

            rules_to_create.append(PricingRuleCreate(
                hotel_id=hotel_id,
                rule_type=RuleType.MARKUP_PCT,
                rule_value=season_markup,
                priority=45,
                source=RuleSource.AUTO_FC,
                reason=f"Seasonal uptrend ({avg_season:.2f}%/day)",
                confidence=0.65,
                expires_at=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                created_by="auto_fc",
            ))

        # ── Rule 7: Strong negative momentum → hold ─────────────
        if avg_momentum < -0.20:
            hold_target = round(current_price * (1 + avg_momentum / 20), 2)
            hold_target = max(hold_target, current_price * 0.85)  # cap at -15%

            rules_to_create.append(PricingRuleCreate(
                hotel_id=hotel_id,
                rule_type=RuleType.HOLD_UNTIL_DROP,
                rule_value=hold_target,
                priority=90,
                source=RuleSource.AUTO_FC,
                reason=f"Negative momentum ({avg_momentum:.2f}%/day) — wait for ${hold_target:.2f}",
                confidence=min(0.8, 0.5 + abs(avg_momentum)),
                expires_at=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
                created_by="auto_fc",
            ))

        # ── Create all rules in DB ───────────────────────────────
        created = []
        for rule_data in rules_to_create:
            try:
                result = self._store.create_rule(rule_data)
                created.append({
                    "rule_id": result.id,
                    "type": result.rule_type,
                    "value": result.rule_value,
                    "reason": result.reason,
                    "confidence": result.confidence,
                })
            except (ValueError, TypeError, KeyError, OSError) as e:
                logger.error("Failed to create rule: %s", e, exc_info=True)

        logger.info(
            "Auto-generated %d rules for hotel %d from FC (price=%.2f, "
            "min_chg=%.1f%%, max_chg=%.1f%%, vol=%.1f)",
            len(created), hotel_id, current_price,
            min_change_pct, max_change_pct, avg_vol,
        )

        return created

    def generate_for_all_hotels(self, analyses: list[dict]) -> dict:
        """Batch auto-generate rules for multiple hotels.

        Args:
            analyses: List of dicts with keys:
                - hotel_id, current_price, forward_points

        Returns:
            Summary: {total_hotels, total_rules, by_hotel: {...}}
        """
        summary = {
            "total_hotels": 0,
            "total_rules": 0,
            "by_hotel": {},
        }

        for a in analyses:
            hotel_id = a.get("hotel_id")
            price = a.get("current_price", 0)
            points = a.get("forward_points", [])

            if not hotel_id or not points:
                continue

            created = self.generate_from_forward_curve(
                hotel_id=hotel_id,
                current_price=price,
                forward_points=points,
            )

            summary["total_hotels"] += 1
            summary["total_rules"] += len(created)
            summary["by_hotel"][hotel_id] = created

        return summary
