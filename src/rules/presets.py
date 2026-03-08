"""Built-in preset templates for common pricing strategies.

Each preset is a named collection of rule templates that can be
applied to any hotel with one click.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from src.rules.store import RulesStore

logger = logging.getLogger(__name__)

# ── Preset definitions ───────────────────────────────────────────────

BUILTIN_PRESETS = {
    "conservative": {
        "description": "Play it safe — minimal markup, tight ceiling. Best for new/unknown hotels.",
        "rules": [
            {
                "rule_type": "markup_fixed",
                "rule_value": 0.01,
                "priority": 50,
                "confidence": 0.9,
            },
            {
                "rule_type": "price_ceiling",
                "rule_value": 1.10,      # multiplier — applied as current_price × value
                "priority": 70,
                "confidence": 0.9,
            },
        ],
    },
    "moderate": {
        "description": "Balanced risk/reward — 3% markup, reasonable ceiling.",
        "rules": [
            {
                "rule_type": "markup_pct",
                "rule_value": 3.0,
                "priority": 50,
                "confidence": 0.7,
            },
            {
                "rule_type": "price_ceiling",
                "rule_value": 1.20,
                "priority": 70,
                "confidence": 0.7,
            },
        ],
    },
    "aggressive": {
        "description": "Maximum margin capture — 5-8% markup, wide ceiling. For high-demand hotels.",
        "rules": [
            {
                "rule_type": "markup_pct",
                "rule_value": 6.0,
                "priority": 50,
                "confidence": 0.6,
            },
            {
                "rule_type": "price_ceiling",
                "rule_value": 1.30,
                "priority": 70,
                "confidence": 0.6,
            },
        ],
    },
    "seasonal_high": {
        "description": "Peak season pricing — strong demand expected, premium markup.",
        "rules": [
            {
                "rule_type": "markup_pct",
                "rule_value": 10.0,
                "priority": 55,
                "confidence": 0.65,
            },
        ],
    },
    "fire_sale": {
        "description": "Grab cheap inventory — tight ceiling, $0.01 markup. Buy everything below ceiling.",
        "rules": [
            {
                "rule_type": "markup_fixed",
                "rule_value": 0.01,
                "priority": 50,
                "confidence": 0.85,
            },
            {
                "rule_type": "price_ceiling",
                "rule_value": 1.05,
                "priority": 70,
                "confidence": 0.85,
            },
        ],
    },
    "wait_for_drop": {
        "description": "Don't buy yet — Forward Curve predicts a price decline. Hold and wait.",
        "rules": [
            {
                "rule_type": "hold_until_drop",
                "rule_value": 1.0,        # flag — actual target comes from target_price
                "priority": 90,
                "confidence": 0.7,
            },
        ],
    },
    "exclude_ai": {
        "description": "Exclude All-Inclusive board type — typically low margin.",
        "rules": [
            {
                "rule_type": "exclude_board",
                "rule_value": 0,
                "rule_text": "AI",
                "priority": 80,
                "confidence": 0.9,
            },
        ],
    },
}


def install_builtin_presets(store: Optional[RulesStore] = None) -> dict:
    """Save all built-in presets to the database.

    Safe to call multiple times — existing presets are updated.

    Returns:
        Summary of created/updated presets.
    """
    store = store or RulesStore()
    results = {}

    for name, cfg in BUILTIN_PRESETS.items():
        # For presets that use multipliers (price_ceiling as 1.10),
        # mark them so the apply logic knows to multiply by current price
        rules_json = json.dumps(cfg["rules"])
        result = store.save_preset(
            name=name,
            description=cfg["description"],
            rules_json=rules_json,
            is_default=(name == "moderate"),
        )
        results[name] = result

    logger.info("Installed %d built-in presets", len(results))
    return results


def apply_preset_to_hotel(
    preset_name: str,
    hotel_id: int,
    current_price: float = 0.0,
    store: Optional[RulesStore] = None,
) -> list[dict]:
    """Apply a named preset to a hotel.

    For ceiling rules with multiplier values (like 1.20),
    converts to absolute price using current_price.

    Args:
        preset_name: Name of the preset (e.g., 'aggressive').
        hotel_id: Target hotel.
        current_price: Current market price for ceiling calculations.
        store: Optional RulesStore instance.

    Returns:
        List of created rule summaries.
    """
    preset_cfg = BUILTIN_PRESETS.get(preset_name)
    if not preset_cfg:
        return []

    store = store or RulesStore()

    # Deactivate old preset rules for this hotel
    store.deactivate_hotel_rules(hotel_id, source="preset")

    from src.rules.models import PricingRuleCreate, RuleSource, RuleType

    created = []
    for rd in preset_cfg["rules"]:
        rule_value = rd.get("rule_value", 0)

        # Convert ceiling multipliers to absolute values
        if rd.get("rule_type") == "price_ceiling" and rule_value < 10 and current_price > 0:
            rule_value = round(current_price * rule_value, 2)

        rule = PricingRuleCreate(
            hotel_id=hotel_id,
            rule_type=rd.get("rule_type", "markup_pct"),
            rule_value=rule_value,
            rule_text=rd.get("rule_text"),
            priority=rd.get("priority", 0),
            source=RuleSource.PRESET,
            reason=f"Preset: {preset_name}",
            confidence=rd.get("confidence"),
            created_by="preset",
        )
        result = store.create_rule(rule)
        created.append({
            "rule_id": result.id,
            "type": result.rule_type,
            "value": result.rule_value,
            "preset": preset_name,
        })

    logger.info("Applied preset '%s' to hotel %d: %d rules", preset_name, hotel_id, len(created))
    return created
