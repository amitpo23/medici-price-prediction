"""Rules Application Engine — the core pipeline.

Called by the WebJob at Step 5 to decide:
  - ACCEPT / REJECT / MODIFY for each room
  - What price to push to Zenith

Pipeline order:
  1. hold_until_drop    → REJECT if waiting for drop
  2. exclude_category   → REJECT if category blacklisted
  3. exclude_board      → REJECT if board blacklisted
  4. price_ceiling      → REJECT if price too high
  5. target_price       → REJECT if price above target
  6. max_rooms          → REJECT if at room limit
  7. markup (pct/fixed) → MODIFY price with markup
  8. price_floor        → ensure price ≥ floor
  9. auto_close         → REJECT if above threshold
"""
from __future__ import annotations

import logging
from typing import Optional

from src.rules.models import (
    PricingRuleORM,
    RuleAction,
    RuleApplyResult,
    RuleType,
)
from src.rules.store import RulesStore

logger = logging.getLogger(__name__)

# Default markup when no markup rule exists (original SalesOffice behaviour)
_DEFAULT_MARKUP = 0.01


class RulesEngine:
    """Evaluate pricing rules for a hotel room and return an action."""

    def __init__(self, store: Optional[RulesStore] = None):
        self._store = store or RulesStore()

    # ── Main entry point ─────────────────────────────────────────

    def apply(
        self,
        hotel_id: int,
        price: float,
        category: str = "",
        board: str = "",
    ) -> RuleApplyResult:
        """Apply all active rules for a hotel to a room price.

        This is what the WebJob calls at Step 5.

        Args:
            hotel_id: Hotel ID from the scan.
            price: Cheapest price found (MinBy result).
            category: Room category (standard, deluxe, etc.).
            board: Board type (RO, BB, HB, AI, etc.).

        Returns:
            RuleApplyResult with action (ACCEPT/REJECT/MODIFY)
            and the adjusted price to push to Zenith.
        """
        rules = self._store.get_active_rules_raw(hotel_id)

        if not rules:
            # No rules → default behaviour: ACCEPT with $0.01 markup
            return RuleApplyResult(
                hotel_id=hotel_id,
                original_price=price,
                action=RuleAction.ACCEPT,
                adjusted_price=round(price + _DEFAULT_MARKUP, 2),
                markup_applied=_DEFAULT_MARKUP,
                rules_applied=[],
                reason="No rules configured — default $0.01 markup",
            )

        # Sort by priority (highest first)
        rules.sort(key=lambda r: r.priority, reverse=True)

        # Filter rules that match this room
        applicable = self._filter_applicable(rules, category, board)

        if not applicable:
            return RuleApplyResult(
                hotel_id=hotel_id,
                original_price=price,
                action=RuleAction.ACCEPT,
                adjusted_price=round(price + _DEFAULT_MARKUP, 2),
                markup_applied=_DEFAULT_MARKUP,
                rules_applied=[],
                reason="No matching rules for this room — default $0.01 markup",
            )

        # Run the pipeline
        return self._run_pipeline(hotel_id, price, category, board, applicable)

    def apply_batch(
        self,
        rooms: list[dict],
    ) -> list[RuleApplyResult]:
        """Apply rules to multiple rooms at once.

        Args:
            rooms: List of dicts with keys: hotel_id, price, category, board.

        Returns:
            List of RuleApplyResult, one per room.
        """
        return [
            self.apply(
                hotel_id=r["hotel_id"],
                price=r["price"],
                category=r.get("category", ""),
                board=r.get("board", ""),
            )
            for r in rooms
        ]

    # ── Pipeline steps ───────────────────────────────────────────

    def _run_pipeline(
        self,
        hotel_id: int,
        price: float,
        category: str,
        board: str,
        rules: list[PricingRuleORM],
    ) -> RuleApplyResult:
        """Execute the rules pipeline in order."""
        applied = []
        adjusted_price = price
        total_confidence = []

        # Group rules by type for efficient lookup
        by_type: dict[str, list[PricingRuleORM]] = {}
        for r in rules:
            by_type.setdefault(r.rule_type, []).append(r)

        # ── Step 1: hold_until_drop ──────────────────────────────
        hold_rules = by_type.get(RuleType.HOLD_UNTIL_DROP.value, [])
        for r in hold_rules:
            if r.rule_value > 0:
                applied.append(self._rule_dict(r, "REJECTED: waiting for price drop"))
                if r.confidence:
                    total_confidence.append(r.confidence)
                self._log_apply(r, hotel_id, price, price)
                return RuleApplyResult(
                    hotel_id=hotel_id,
                    original_price=price,
                    action=RuleAction.HOLD,
                    adjusted_price=price,
                    rules_applied=applied,
                    reason=f"Hold: waiting for drop to ≤${r.rule_value:.2f} ({r.reason or ''})",
                    confidence=self._avg_confidence(total_confidence),
                )

        # ── Step 2: exclude_category ─────────────────────────────
        cat_rules = by_type.get(RuleType.EXCLUDE_CATEGORY.value, [])
        for r in cat_rules:
            excluded = (r.rule_text or "").lower()
            if excluded and category.lower() == excluded:
                applied.append(self._rule_dict(r, f"REJECTED: category '{category}' excluded"))
                self._log_apply(r, hotel_id, price, price)
                return RuleApplyResult(
                    hotel_id=hotel_id,
                    original_price=price,
                    action=RuleAction.REJECT,
                    adjusted_price=price,
                    rules_applied=applied,
                    reason=f"Category '{category}' excluded by rule",
                    confidence=r.confidence,
                )

        # ── Step 3: exclude_board ────────────────────────────────
        board_rules = by_type.get(RuleType.EXCLUDE_BOARD.value, [])
        for r in board_rules:
            excluded = (r.rule_text or "").lower()
            if excluded and board.lower() == excluded:
                applied.append(self._rule_dict(r, f"REJECTED: board '{board}' excluded"))
                self._log_apply(r, hotel_id, price, price)
                return RuleApplyResult(
                    hotel_id=hotel_id,
                    original_price=price,
                    action=RuleAction.REJECT,
                    adjusted_price=price,
                    rules_applied=applied,
                    reason=f"Board '{board}' excluded by rule",
                    confidence=r.confidence,
                )

        # ── Step 4: price_ceiling ────────────────────────────────
        ceiling_rules = by_type.get(RuleType.PRICE_CEILING.value, [])
        for r in ceiling_rules:
            if price > r.rule_value:
                applied.append(self._rule_dict(r, f"REJECTED: ${price:.2f} > ceiling ${r.rule_value:.2f}"))
                self._log_apply(r, hotel_id, price, price)
                return RuleApplyResult(
                    hotel_id=hotel_id,
                    original_price=price,
                    action=RuleAction.REJECT,
                    adjusted_price=price,
                    rules_applied=applied,
                    reason=f"Price ${price:.2f} exceeds ceiling ${r.rule_value:.2f}",
                    confidence=r.confidence,
                )
            if r.confidence:
                total_confidence.append(r.confidence)

        # ── Step 5: target_price ─────────────────────────────────
        target_rules = by_type.get(RuleType.TARGET_PRICE.value, [])
        for r in target_rules:
            if price > r.rule_value:
                applied.append(self._rule_dict(r, f"REJECTED: ${price:.2f} > target ${r.rule_value:.2f}"))
                self._log_apply(r, hotel_id, price, price)
                return RuleApplyResult(
                    hotel_id=hotel_id,
                    original_price=price,
                    action=RuleAction.REJECT,
                    adjusted_price=price,
                    rules_applied=applied,
                    reason=f"Price ${price:.2f} above target ${r.rule_value:.2f} — waiting for drop",
                    confidence=r.confidence,
                )
            else:
                applied.append(self._rule_dict(r, f"PASSED: ${price:.2f} ≤ target ${r.rule_value:.2f}"))
            if r.confidence:
                total_confidence.append(r.confidence)

        # ── Step 6: max_rooms ────────────────────────────────────
        max_rules = by_type.get(RuleType.MAX_ROOMS.value, [])
        for r in max_rules:
            # max_rooms check — would need active room count from DB
            # For now, store the rule; actual enforcement needs room count
            applied.append(self._rule_dict(r, f"max_rooms={int(r.rule_value)} (advisory)"))
            if r.confidence:
                total_confidence.append(r.confidence)

        # ── Step 7: markup ───────────────────────────────────────
        markup_applied = False
        markup_amount = 0.0

        pct_rules = by_type.get(RuleType.MARKUP_PCT.value, [])
        fixed_rules = by_type.get(RuleType.MARKUP_FIXED.value, [])

        if pct_rules:
            # Use highest-priority pct rule
            r = pct_rules[0]
            markup_amount = round(adjusted_price * (r.rule_value / 100.0), 2)
            adjusted_price = round(adjusted_price + markup_amount, 2)
            applied.append(self._rule_dict(r, f"markup {r.rule_value}% → +${markup_amount:.2f}"))
            markup_applied = True
            if r.confidence:
                total_confidence.append(r.confidence)
        elif fixed_rules:
            r = fixed_rules[0]
            markup_amount = r.rule_value
            adjusted_price = round(adjusted_price + markup_amount, 2)
            applied.append(self._rule_dict(r, f"markup fixed +${markup_amount:.2f}"))
            markup_applied = True
            if r.confidence:
                total_confidence.append(r.confidence)

        if not markup_applied:
            # Default $0.01 markup
            markup_amount = _DEFAULT_MARKUP
            adjusted_price = round(adjusted_price + _DEFAULT_MARKUP, 2)

        # ── Step 8: price_floor ──────────────────────────────────
        floor_rules = by_type.get(RuleType.PRICE_FLOOR.value, [])
        for r in floor_rules:
            if adjusted_price < r.rule_value:
                old_adj = adjusted_price
                adjusted_price = r.rule_value
                markup_amount = round(adjusted_price - price, 2)
                applied.append(self._rule_dict(
                    r, f"floor: ${old_adj:.2f} → ${r.rule_value:.2f}",
                ))
            if r.confidence:
                total_confidence.append(r.confidence)

        # ── Step 9: auto_close_threshold ─────────────────────────
        close_rules = by_type.get(RuleType.AUTO_CLOSE_THRESHOLD.value, [])
        for r in close_rules:
            if adjusted_price > r.rule_value:
                applied.append(self._rule_dict(
                    r, f"REJECTED: adjusted ${adjusted_price:.2f} > close threshold ${r.rule_value:.2f}",
                ))
                self._log_apply(r, hotel_id, price, adjusted_price)
                return RuleApplyResult(
                    hotel_id=hotel_id,
                    original_price=price,
                    action=RuleAction.REJECT,
                    adjusted_price=price,
                    rules_applied=applied,
                    reason=f"Adjusted price ${adjusted_price:.2f} exceeds auto-close threshold ${r.rule_value:.2f}",
                    confidence=r.confidence,
                )

        # ── Preferred category (info only) ───────────────────────
        pref_rules = by_type.get(RuleType.PREFERRED_CATEGORY.value, [])
        for r in pref_rules:
            preferred = (r.rule_text or "").lower()
            if preferred and category.lower() == preferred:
                applied.append(self._rule_dict(r, f"preferred category match ✓"))
            elif preferred:
                applied.append(self._rule_dict(r, f"not preferred (want '{preferred}')"))

        # ── Final result ─────────────────────────────────────────
        action = RuleAction.MODIFY if markup_applied else RuleAction.ACCEPT

        # Log the application
        for r_dict in applied:
            if r_dict.get("rule_id"):
                try:
                    self._store.log_application(
                        rule_id=r_dict["rule_id"],
                        hotel_id=hotel_id,
                        applied_to_price=price,
                        result_price=adjusted_price,
                        details=r_dict.get("effect", ""),
                    )
                except Exception:
                    pass

        return RuleApplyResult(
            hotel_id=hotel_id,
            original_price=price,
            action=action,
            adjusted_price=adjusted_price,
            markup_applied=round(markup_amount, 2),
            rules_applied=applied,
            reason=f"{len(applied)} rules applied → ${price:.2f} → ${adjusted_price:.2f}",
            confidence=self._avg_confidence(total_confidence),
        )

    # ── Helpers ──────────────────────────────────────────────────

    def _filter_applicable(
        self,
        rules: list[PricingRuleORM],
        category: str,
        board: str,
    ) -> list[PricingRuleORM]:
        """Filter rules to those matching this room's category/board."""
        result = []
        cat_lower = category.lower() if category else ""
        board_lower = board.lower() if board else ""

        for r in rules:
            # rule_category=NULL means applies to all
            if r.room_category and r.room_category.lower() != cat_lower:
                continue
            # rule_board=NULL means applies to all
            if r.room_board and r.room_board.lower() != board_lower:
                continue
            result.append(r)

        return result

    @staticmethod
    def _rule_dict(r: PricingRuleORM, effect: str) -> dict:
        """Convert a rule + its effect to a summary dict."""
        return {
            "rule_id": r.id,
            "rule_type": r.rule_type,
            "rule_value": r.rule_value,
            "rule_text": r.rule_text,
            "source": r.source,
            "reason": r.reason or "",
            "effect": effect,
        }

    def _log_apply(self, r: PricingRuleORM, hotel_id: int,
                   input_price: float, result_price: float) -> None:
        """Log a single rule application."""
        try:
            self._store.log_application(
                rule_id=r.id,
                hotel_id=hotel_id,
                applied_to_price=input_price,
                result_price=result_price,
                details=f"type={r.rule_type}",
            )
        except Exception:
            pass

    @staticmethod
    def _avg_confidence(confidences: list[float]) -> Optional[float]:
        """Average confidence from multiple rules."""
        if not confidences:
            return None
        return round(sum(confidences) / len(confidences), 3)

    # ── Preview (dry-run) ────────────────────────────────────────

    def preview(self, hotel_id: int, prices: list[dict]) -> list[RuleApplyResult]:
        """Preview what would happen with current rules.

        Args:
            prices: List of dicts with price/category/board from recent scans.

        Returns:
            List of RuleApplyResult showing hypothetical outcomes.
        """
        return [
            self.apply(
                hotel_id=hotel_id,
                price=p.get("price", 0),
                category=p.get("category", ""),
                board=p.get("board", ""),
            )
            for p in prices
        ]
