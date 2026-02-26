"""Data schemas for trading system entities (read from medici-db)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class TradingBooking:
    """A room purchased and held in inventory (from MED_Book)."""

    pre_book_id: int
    hotel_id: int
    buy_price: float
    push_price: float
    date_from: date
    date_to: date
    is_active: bool
    is_sold: bool
    cancellation_to: date | None = None
    last_price: float | None = None
    sold_id: str | None = None
    source: int | None = None
    adults: int = 2
    children: int = 0
    created: datetime | None = None
    hotel_name: str | None = None
    opportunity_id: int | None = None

    @property
    def nights(self) -> int:
        return (self.date_to - self.date_from).days

    @property
    def margin_pct(self) -> float:
        if self.buy_price <= 0:
            return 0.0
        return (self.push_price - self.buy_price) / self.buy_price * 100

    @property
    def days_to_checkin(self) -> int:
        return max(0, (self.date_from - date.today()).days)

    @property
    def days_to_cancel_deadline(self) -> int | None:
        if self.cancellation_to is None:
            return None
        return max(0, (self.cancellation_to - date.today()).days)


@dataclass
class TradingOpportunity:
    """A buy opportunity being evaluated (from MED_Opportunities or API request)."""

    hotel_id: int
    date_from: date
    date_to: date
    buy_price: float
    push_price: float | None = None
    category_id: int | None = None
    board_id: int | None = None
    source_id: int | None = None
    source_name: str | None = None
    is_free_cancellation: bool = False
    cancellation_deadline: date | None = None
    adults: int = 2
    children: int = 0
    currency: str = "USD"
    opportunity_id: str | None = None

    @property
    def nights(self) -> int:
        return (self.date_to - self.date_from).days

    @property
    def buy_price_per_night(self) -> float:
        n = self.nights
        return self.buy_price / n if n > 0 else self.buy_price


@dataclass
class Recommendation:
    """A recommendation produced by the analysis engine."""

    type: str  # BUY, PASS, HOLD, REPRICE, CONSIDER_CANCEL, ALERT
    confidence: float
    reasoning: list[str]
    hotel_id: int
    booking_reference: int | None = None
    opportunity_reference: str | None = None
    price_data: dict | None = None
    risk_data: dict | None = None
    market_context: dict | None = None
    impact_factors: list[dict] = field(default_factory=list)
