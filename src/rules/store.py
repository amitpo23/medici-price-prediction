"""CRUD operations for the Pricing Rules database.

All read/write operations for pricing_rules, pricing_rules_log,
and pricing_rule_presets tables.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from src.rules.models import (
    PricingRuleCreate,
    PricingRuleLogORM,
    PricingRuleORM,
    PricingRulePresetORM,
    PricingRuleResponse,
    PricingRuleUpdate,
    RuleStatsResponse,
    SessionLocal,
)

logger = logging.getLogger(__name__)


def _orm_to_response(r: PricingRuleORM) -> PricingRuleResponse:
    """Convert ORM row to Pydantic response."""
    return PricingRuleResponse(
        id=r.id,
        hotel_id=r.hotel_id,
        rule_type=r.rule_type,
        rule_value=r.rule_value,
        rule_text=r.rule_text,
        room_category=r.room_category,
        room_board=r.room_board,
        is_active=r.is_active,
        priority=r.priority,
        source=r.source,
        reason=r.reason,
        confidence=r.confidence,
        created_at=r.created_at.isoformat() if r.created_at else None,
        updated_at=r.updated_at.isoformat() if r.updated_at else None,
        expires_at=r.expires_at.isoformat() if r.expires_at else None,
        created_by=r.created_by or "system",
    )


class RulesStore:
    """CRUD interface for pricing rules."""

    # ── Create ───────────────────────────────────────────────────────

    def create_rule(self, data: PricingRuleCreate) -> PricingRuleResponse:
        """Create a new pricing rule."""
        with SessionLocal() as session:
            expires = None
            if data.expires_at:
                try:
                    expires = datetime.fromisoformat(data.expires_at)
                except ValueError:
                    pass

            rule = PricingRuleORM(
                hotel_id=data.hotel_id,
                rule_type=data.rule_type.value,
                rule_value=data.rule_value,
                rule_text=data.rule_text,
                room_category=data.room_category,
                room_board=data.room_board,
                priority=data.priority,
                source=data.source.value,
                reason=data.reason,
                confidence=data.confidence,
                expires_at=expires,
                created_by=data.created_by,
            )
            session.add(rule)
            session.commit()
            session.refresh(rule)

            self._log_action(session, rule.id, rule.hotel_id, "created",
                             new_value=rule.rule_value,
                             details=f"type={rule.rule_type}, source={rule.source}")

            logger.info("Rule #%d created: hotel=%d type=%s value=%s",
                        rule.id, rule.hotel_id, rule.rule_type, rule.rule_value)
            return _orm_to_response(rule)

    def create_rules_batch(self, rules: list[PricingRuleCreate]) -> list[PricingRuleResponse]:
        """Create multiple rules at once."""
        results = []
        for r in rules:
            results.append(self.create_rule(r))
        return results

    # ── Read ─────────────────────────────────────────────────────────

    def get_rule(self, rule_id: int) -> Optional[PricingRuleResponse]:
        """Get a single rule by ID."""
        with SessionLocal() as session:
            rule = session.query(PricingRuleORM).filter_by(id=rule_id).first()
            return _orm_to_response(rule) if rule else None

    def get_rules_for_hotel(self, hotel_id: int,
                            active_only: bool = True) -> list[PricingRuleResponse]:
        """Get all rules for a specific hotel."""
        with SessionLocal() as session:
            q = session.query(PricingRuleORM).filter_by(hotel_id=hotel_id)
            if active_only:
                q = q.filter_by(is_active=True)
            # Expire stale rules
            now = datetime.now(timezone.utc)
            q = q.order_by(PricingRuleORM.priority.desc())
            rules = q.all()

            result = []
            for r in rules:
                if r.expires_at and r.expires_at.replace(tzinfo=timezone.utc) < now:
                    r.is_active = False
                    self._log_action(session, r.id, r.hotel_id, "expired")
                    continue
                result.append(_orm_to_response(r))

            session.commit()
            return result

    def get_all_active_rules(self) -> list[PricingRuleResponse]:
        """Get all active rules across all hotels."""
        with SessionLocal() as session:
            now = datetime.now(timezone.utc)
            rules = (
                session.query(PricingRuleORM)
                .filter_by(is_active=True)
                .order_by(PricingRuleORM.hotel_id, PricingRuleORM.priority.desc())
                .all()
            )
            result = []
            for r in rules:
                if r.expires_at and r.expires_at.replace(tzinfo=timezone.utc) < now:
                    r.is_active = False
                    continue
                result.append(_orm_to_response(r))
            session.commit()
            return result

    def get_active_rules_raw(self, hotel_id: int) -> list[PricingRuleORM]:
        """Get raw ORM objects for the engine (avoids double serialization)."""
        with SessionLocal() as session:
            now = datetime.now(timezone.utc)
            rules = (
                session.query(PricingRuleORM)
                .filter_by(hotel_id=hotel_id, is_active=True)
                .order_by(PricingRuleORM.priority.desc())
                .all()
            )
            # Detach from session so engine can use them
            active = []
            for r in rules:
                if r.expires_at and r.expires_at.replace(tzinfo=timezone.utc) < now:
                    r.is_active = False
                    continue
                # Make a detached copy
                session.expunge(r)
                active.append(r)
            session.commit()
            return active

    # ── Update ───────────────────────────────────────────────────────

    def update_rule(self, rule_id: int, data: PricingRuleUpdate) -> Optional[PricingRuleResponse]:
        """Update an existing rule."""
        with SessionLocal() as session:
            rule = session.query(PricingRuleORM).filter_by(id=rule_id).first()
            if not rule:
                return None

            old_value = rule.rule_value
            update_fields = data.model_dump(exclude_unset=True)

            if "expires_at" in update_fields and update_fields["expires_at"]:
                try:
                    update_fields["expires_at"] = datetime.fromisoformat(update_fields["expires_at"])
                except ValueError:
                    del update_fields["expires_at"]

            for field, value in update_fields.items():
                if value is not None:
                    setattr(rule, field, value)

            rule.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(rule)

            self._log_action(session, rule.id, rule.hotel_id, "updated",
                             old_value=old_value, new_value=rule.rule_value)

            logger.info("Rule #%d updated: hotel=%d", rule.id, rule.hotel_id)
            return _orm_to_response(rule)

    # ── Delete (soft) ────────────────────────────────────────────────

    def deactivate_rule(self, rule_id: int) -> bool:
        """Soft-delete: set is_active=False."""
        with SessionLocal() as session:
            rule = session.query(PricingRuleORM).filter_by(id=rule_id).first()
            if not rule:
                return False
            rule.is_active = False
            rule.updated_at = datetime.now(timezone.utc)
            self._log_action(session, rule.id, rule.hotel_id, "deactivated")
            session.commit()
            logger.info("Rule #%d deactivated: hotel=%d", rule.id, rule.hotel_id)
            return True

    def deactivate_hotel_rules(self, hotel_id: int,
                                rule_type: Optional[str] = None,
                                source: Optional[str] = None) -> int:
        """Deactivate all rules for a hotel (optionally filtered)."""
        with SessionLocal() as session:
            q = session.query(PricingRuleORM).filter_by(
                hotel_id=hotel_id, is_active=True,
            )
            if rule_type:
                q = q.filter_by(rule_type=rule_type)
            if source:
                q = q.filter_by(source=source)

            rules = q.all()
            count = 0
            for r in rules:
                r.is_active = False
                r.updated_at = datetime.now(timezone.utc)
                count += 1

            session.commit()
            logger.info("Deactivated %d rules for hotel %d", count, hotel_id)
            return count

    # ── Log ──────────────────────────────────────────────────────────

    def log_application(self, rule_id: Optional[int], hotel_id: int,
                        applied_to_price: float, result_price: float,
                        details: str = "") -> None:
        """Log that a rule was applied to a price."""
        with SessionLocal() as session:
            self._log_action(
                session, rule_id, hotel_id, "applied",
                applied_to_price=applied_to_price,
                result_price=result_price,
                details=details,
            )
            session.commit()

    def _log_action(self, session, rule_id: Optional[int], hotel_id: int,
                    action: str, old_value: float = None,
                    new_value: float = None, applied_to_price: float = None,
                    result_price: float = None, details: str = "") -> None:
        """Write an audit log entry."""
        log = PricingRuleLogORM(
            rule_id=rule_id,
            hotel_id=hotel_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            applied_to_price=applied_to_price,
            result_price=result_price,
            details=details,
        )
        session.add(log)

    def get_recent_logs(self, hotel_id: Optional[int] = None,
                        limit: int = 50) -> list[dict]:
        """Get recent rule application logs."""
        with SessionLocal() as session:
            q = session.query(PricingRuleLogORM)
            if hotel_id:
                q = q.filter_by(hotel_id=hotel_id)
            logs = q.order_by(PricingRuleLogORM.timestamp.desc()).limit(limit).all()
            return [
                {
                    "id": l.id,
                    "rule_id": l.rule_id,
                    "hotel_id": l.hotel_id,
                    "action": l.action,
                    "old_value": l.old_value,
                    "new_value": l.new_value,
                    "applied_to_price": l.applied_to_price,
                    "result_price": l.result_price,
                    "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                    "details": l.details,
                }
                for l in logs
            ]

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> RuleStatsResponse:
        """Get aggregate statistics about rules."""
        with SessionLocal() as session:
            all_rules = session.query(PricingRuleORM).all()
            active = [r for r in all_rules if r.is_active]

            by_type: dict[str, int] = {}
            by_source: dict[str, int] = {}
            hotels = set()
            auto_count = 0

            for r in active:
                by_type[r.rule_type] = by_type.get(r.rule_type, 0) + 1
                by_source[r.source] = by_source.get(r.source, 0) + 1
                hotels.add(r.hotel_id)
                if r.source in ("auto_fc", "auto_ml", "auto_market"):
                    auto_count += 1

            # Count recent applications (last 24h)
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            recent = (
                session.query(PricingRuleLogORM)
                .filter(PricingRuleLogORM.action == "applied")
                .filter(PricingRuleLogORM.timestamp >= cutoff)
                .count()
            )

            return RuleStatsResponse(
                total_rules=len(all_rules),
                active_rules=len(active),
                hotels_with_rules=len(hotels),
                rules_by_type=by_type,
                rules_by_source=by_source,
                recently_applied=recent,
                auto_generated=auto_count,
            )

    # ── Presets ──────────────────────────────────────────────────────

    def save_preset(self, name: str, description: str,
                    rules_json: str, is_default: bool = False) -> dict:
        """Save a preset template."""
        with SessionLocal() as session:
            existing = session.query(PricingRulePresetORM).filter_by(
                preset_name=name,
            ).first()
            if existing:
                existing.description = description
                existing.rules_json = rules_json
                existing.is_default = is_default
                session.commit()
                return {"id": existing.id, "name": name, "action": "updated"}
            else:
                preset = PricingRulePresetORM(
                    preset_name=name,
                    description=description,
                    rules_json=rules_json,
                    is_default=is_default,
                )
                session.add(preset)
                session.commit()
                session.refresh(preset)
                return {"id": preset.id, "name": name, "action": "created"}

    def get_presets(self) -> list[dict]:
        """List all presets."""
        with SessionLocal() as session:
            presets = session.query(PricingRulePresetORM).all()
            return [
                {
                    "id": p.id,
                    "name": p.preset_name,
                    "description": p.description,
                    "rules": json.loads(p.rules_json) if p.rules_json else [],
                    "is_default": p.is_default,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in presets
            ]

    def get_preset(self, preset_id: int) -> Optional[dict]:
        """Get a single preset."""
        with SessionLocal() as session:
            p = session.query(PricingRulePresetORM).filter_by(id=preset_id).first()
            if not p:
                return None
            return {
                "id": p.id,
                "name": p.preset_name,
                "description": p.description,
                "rules": json.loads(p.rules_json) if p.rules_json else [],
                "is_default": p.is_default,
            }

    def apply_preset(self, preset_id: int, hotel_id: int) -> list[PricingRuleResponse]:
        """Apply a preset to a hotel — creates rules from the template."""
        preset = self.get_preset(preset_id)
        if not preset:
            return []

        rules_defs = preset.get("rules", [])
        created = []
        for rd in rules_defs:
            rule_create = PricingRuleCreate(
                hotel_id=hotel_id,
                rule_type=rd.get("rule_type", "markup_pct"),
                rule_value=rd.get("rule_value", 0),
                rule_text=rd.get("rule_text"),
                room_category=rd.get("room_category"),
                room_board=rd.get("room_board"),
                priority=rd.get("priority", 0),
                source="preset",
                reason=f"Preset: {preset['name']}",
                confidence=rd.get("confidence"),
                created_by="preset",
            )
            created.append(self.create_rule(rule_create))

        return created
