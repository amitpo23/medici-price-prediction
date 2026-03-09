"""Background analysis scheduler for periodic trading analysis.

Runs portfolio analysis and opportunity scans on configurable intervals.
Stores results in memory for fast retrieval via the API.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from config.settings import TRADING_ANALYSIS_INTERVAL_MINUTES

logger = logging.getLogger(__name__)

# ── In-memory result store ───────────────────────────────────────────

_latest_results: dict = {}
_lock = threading.Lock()


def get_latest_results() -> dict:
    """Return the latest analysis results (thread-safe)."""
    with _lock:
        return _latest_results.copy()


def _store_results(results: dict) -> None:
    """Store analysis results (thread-safe)."""
    global _latest_results
    with _lock:
        _latest_results = results


# ── Scheduler ────────────────────────────────────────────────────────

class AnalysisScheduler:
    """Periodic background analysis of the trading portfolio.

    Runs on a configurable interval (default: every 30 minutes).
    Results are stored in memory and served via GET /recommendations/active.
    """

    def __init__(self, interval_minutes: int = TRADING_ANALYSIS_INTERVAL_MINUTES):
        self.interval_seconds = interval_minutes * 60
        self._timer: threading.Timer | None = None
        self._running = False

    def start(self) -> None:
        """Start the periodic analysis loop."""
        if self._running:
            return
        self._running = True
        logger.info(
            "Analysis scheduler started (interval: %d min)",
            self.interval_seconds // 60,
        )
        self._schedule_next()

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        logger.info("Analysis scheduler stopped")

    def _schedule_next(self) -> None:
        """Schedule the next analysis run."""
        if not self._running:
            return
        self._timer = threading.Timer(self.interval_seconds, self._run_cycle)
        self._timer.daemon = True
        self._timer.start()

    def _run_cycle(self) -> None:
        """Execute one analysis cycle."""
        try:
            self.run_portfolio_analysis()
        except (OSError, ConnectionError, ValueError, TypeError, RuntimeError):
            logger.exception("Portfolio analysis cycle failed")
        finally:
            self._schedule_next()

    def run_portfolio_analysis(self) -> dict:
        """Run a full portfolio analysis and store results."""
        from src.data.trading_db import load_active_bookings, check_connection
        from src.models.recommender import TradingRecommender

        if not check_connection():
            logger.warning("Trading DB not connected — skipping analysis")
            return {}

        bookings = load_active_bookings()
        if bookings.empty:
            result = {
                "last_run": datetime.utcnow().isoformat(),
                "portfolio": {"total_bookings": 0, "summary": "No active bookings"},
                "recommendations_count": 0,
            }
            _store_results(result)
            return result

        # Build predictions for all hotels
        from src.api.integration import _get_predicted_price, _get_occupancy_forecast

        hotel_ids = bookings["HotelId"].unique()
        predictions = {}
        occupancy_forecasts = {}

        for hid in hotel_ids:
            hid = int(hid)
            hotel_bookings = bookings[bookings["HotelId"] == hid]
            date_from = str(hotel_bookings.iloc[0].get("DateFrom", ""))
            predictions[hid] = _get_predicted_price(hid, date_from)
            occ = _get_occupancy_forecast(hid, date_from)
            if occ is not None:
                occupancy_forecasts[hid] = occ

        recommender = TradingRecommender()
        portfolio = recommender.analyze_portfolio(
            bookings, predictions, occupancy_forecasts or None,
        )

        result = {
            "last_run": datetime.utcnow().isoformat(),
            "portfolio": portfolio,
            "recommendations_count": portfolio.get("attention_count", 0),
        }
        _store_results(result)
        logger.info(
            "Portfolio analysis complete: %d bookings, %d attention items",
            portfolio.get("total_bookings", 0),
            portfolio.get("attention_count", 0),
        )
        return result

    def run_now(self) -> dict:
        """Trigger an immediate analysis (used for testing or manual triggers)."""
        return self.run_portfolio_analysis()


# ── Module-level singleton ───────────────────────────────────────────

_scheduler: AnalysisScheduler | None = None


def get_scheduler() -> AnalysisScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AnalysisScheduler()
    return _scheduler


def start_scheduler() -> None:
    """Start the global scheduler (called from FastAPI startup)."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler() -> None:
    """Stop the global scheduler (called from FastAPI shutdown)."""
    if _scheduler is not None:
        _scheduler.stop()
