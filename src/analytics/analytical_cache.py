"""Analytical Cache — Local SQLite pre-computed data store.

Three-layer cache architecture:
  Layer 1: Reference Data (static, loaded at startup)
  Layer 2: Aggregated Market Data (refreshed nightly)
  Layer 3: Real-Time signals & zones (refreshed every 3h with scheduler)

This is a SEPARATE database from price_store.py (salesoffice_prices.db).
It never touches trading_db.py or Azure SQL directly — it consumes
pre-aggregated data from cache_aggregator.py.

Safety: This file is NEW — does not modify any existing file.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)

CACHE_DB_PATH = DATA_DIR / "analytical_cache.db"


class AnalyticalCache:
    """Manages the local analytical cache database.

    Thread-safe via SQLite WAL mode. Each method opens/closes its own
    connection to avoid cross-thread issues.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or CACHE_DB_PATH
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a new connection with WAL mode and row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Create all tables if they don't exist."""
        conn = self._get_conn()
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
            logger.info("Analytical cache schema ensured at %s", self.db_path)
        finally:
            conn.close()

    # ── Layer 1: Reference Data ──────────────────────────────────────

    def upsert_hotels(self, hotels: list[dict]) -> int:
        """Upsert hotel reference data. Returns count inserted/updated."""
        if not hotels:
            return 0
        conn = self._get_conn()
        try:
            count = 0
            for h in hotels:
                conn.execute("""
                    INSERT INTO ref_hotels (hotel_id, hotel_name, city, stars, latitude, longitude, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(hotel_id) DO UPDATE SET
                        hotel_name=excluded.hotel_name, city=excluded.city,
                        stars=excluded.stars, latitude=excluded.latitude,
                        longitude=excluded.longitude, updated_at=excluded.updated_at
                """, (
                    h.get("hotel_id"), h.get("hotel_name", ""),
                    h.get("city", ""), h.get("stars", 0),
                    h.get("latitude"), h.get("longitude"),
                    datetime.utcnow().isoformat(),
                ))
                count += 1
            conn.commit()
            logger.info("Upserted %d hotels into ref_hotels", count)
            return count
        finally:
            conn.close()

    def upsert_categories(self, categories: list[dict]) -> int:
        """Upsert category reference data."""
        if not categories:
            return 0
        conn = self._get_conn()
        try:
            count = 0
            for c in categories:
                conn.execute("""
                    INSERT INTO ref_categories (category_id, category_name, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(category_id) DO UPDATE SET
                        category_name=excluded.category_name, updated_at=excluded.updated_at
                """, (c.get("category_id"), c.get("category_name", ""), datetime.utcnow().isoformat()))
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def upsert_boards(self, boards: list[dict]) -> int:
        """Upsert board type reference data."""
        if not boards:
            return 0
        conn = self._get_conn()
        try:
            count = 0
            for b in boards:
                conn.execute("""
                    INSERT INTO ref_boards (board_id, board_name, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(board_id) DO UPDATE SET
                        board_name=excluded.board_name, updated_at=excluded.updated_at
                """, (b.get("board_id"), b.get("board_name", ""), datetime.utcnow().isoformat()))
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def get_hotels(self) -> list[dict]:
        """Get all hotels from reference cache."""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM ref_hotels ORDER BY hotel_name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_hotel(self, hotel_id: int) -> Optional[dict]:
        """Get single hotel by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM ref_hotels WHERE hotel_id=?", (hotel_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ── Layer 2: Aggregated Market Data ──────────────────────────────

    def upsert_market_daily(self, rows: list[dict]) -> int:
        """Upsert aggregated daily market data (from AI_Search_HotelData).

        Each row represents one hotel+date+room_type+board aggregation.
        """
        if not rows:
            return 0
        conn = self._get_conn()
        try:
            count = 0
            for r in rows:
                conn.execute("""
                    INSERT INTO agg_market_daily
                        (hotel_id, date, room_type, board, avg_price, min_price,
                         max_price, observation_count, providers, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(hotel_id, date, room_type, board) DO UPDATE SET
                        avg_price=excluded.avg_price, min_price=excluded.min_price,
                        max_price=excluded.max_price, observation_count=excluded.observation_count,
                        providers=excluded.providers, computed_at=excluded.computed_at
                """, (
                    r["hotel_id"], r["date"], r.get("room_type", ""),
                    r.get("board", ""), r["avg_price"], r["min_price"],
                    r["max_price"], r["observation_count"],
                    r.get("providers", ""), datetime.utcnow().isoformat(),
                ))
                count += 1
            conn.commit()
            logger.info("Upserted %d rows into agg_market_daily", count)
            return count
        finally:
            conn.close()

    def upsert_competitor_matrix(self, rows: list[dict]) -> int:
        """Upsert pre-computed competitor relationships."""
        if not rows:
            return 0
        conn = self._get_conn()
        try:
            count = 0
            for r in rows:
                conn.execute("""
                    INSERT INTO agg_competitor_matrix
                        (hotel_id, competitor_hotel_id, distance_km, star_diff,
                         avg_price_ratio, market_pressure, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(hotel_id, competitor_hotel_id) DO UPDATE SET
                        distance_km=excluded.distance_km, star_diff=excluded.star_diff,
                        avg_price_ratio=excluded.avg_price_ratio,
                        market_pressure=excluded.market_pressure,
                        computed_at=excluded.computed_at
                """, (
                    r["hotel_id"], r["competitor_hotel_id"],
                    r.get("distance_km", 0), r.get("star_diff", 0),
                    r.get("avg_price_ratio", 1.0), r.get("market_pressure", 0.0),
                    datetime.utcnow().isoformat(),
                ))
                count += 1
            conn.commit()
            logger.info("Upserted %d rows into agg_competitor_matrix", count)
            return count
        finally:
            conn.close()

    def get_market_daily(self, hotel_id: int, days_back: int = 90) -> list[dict]:
        """Get aggregated market data for a hotel."""
        conn = self._get_conn()
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            rows = conn.execute("""
                SELECT * FROM agg_market_daily
                WHERE hotel_id=? AND date >= ?
                ORDER BY date
            """, (hotel_id, cutoff)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_competitors(self, hotel_id: int) -> list[dict]:
        """Get pre-computed competitors for a hotel."""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT cm.*, h.hotel_name AS competitor_name, h.stars AS competitor_stars
                FROM agg_competitor_matrix cm
                LEFT JOIN ref_hotels h ON h.hotel_id = cm.competitor_hotel_id
                WHERE cm.hotel_id=?
                ORDER BY cm.distance_km
            """, (hotel_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Layer 3: Daily Signals ───────────────────────────────────────

    def save_daily_signals(self, signals: list[dict]) -> int:
        """Save per-day CALL/PUT/NEUTRAL signals for rooms."""
        if not signals:
            return 0
        conn = self._get_conn()
        try:
            count = 0
            for s in signals:
                conn.execute("""
                    INSERT INTO daily_signals
                        (detail_id, hotel_id, signal_date, t_value, predicted_price,
                         daily_change_pct, signal, confidence, enrichment_json, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(detail_id, signal_date) DO UPDATE SET
                        t_value=excluded.t_value, predicted_price=excluded.predicted_price,
                        daily_change_pct=excluded.daily_change_pct, signal=excluded.signal,
                        confidence=excluded.confidence, enrichment_json=excluded.enrichment_json,
                        computed_at=excluded.computed_at
                """, (
                    s["detail_id"], s["hotel_id"], s["signal_date"],
                    s["t_value"], s["predicted_price"], s["daily_change_pct"],
                    s["signal"], s["confidence"],
                    json.dumps(s.get("enrichments", {})),
                    datetime.utcnow().isoformat(),
                ))
                count += 1
            conn.commit()
            logger.info("Saved %d daily signals", count)
            return count
        finally:
            conn.close()

    def get_daily_signals(self, detail_id: int, days_forward: int = 30) -> list[dict]:
        """Get daily signals for a specific room option."""
        conn = self._get_conn()
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            cutoff = (datetime.utcnow() + timedelta(days=days_forward)).strftime("%Y-%m-%d")
            rows = conn.execute("""
                SELECT * FROM daily_signals
                WHERE detail_id=? AND signal_date >= ? AND signal_date <= ?
                ORDER BY signal_date
            """, (detail_id, today, cutoff)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_hotel_daily_signals(self, hotel_id: int, signal_date: Optional[str] = None) -> list[dict]:
        """Get all signals for a hotel on a specific date (default: today)."""
        conn = self._get_conn()
        try:
            date = signal_date or datetime.utcnow().strftime("%Y-%m-%d")
            rows = conn.execute("""
                SELECT * FROM daily_signals
                WHERE hotel_id=? AND signal_date=?
                ORDER BY detail_id
            """, (hotel_id, date)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Layer 3: Demand Zones ────────────────────────────────────────

    def save_demand_zones(self, zones: list[dict]) -> int:
        """Save detected demand zones (support/resistance levels)."""
        if not zones:
            return 0
        conn = self._get_conn()
        try:
            count = 0
            for z in zones:
                conn.execute("""
                    INSERT INTO demand_zones
                        (zone_id, hotel_id, category, zone_type, price_lower, price_upper,
                         touch_count, strength, first_touch, last_touch, is_broken, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(zone_id) DO UPDATE SET
                        price_lower=excluded.price_lower, price_upper=excluded.price_upper,
                        touch_count=excluded.touch_count, strength=excluded.strength,
                        last_touch=excluded.last_touch, is_broken=excluded.is_broken,
                        computed_at=excluded.computed_at
                """, (
                    z["zone_id"], z["hotel_id"], z.get("category", ""),
                    z["zone_type"], z["price_lower"], z["price_upper"],
                    z["touch_count"], z["strength"],
                    z.get("first_touch", ""), z.get("last_touch", ""),
                    z.get("is_broken", False), datetime.utcnow().isoformat(),
                ))
                count += 1
            conn.commit()
            logger.info("Saved %d demand zones", count)
            return count
        finally:
            conn.close()

    def get_demand_zones(self, hotel_id: int, category: Optional[str] = None, active_only: bool = True) -> list[dict]:
        """Get demand zones for a hotel, optionally filtered by category."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM demand_zones WHERE hotel_id=?"
            params: list = [hotel_id]
            if category:
                query += " AND category=?"
                params.append(category)
            if active_only:
                query += " AND is_broken=0"
            query += " ORDER BY strength DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Layer 3: Trade Setups ────────────────────────────────────────

    def save_trade_setups(self, setups: list[dict]) -> int:
        """Save computed trade setups (entry/stop/target/RR)."""
        if not setups:
            return 0
        conn = self._get_conn()
        try:
            count = 0
            for s in setups:
                conn.execute("""
                    INSERT INTO trade_setups
                        (detail_id, hotel_id, setup_type, entry_price, entry_t, entry_date,
                         stop_loss, stop_distance_pct, take_profit, target_distance_pct,
                         risk_reward_ratio, position_size, max_risk_usd,
                         signal, confidence, setup_quality, reason_json, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(detail_id, setup_type) DO UPDATE SET
                        entry_price=excluded.entry_price, entry_t=excluded.entry_t,
                        entry_date=excluded.entry_date, stop_loss=excluded.stop_loss,
                        stop_distance_pct=excluded.stop_distance_pct,
                        take_profit=excluded.take_profit, target_distance_pct=excluded.target_distance_pct,
                        risk_reward_ratio=excluded.risk_reward_ratio,
                        position_size=excluded.position_size, max_risk_usd=excluded.max_risk_usd,
                        signal=excluded.signal, confidence=excluded.confidence,
                        setup_quality=excluded.setup_quality, reason_json=excluded.reason_json,
                        computed_at=excluded.computed_at
                """, (
                    s["detail_id"], s["hotel_id"], s.get("setup_type", "primary"),
                    s["entry_price"], s["entry_t"], s.get("entry_date", ""),
                    s["stop_loss"], s["stop_distance_pct"],
                    s["take_profit"], s["target_distance_pct"],
                    s["risk_reward_ratio"], s.get("position_size", 1),
                    s.get("max_risk_usd", 0), s["signal"], s["confidence"],
                    s.get("setup_quality", "medium"),
                    json.dumps(s.get("reasons", {})),
                    datetime.utcnow().isoformat(),
                ))
                count += 1
            conn.commit()
            logger.info("Saved %d trade setups", count)
            return count
        finally:
            conn.close()

    def get_trade_setups(self, hotel_id: Optional[int] = None, signal: Optional[str] = None,
                         min_rr: float = 0.0) -> list[dict]:
        """Get trade setups, optionally filtered."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM trade_setups WHERE 1=1"
            params: list = []
            if hotel_id:
                query += " AND hotel_id=?"
                params.append(hotel_id)
            if signal:
                query += " AND signal=?"
                params.append(signal)
            if min_rr > 0:
                query += " AND risk_reward_ratio >= ?"
                params.append(min_rr)
            query += " ORDER BY risk_reward_ratio DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_trade_setup(self, detail_id: int) -> Optional[dict]:
        """Get trade setup for a specific room."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM trade_setups WHERE detail_id=? AND setup_type='primary'",
                (detail_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ── Layer 3: Trade Journal ───────────────────────────────────────

    def log_trade(self, trade: dict) -> int:
        """Log a trade entry/exit to the journal. Returns trade_id."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                INSERT INTO trade_journal
                    (detail_id, hotel_id, trade_type, entry_price, entry_date, entry_t,
                     exit_price, exit_date, exit_t, position_size, pnl_usd, pnl_pct,
                     mae_usd, mae_pct, mfe_usd, mfe_pct, signal_at_entry, confidence_at_entry,
                     exit_reason, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade["detail_id"], trade["hotel_id"],
                trade.get("trade_type", "CALL"),
                trade["entry_price"], trade["entry_date"], trade.get("entry_t", 0),
                trade.get("exit_price"), trade.get("exit_date"), trade.get("exit_t"),
                trade.get("position_size", 1),
                trade.get("pnl_usd", 0), trade.get("pnl_pct", 0),
                trade.get("mae_usd"), trade.get("mae_pct"),
                trade.get("mfe_usd"), trade.get("mfe_pct"),
                trade.get("signal_at_entry", ""), trade.get("confidence_at_entry", 0),
                trade.get("exit_reason", ""), trade.get("notes", ""),
                datetime.utcnow().isoformat(),
            ))
            conn.commit()
            return cursor.lastrowid or 0
        finally:
            conn.close()

    def get_trade_journal(self, hotel_id: Optional[int] = None, days_back: int = 90) -> list[dict]:
        """Get trade journal entries."""
        conn = self._get_conn()
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            query = "SELECT * FROM trade_journal WHERE created_at >= ?"
            params: list = [cutoff]
            if hotel_id:
                query += " AND hotel_id=?"
                params.append(hotel_id)
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_trade_stats(self) -> dict:
        """Get aggregated trading statistics."""
        conn = self._get_conn()
        try:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl_usd <= 0 THEN 1 ELSE 0 END) as losses,
                    AVG(pnl_pct) as avg_pnl_pct,
                    SUM(pnl_usd) as total_pnl_usd,
                    AVG(CASE WHEN pnl_usd > 0 THEN pnl_pct END) as avg_win_pct,
                    AVG(CASE WHEN pnl_usd <= 0 THEN pnl_pct END) as avg_loss_pct,
                    MIN(mae_pct) as worst_mae_pct,
                    MAX(mfe_pct) as best_mfe_pct
                FROM trade_journal
                WHERE exit_price IS NOT NULL
            """).fetchone()
            if not row or row["total_trades"] == 0:
                return {"total_trades": 0, "win_rate": 0, "total_pnl_usd": 0}
            d = dict(row)
            d["win_rate"] = round(d["wins"] / d["total_trades"] * 100, 1) if d["total_trades"] else 0
            # Profit factor: sum of wins / abs(sum of losses)
            pf_row = conn.execute("""
                SELECT
                    SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END) as gross_profit,
                    ABS(SUM(CASE WHEN pnl_usd <= 0 THEN pnl_usd ELSE 0 END)) as gross_loss
                FROM trade_journal WHERE exit_price IS NOT NULL
            """).fetchone()
            if pf_row and pf_row["gross_loss"] and pf_row["gross_loss"] > 0:
                d["profit_factor"] = round(pf_row["gross_profit"] / pf_row["gross_loss"], 2)
            else:
                d["profit_factor"] = 0
            return d
        finally:
            conn.close()

    # ── Structure Breaks ─────────────────────────────────────────────

    def save_structure_breaks(self, breaks: list[dict]) -> int:
        """Save detected Break of Structure (BOS) and CHOCH events."""
        if not breaks:
            return 0
        conn = self._get_conn()
        try:
            count = 0
            for b in breaks:
                conn.execute("""
                    INSERT INTO structure_breaks
                        (break_id, hotel_id, category, break_type, break_date,
                         break_price, previous_level, direction, significance, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(break_id) DO UPDATE SET
                        break_price=excluded.break_price, significance=excluded.significance,
                        computed_at=excluded.computed_at
                """, (
                    b["break_id"], b["hotel_id"], b.get("category", ""),
                    b["break_type"], b["break_date"], b["break_price"],
                    b.get("previous_level", 0), b["direction"],
                    b.get("significance", 0.5), datetime.utcnow().isoformat(),
                ))
                count += 1
            conn.commit()
            logger.info("Saved %d structure breaks", count)
            return count
        finally:
            conn.close()

    def get_structure_breaks(self, hotel_id: int, days_back: int = 30) -> list[dict]:
        """Get recent structure breaks for a hotel."""
        conn = self._get_conn()
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            rows = conn.execute("""
                SELECT * FROM structure_breaks
                WHERE hotel_id=? AND break_date >= ?
                ORDER BY break_date DESC
            """, (hotel_id, cutoff)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Metadata ─────────────────────────────────────────────────────

    def get_freshness(self) -> dict:
        """Get freshness info for each cache layer."""
        conn = self._get_conn()
        try:
            result = {}
            tables = {
                "ref_hotels": "Layer 1: Hotels",
                "agg_market_daily": "Layer 2: Market Daily",
                "agg_competitor_matrix": "Layer 2: Competitors",
                "daily_signals": "Layer 3: Daily Signals",
                "demand_zones": "Layer 3: Demand Zones",
                "trade_setups": "Layer 3: Trade Setups",
                "trade_journal": "Layer 3: Trade Journal",
                "structure_breaks": "Layer 3: Structure Breaks",
            }
            for table, label in tables.items():
                try:
                    row = conn.execute(f"SELECT COUNT(*) as cnt, MAX(computed_at) as latest FROM {table}").fetchone()
                    result[table] = {
                        "label": label,
                        "count": row["cnt"] if row else 0,
                        "latest": row["latest"] if row else None,
                    }
                except sqlite3.OperationalError:
                    result[table] = {"label": label, "count": 0, "latest": None}
            # Trade journal uses created_at, not computed_at
            try:
                row = conn.execute("SELECT COUNT(*) as cnt, MAX(created_at) as latest FROM trade_journal").fetchone()
                result["trade_journal"]["count"] = row["cnt"] if row else 0
                result["trade_journal"]["latest"] = row["latest"] if row else None
            except sqlite3.OperationalError:
                pass
            return result
        finally:
            conn.close()

    def clear_layer(self, layer: int) -> None:
        """Clear all data from a specific layer. Use with caution."""
        conn = self._get_conn()
        try:
            if layer == 1:
                conn.execute("DELETE FROM ref_hotels")
                conn.execute("DELETE FROM ref_categories")
                conn.execute("DELETE FROM ref_boards")
            elif layer == 2:
                conn.execute("DELETE FROM agg_market_daily")
                conn.execute("DELETE FROM agg_competitor_matrix")
            elif layer == 3:
                conn.execute("DELETE FROM daily_signals")
                conn.execute("DELETE FROM demand_zones")
                conn.execute("DELETE FROM trade_setups")
                conn.execute("DELETE FROM structure_breaks")
            conn.commit()
            logger.warning("Cleared analytical cache layer %d", layer)
        finally:
            conn.close()


# ── Schema SQL ───────────────────────────────────────────────────────

_SCHEMA_SQL = """
-- ══ Layer 1: Reference Data (static) ══

CREATE TABLE IF NOT EXISTS ref_hotels (
    hotel_id    INTEGER PRIMARY KEY,
    hotel_name  TEXT NOT NULL,
    city        TEXT DEFAULT '',
    stars       INTEGER DEFAULT 0,
    latitude    REAL,
    longitude   REAL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ref_categories (
    category_id   INTEGER PRIMARY KEY,
    category_name TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ref_boards (
    board_id   INTEGER PRIMARY KEY,
    board_name TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ══ Layer 2: Aggregated Market Data (nightly refresh) ══

CREATE TABLE IF NOT EXISTS agg_market_daily (
    hotel_id          INTEGER NOT NULL,
    date              TEXT NOT NULL,
    room_type         TEXT DEFAULT '',
    board             TEXT DEFAULT '',
    avg_price         REAL NOT NULL,
    min_price         REAL NOT NULL,
    max_price         REAL NOT NULL,
    observation_count INTEGER DEFAULT 0,
    providers         TEXT DEFAULT '',
    computed_at       TEXT NOT NULL,
    UNIQUE(hotel_id, date, room_type, board)
);
CREATE INDEX IF NOT EXISTS idx_amd_hotel_date ON agg_market_daily(hotel_id, date);

CREATE TABLE IF NOT EXISTS agg_competitor_matrix (
    hotel_id            INTEGER NOT NULL,
    competitor_hotel_id INTEGER NOT NULL,
    distance_km         REAL DEFAULT 0,
    star_diff           INTEGER DEFAULT 0,
    avg_price_ratio     REAL DEFAULT 1.0,
    market_pressure     REAL DEFAULT 0.0,
    computed_at         TEXT NOT NULL,
    UNIQUE(hotel_id, competitor_hotel_id)
);

-- ══ Layer 3: Real-Time Signals & Zones (every 3h) ══

CREATE TABLE IF NOT EXISTS daily_signals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id        INTEGER NOT NULL,
    hotel_id         INTEGER NOT NULL,
    signal_date      TEXT NOT NULL,
    t_value          INTEGER NOT NULL,
    predicted_price  REAL NOT NULL,
    daily_change_pct REAL DEFAULT 0,
    signal           TEXT NOT NULL CHECK(signal IN ('CALL','PUT','NEUTRAL')),
    confidence       REAL DEFAULT 0.5,
    enrichment_json  TEXT DEFAULT '{}',
    computed_at      TEXT NOT NULL,
    UNIQUE(detail_id, signal_date)
);
CREATE INDEX IF NOT EXISTS idx_ds_hotel_date ON daily_signals(hotel_id, signal_date);
CREATE INDEX IF NOT EXISTS idx_ds_detail ON daily_signals(detail_id, signal_date);

CREATE TABLE IF NOT EXISTS demand_zones (
    zone_id      TEXT PRIMARY KEY,
    hotel_id     INTEGER NOT NULL,
    category     TEXT DEFAULT '',
    zone_type    TEXT NOT NULL CHECK(zone_type IN ('SUPPORT','RESISTANCE')),
    price_lower  REAL NOT NULL,
    price_upper  REAL NOT NULL,
    touch_count  INTEGER DEFAULT 0,
    strength     REAL DEFAULT 0.5,
    first_touch  TEXT DEFAULT '',
    last_touch   TEXT DEFAULT '',
    is_broken    INTEGER DEFAULT 0,
    computed_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dz_hotel ON demand_zones(hotel_id, is_broken);

CREATE TABLE IF NOT EXISTS structure_breaks (
    break_id       TEXT PRIMARY KEY,
    hotel_id       INTEGER NOT NULL,
    category       TEXT DEFAULT '',
    break_type     TEXT NOT NULL CHECK(break_type IN ('BOS','CHOCH')),
    break_date     TEXT NOT NULL,
    break_price    REAL NOT NULL,
    previous_level REAL DEFAULT 0,
    direction      TEXT NOT NULL CHECK(direction IN ('BULLISH','BEARISH')),
    significance   REAL DEFAULT 0.5,
    computed_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sb_hotel ON structure_breaks(hotel_id, break_date);

CREATE TABLE IF NOT EXISTS trade_setups (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id           INTEGER NOT NULL,
    hotel_id            INTEGER NOT NULL,
    setup_type          TEXT DEFAULT 'primary',
    entry_price         REAL NOT NULL,
    entry_t             INTEGER DEFAULT 0,
    entry_date          TEXT DEFAULT '',
    stop_loss           REAL NOT NULL,
    stop_distance_pct   REAL DEFAULT 0,
    take_profit         REAL NOT NULL,
    target_distance_pct REAL DEFAULT 0,
    risk_reward_ratio   REAL DEFAULT 0,
    position_size       INTEGER DEFAULT 1,
    max_risk_usd        REAL DEFAULT 0,
    signal              TEXT NOT NULL,
    confidence          REAL DEFAULT 0.5,
    setup_quality       TEXT DEFAULT 'medium',
    reason_json         TEXT DEFAULT '{}',
    computed_at         TEXT NOT NULL,
    UNIQUE(detail_id, setup_type)
);
CREATE INDEX IF NOT EXISTS idx_ts_hotel ON trade_setups(hotel_id);
CREATE INDEX IF NOT EXISTS idx_ts_signal ON trade_setups(signal);

CREATE TABLE IF NOT EXISTS trade_journal (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    detail_id           INTEGER NOT NULL,
    hotel_id            INTEGER NOT NULL,
    trade_type          TEXT DEFAULT 'CALL',
    entry_price         REAL NOT NULL,
    entry_date          TEXT NOT NULL,
    entry_t             INTEGER DEFAULT 0,
    exit_price          REAL,
    exit_date           TEXT,
    exit_t              INTEGER,
    position_size       INTEGER DEFAULT 1,
    pnl_usd             REAL DEFAULT 0,
    pnl_pct             REAL DEFAULT 0,
    mae_usd             REAL,
    mae_pct             REAL,
    mfe_usd             REAL,
    mfe_pct             REAL,
    signal_at_entry     TEXT DEFAULT '',
    confidence_at_entry REAL DEFAULT 0,
    exit_reason         TEXT DEFAULT '',
    notes               TEXT DEFAULT '',
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tj_hotel ON trade_journal(hotel_id);
CREATE INDEX IF NOT EXISTS idx_tj_date ON trade_journal(created_at);
"""
