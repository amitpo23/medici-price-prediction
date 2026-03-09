"""ORM models and Pydantic schemas for the Pricing Rules Engine.

Two layers:
  1. SQLAlchemy ORM — persistent storage in SQLite
  2. Pydantic models — API request/response validation
"""
from __future__ import annotations

import enum
import logging
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import RULES_DB_PATH

# ── Enums ────────────────────────────────────────────────────────────


class RuleType(str, enum.Enum):
    """Types of pricing rules that can be applied."""

    PRICE_CEILING = "price_ceiling"           # max buy price
    PRICE_FLOOR = "price_floor"               # min sell price
    MARKUP_PCT = "markup_pct"                 # % markup instead of $0.01
    MARKUP_FIXED = "markup_fixed"             # fixed $ markup
    TARGET_PRICE = "target_price"             # buy only if ≤ target
    EXCLUDE_CATEGORY = "exclude_category"     # skip category
    EXCLUDE_BOARD = "exclude_board"           # skip board type
    MAX_ROOMS = "max_rooms"                   # max rooms to push
    AUTO_CLOSE_THRESHOLD = "auto_close_threshold"  # close if price >
    HOLD_UNTIL_DROP = "hold_until_drop"       # don't add — wait for price drop
    PREFERRED_CATEGORY = "preferred_category" # favor specific category


class RuleSource(str, enum.Enum):
    """Who/what created the rule."""

    MANUAL = "manual"         # human operator
    AUTO_FC = "auto_fc"       # auto-generated from Forward Curve
    AUTO_ML = "auto_ml"       # auto-generated from ML model
    AUTO_MARKET = "auto_market"  # auto-generated from market signals
    PRESET = "preset"         # from a preset template


class RuleAction(str, enum.Enum):
    """Action to take on a room after rules evaluation."""

    ACCEPT = "ACCEPT"     # push to Zenith (possibly with new price)
    REJECT = "REJECT"     # do NOT push — skip this room
    MODIFY = "MODIFY"     # push with modified price
    HOLD = "HOLD"         # don't add new, but keep existing


# ── SQLAlchemy ORM ───────────────────────────────────────────────────

Base = declarative_base()


class PricingRuleORM(Base):
    """Persistent pricing rule stored in SQLite."""

    __tablename__ = "pricing_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, nullable=False, index=True)
    rule_type = Column(String(50), nullable=False)
    rule_value = Column(Float, nullable=False)
    rule_text = Column(String(200), nullable=True)        # for exclude_category etc.
    room_category = Column(String(100), nullable=True)    # NULL = all categories
    room_board = Column(String(50), nullable=True)        # NULL = all boards
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0)                 # higher = applied first
    source = Column(String(50), nullable=False, default="manual")
    reason = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(String(100), default="system")


class PricingRuleLogORM(Base):
    """Audit log for rule actions."""

    __tablename__ = "pricing_rules_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, nullable=True)
    hotel_id = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)           # created/updated/applied/expired
    old_value = Column(Float, nullable=True)
    new_value = Column(Float, nullable=True)
    applied_to_price = Column(Float, nullable=True)       # input price
    result_price = Column(Float, nullable=True)            # output price
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    details = Column(Text, nullable=True)                  # JSON context


class PricingRulePresetORM(Base):
    """Reusable preset templates."""

    __tablename__ = "pricing_rule_presets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    preset_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    rules_json = Column(Text, nullable=False)              # JSON array of rule defs
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Engine / Session factory ─────────────────────────────────────────

_engine = create_engine(
    f"sqlite:///{RULES_DB_PATH}",
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Create all tables if they don't exist."""
    try:
        Base.metadata.create_all(_engine, checkfirst=True)
    except (OSError, ImportError) as e:
        logger.warning("DB table init skipped: %s", e)


# Auto-init on import
init_db()


# ── Pydantic Schemas (API layer) ────────────────────────────────────

class PricingRuleCreate(BaseModel):
    """Request body for creating a pricing rule."""

    hotel_id: int
    rule_type: RuleType
    rule_value: float = 0.0
    rule_text: Optional[str] = None
    room_category: Optional[str] = None
    room_board: Optional[str] = None
    priority: int = 0
    source: RuleSource = RuleSource.MANUAL
    reason: Optional[str] = None
    confidence: Optional[float] = None
    expires_at: Optional[str] = None           # ISO datetime string
    created_by: str = "api"


class PricingRuleUpdate(BaseModel):
    """Request body for updating a pricing rule."""

    rule_value: Optional[float] = None
    rule_text: Optional[str] = None
    room_category: Optional[str] = None
    room_board: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    reason: Optional[str] = None
    confidence: Optional[float] = None
    expires_at: Optional[str] = None


class PricingRuleResponse(BaseModel):
    """Response model for a single rule."""

    id: int
    hotel_id: int
    rule_type: str
    rule_value: float
    rule_text: Optional[str] = None
    room_category: Optional[str] = None
    room_board: Optional[str] = None
    is_active: bool
    priority: int
    source: str
    reason: Optional[str] = None
    confidence: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None
    created_by: str = "system"


class RuleApplyRequest(BaseModel):
    """Single room to evaluate rules against."""

    hotel_id: int
    price: float
    category: str = ""
    board: str = ""


class RuleApplyResult(BaseModel):
    """Result of applying rules to a single room."""

    hotel_id: int
    original_price: float
    action: RuleAction
    adjusted_price: float
    markup_applied: float = 0.0
    rules_applied: list[dict] = Field(default_factory=list)
    reason: str = ""
    confidence: Optional[float] = None


class RuleBatchRequest(BaseModel):
    """Batch request: multiple rooms at once."""

    rooms: list[RuleApplyRequest]


class RuleBatchResponse(BaseModel):
    """Batch response."""

    results: list[RuleApplyResult]
    total: int
    accepted: int
    rejected: int
    modified: int


class RuleStatsResponse(BaseModel):
    """Statistics about rules."""

    total_rules: int
    active_rules: int
    hotels_with_rules: int
    rules_by_type: dict
    rules_by_source: dict
    recently_applied: int = 0
    auto_generated: int = 0
