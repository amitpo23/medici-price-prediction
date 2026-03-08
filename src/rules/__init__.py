"""Pricing Rules Engine — per-hotel price control for SalesOffice Step 5.

This module provides:
- Rule definitions and ORM models
- CRUD operations for rules DB (SQLite)
- Rules application pipeline (the core decision engine)
- Auto-generation from Forward Curve predictions
- Preset templates for common strategies
"""
from src.rules.models import RuleType, RuleSource, RuleAction
from src.rules.engine import RulesEngine
from src.rules.store import RulesStore

__all__ = ["RuleType", "RuleSource", "RuleAction", "RulesEngine", "RulesStore"]
