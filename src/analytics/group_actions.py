"""Group Actions — bulk CALL/PUT execution with flexible filtering.

Allows operators to execute actions on groups of rooms filtered by:
  - signal (CALL / PUT / all)
  - hotel_id (specific hotel or all)
  - category (standard / deluxe / suite / all)
  - board (ro / bb / all)
  - confidence (High / Med / Low)
  - T range (min/max days to check-in)

This module is the Decision Brain's bulk action coordinator.
It NEVER executes trades directly — it queues to SQLite for external skills.

Architecture:
  1. Filter signals from cached analysis using GroupFilter
  2. Validate each room against guardrails
  3. Queue to opportunity_queue.db (CALL) or override_queue.db (PUT)
  4. Return batch summary with batch_id for tracking
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Safety caps
MAX_GROUP_SIZE = 200          # Max rooms in a single group action
MIN_T_DAYS = 1                # Don't act on rooms checking in tomorrow


@dataclass
class GroupFilter:
    """Filter criteria for selecting rooms."""
    signal: str | None = None           # "CALL", "PUT", or None for both
    hotel_id: int | None = None         # Specific hotel or None for all
    hotel_ids: list[int] | None = None  # Multiple hotels
    category: str | None = None         # "standard", "deluxe", "suite"
    board: str | None = None            # "ro", "bb"
    confidence: str | None = None       # "High", "Med", "Low"
    min_T: int | None = None            # Minimum days to check-in
    max_T: int | None = None            # Maximum days to check-in
    min_price: float | None = None      # Minimum current price
    max_price: float | None = None      # Maximum current price

    def describe(self) -> str:
        """Human-readable description of the filter."""
        parts = []
        if self.signal:
            parts.append(f"signal={self.signal}")
        if self.hotel_id:
            parts.append(f"hotel={self.hotel_id}")
        if self.hotel_ids:
            parts.append(f"hotels={self.hotel_ids}")
        if self.category:
            parts.append(f"category={self.category}")
        if self.board:
            parts.append(f"board={self.board}")
        if self.confidence:
            parts.append(f"confidence={self.confidence}")
        if self.min_T is not None or self.max_T is not None:
            parts.append(f"T=[{self.min_T or '*'}..{self.max_T or '*'}]")
        if self.min_price is not None or self.max_price is not None:
            parts.append(f"price=[${self.min_price or '*'}..${self.max_price or '*'}]")
        return " & ".join(parts) or "all"


@dataclass
class GroupActionResult:
    """Result of a bulk group action."""
    batch_id: str
    action: str                     # "override" or "opportunity"
    filter_description: str
    total_matched: int              # How many rooms matched the filter
    total_queued: int               # How many were successfully queued
    total_skipped: int              # How many failed validation
    skipped_reasons: list[str]      # Why rooms were skipped
    hotel_breakdown: list[dict]     # Per-hotel counts
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


# ── Core: Filter signals ─────────────────────────────────────────────

def filter_signals(
    signals: list[dict],
    analysis: dict,
    gf: GroupFilter,
) -> list[dict]:
    """Apply GroupFilter to a list of option signals.

    Args:
        signals: Output of compute_next_day_signals(analysis)
        analysis: Full analysis dict with predictions
        gf: Filter criteria

    Returns:
        Filtered list of signal dicts matching ALL criteria.
    """
    predictions = analysis.get("predictions", {})
    result = []

    for sig in signals:
        # Signal filter
        rec = (sig.get("recommendation") or "").upper()
        if gf.signal:
            target_signals = _expand_signal(gf.signal)
            if rec not in target_signals:
                continue

        # Hotel filter
        hid = int(sig.get("hotel_id", 0) or 0)
        if gf.hotel_id is not None and hid != gf.hotel_id:
            continue
        if gf.hotel_ids and hid not in gf.hotel_ids:
            continue

        # Category filter
        if gf.category:
            cat = (sig.get("category") or "").lower()
            if cat != gf.category.lower():
                continue

        # Board filter
        if gf.board:
            board = (sig.get("board") or "").lower()
            if board != gf.board.lower():
                continue

        # Confidence filter
        if gf.confidence:
            conf = (sig.get("confidence") or "").lower()
            if conf != gf.confidence.lower():
                continue

        # T range filter
        T = int(sig.get("T", 0) or 0)
        if gf.min_T is not None and T < gf.min_T:
            continue
        if gf.max_T is not None and T > gf.max_T:
            continue

        # Price range filter
        price = float(sig.get("S_t", 0) or 0)
        if gf.min_price is not None and price < gf.min_price:
            continue
        if gf.max_price is not None and price > gf.max_price:
            continue

        # Minimum T safety
        if T < MIN_T_DAYS:
            continue

        result.append(sig)

    return result


def _expand_signal(signal: str) -> set[str]:
    """Expand a signal to include its strong variant."""
    s = signal.upper()
    if s == "CALL":
        return {"CALL", "STRONG_CALL"}
    elif s == "PUT":
        return {"PUT", "STRONG_PUT"}
    elif s == "NONE":
        return {"NONE"}
    return {s}


# ── Preview (dry-run) ────────────────────────────────────────────────

def preview_group_action(
    signals: list[dict],
    analysis: dict,
    gf: GroupFilter,
) -> dict:
    """Preview what a group action would do — without queuing anything.

    Returns summary with matched rooms, per-hotel breakdown, and estimates.
    """
    matched = filter_signals(signals, analysis, gf)
    predictions = analysis.get("predictions", {})

    hotel_counts: dict[int, dict] = {}
    total_value = 0.0

    for sig in matched:
        hid = int(sig.get("hotel_id", 0))
        hname = sig.get("hotel_name", "")
        price = float(sig.get("S_t", 0) or 0)
        rec = (sig.get("recommendation") or "").upper()

        if hid not in hotel_counts:
            hotel_counts[hid] = {
                "hotel_id": hid, "hotel_name": hname,
                "calls": 0, "puts": 0, "total": 0,
                "total_price": 0.0,
            }
        hotel_counts[hid]["total"] += 1
        hotel_counts[hid]["total_price"] += price
        if rec in ("CALL", "STRONG_CALL"):
            hotel_counts[hid]["calls"] += 1
        elif rec in ("PUT", "STRONG_PUT"):
            hotel_counts[hid]["puts"] += 1
        total_value += price

    return {
        "filter": gf.describe(),
        "total_matched": len(matched),
        "total_value_usd": round(total_value, 2),
        "exceeds_limit": len(matched) > MAX_GROUP_SIZE,
        "max_group_size": MAX_GROUP_SIZE,
        "hotel_breakdown": sorted(
            hotel_counts.values(),
            key=lambda h: h["total"],
            reverse=True,
        ),
        "matched_details": [
            {
                "detail_id": sig.get("detail_id"),
                "hotel_name": sig.get("hotel_name", ""),
                "category": sig.get("category", ""),
                "board": sig.get("board", ""),
                "T": sig.get("T", 0),
                "price": sig.get("S_t", 0),
                "signal": sig.get("recommendation", ""),
                "confidence": sig.get("confidence", ""),
            }
            for sig in matched[:50]  # Cap preview to 50 rows
        ],
    }


# ── Execute: Bulk Override (PUT) ─────────────────────────────────────

def execute_group_override(
    signals: list[dict],
    analysis: dict,
    gf: GroupFilter,
    discount_usd: float = 1.0,
) -> GroupActionResult:
    """Execute bulk PUT overrides for all rooms matching the filter.

    Forces signal filter to PUT/STRONG_PUT.
    """
    from src.analytics.override_queue import (
        enqueue_override,
        OverrideValidationError,
    )

    # Force PUT signal filter
    gf.signal = "PUT"
    matched = filter_signals(signals, analysis, gf)

    if len(matched) > MAX_GROUP_SIZE:
        return GroupActionResult(
            batch_id="",
            action="override",
            filter_description=gf.describe(),
            total_matched=len(matched),
            total_queued=0,
            total_skipped=len(matched),
            skipped_reasons=[f"Group size {len(matched)} exceeds limit {MAX_GROUP_SIZE}. Add more filters."],
            hotel_breakdown=[],
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    batch_id = f"GRP-OVR-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    predictions = analysis.get("predictions", {})
    queued = 0
    skipped = 0
    skip_reasons: list[str] = []
    hotel_counts: dict[int, dict] = {}

    for sig in matched:
        detail_id = int(sig.get("detail_id", 0))
        hid = int(sig.get("hotel_id", 0))
        hname = sig.get("hotel_name", "")
        price = float(sig.get("S_t", 0) or 0)
        pred = predictions.get(str(detail_id)) or {}

        if hid not in hotel_counts:
            hotel_counts[hid] = {"hotel_id": hid, "hotel_name": hname, "queued": 0, "skipped": 0}

        try:
            enqueue_override(
                detail_id=detail_id,
                hotel_id=hid,
                current_price=price,
                discount_usd=discount_usd,
                signal=str(sig.get("recommendation", "PUT")),
                confidence=str(sig.get("confidence", "")),
                hotel_name=hname,
                category=str(sig.get("category", "")),
                board=str(sig.get("board", "")),
                checkin_date=str(sig.get("checkin_date", "")),
                path_min_price=sig.get("path_min_price"),
                trigger_type="group_override",
                batch_id=batch_id,
            )
            queued += 1
            hotel_counts[hid]["queued"] += 1
        except (OverrideValidationError, ValueError) as exc:
            skipped += 1
            hotel_counts[hid]["skipped"] += 1
            reason = f"detail={detail_id}: {exc}"
            if len(skip_reasons) < 10:
                skip_reasons.append(reason)

    logger.info(
        "group_actions: override batch=%s filter=[%s] queued=%d skipped=%d discount=$%.2f",
        batch_id, gf.describe(), queued, skipped, discount_usd,
    )

    return GroupActionResult(
        batch_id=batch_id,
        action="override",
        filter_description=gf.describe(),
        total_matched=len(matched),
        total_queued=queued,
        total_skipped=skipped,
        skipped_reasons=skip_reasons,
        hotel_breakdown=sorted(hotel_counts.values(), key=lambda h: h["queued"], reverse=True),
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


# ── Execute: Bulk Opportunity (CALL) ─────────────────────────────────

def execute_group_opportunity(
    signals: list[dict],
    analysis: dict,
    gf: GroupFilter,
    max_rooms: int = 1,
) -> GroupActionResult:
    """Execute bulk CALL opportunities for all rooms matching the filter.

    Forces signal filter to CALL/STRONG_CALL.
    """
    from src.analytics.opportunity_queue import (
        enqueue_opportunity,
        OpportunityValidationError,
    )

    # Force CALL signal filter
    gf.signal = "CALL"
    matched = filter_signals(signals, analysis, gf)

    if len(matched) > MAX_GROUP_SIZE:
        return GroupActionResult(
            batch_id="",
            action="opportunity",
            filter_description=gf.describe(),
            total_matched=len(matched),
            total_queued=0,
            total_skipped=len(matched),
            skipped_reasons=[f"Group size {len(matched)} exceeds limit {MAX_GROUP_SIZE}. Add more filters."],
            hotel_breakdown=[],
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    batch_id = f"GRP-OPP-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    predictions = analysis.get("predictions", {})
    queued = 0
    skipped = 0
    skip_reasons: list[str] = []
    hotel_counts: dict[int, dict] = {}

    for sig in matched:
        detail_id = int(sig.get("detail_id", 0))
        hid = int(sig.get("hotel_id", 0))
        hname = sig.get("hotel_name", "")
        price = float(sig.get("S_t", 0) or 0)
        pred = predictions.get(str(detail_id)) or {}
        predicted_price = float(
            sig.get("predicted_price", 0)
            or pred.get("predicted_checkin_price", 0)
            or 0
        )

        if hid not in hotel_counts:
            hotel_counts[hid] = {"hotel_id": hid, "hotel_name": hname, "queued": 0, "skipped": 0}

        try:
            enqueue_opportunity(
                detail_id=detail_id,
                hotel_id=hid,
                buy_price=price,
                predicted_price=predicted_price,
                signal=str(sig.get("recommendation", "CALL")),
                confidence=str(sig.get("confidence", "")),
                max_rooms=max_rooms,
                hotel_name=hname,
                category=str(sig.get("category", "")),
                board=str(sig.get("board", "")),
                checkin_date=str(sig.get("checkin_date", "")),
                trigger_type="group_opportunity",
                batch_id=batch_id,
            )
            queued += 1
            hotel_counts[hid]["queued"] += 1
        except (OpportunityValidationError, ValueError) as exc:
            skipped += 1
            hotel_counts[hid]["skipped"] += 1
            reason = f"detail={detail_id}: {exc}"
            if len(skip_reasons) < 10:
                skip_reasons.append(reason)

    logger.info(
        "group_actions: opportunity batch=%s filter=[%s] queued=%d skipped=%d rooms=%d",
        batch_id, gf.describe(), queued, skipped, max_rooms,
    )

    return GroupActionResult(
        batch_id=batch_id,
        action="opportunity",
        filter_description=gf.describe(),
        total_matched=len(matched),
        total_queued=queued,
        total_skipped=skipped,
        skipped_reasons=skip_reasons,
        hotel_breakdown=sorted(hotel_counts.values(), key=lambda h: h["queued"], reverse=True),
        timestamp=datetime.utcnow().isoformat() + "Z",
    )
