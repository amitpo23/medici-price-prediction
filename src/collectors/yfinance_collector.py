"""yfinance Collector — Macro market indicators for hotel demand signals.

Pulls daily data for travel/hospitality ETFs, hotel REITs, and volatility index.
Caches in SQLite for fast reads by the chart indicators aggregator.

Indicators:
  - JETS ETF: U.S. airline industry proxy (travel demand)
  - Hotel REITs: PK, HST, RLJ, APLE (hospitality sector health)
  - VIX: CBOE Volatility Index (market uncertainty)
"""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from src.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

SYMBOLS = {
    "JETS": "JETS ETF (airline/travel demand)",
    "PK": "Park Hotels & Resorts REIT",
    "HST": "Host Hotels & Resorts REIT",
    "RLJ": "RLJ Lodging Trust REIT",
    "APLE": "Apple Hospitality REIT",
    "^VIX": "CBOE Volatility Index",
}

SQLITE_PATH = Path(os.getenv("MACRO_DB_PATH", "data/macro_indicators.db"))
TABLE_NAME = "yfinance_daily"


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            fetched_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.commit()


class YFinanceCollector(BaseCollector):
    """Collects macro market indicators from Yahoo Finance."""

    name = "yfinance"

    def __init__(self, cache=None, symbols: dict[str, str] | None = None):
        super().__init__(cache)
        self.symbols = symbols or SYMBOLS
        self.db_path = SQLITE_PATH

    def is_available(self) -> bool:
        try:
            import yfinance  # noqa: F401
            return True
        except ImportError:
            logger.warning("yfinance package not installed")
            return False

    def collect(self, months_back: int = 6, **kwargs) -> pd.DataFrame:
        """Fetch daily prices for all symbols, cache in SQLite, return DataFrame."""
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed — skipping macro indicators")
            return pd.DataFrame()

        start_date = (datetime.utcnow() - timedelta(days=months_back * 30)).strftime("%Y-%m-%d")
        end_date = datetime.utcnow().strftime("%Y-%m-%d")

        all_rows = []
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=start_date, end=end_date, auto_adjust=True)
                if hist.empty:
                    logger.debug("No data for %s", symbol)
                    continue

                for date_idx, row in hist.iterrows():
                    all_rows.append({
                        "symbol": symbol,
                        "date": date_idx.strftime("%Y-%m-%d"),
                        "open": round(row.get("Open", 0), 2),
                        "high": round(row.get("High", 0), 2),
                        "low": round(row.get("Low", 0), 2),
                        "close": round(row.get("Close", 0), 2),
                        "volume": int(row.get("Volume", 0)),
                    })
                logger.info("yfinance: %s — %d rows fetched", symbol, len(hist))
            except Exception as exc:
                logger.warning("yfinance fetch failed for %s: %s", symbol, exc)

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)
        self._save_to_sqlite(df)
        return df

    def _save_to_sqlite(self, df: pd.DataFrame) -> None:
        """Upsert rows into SQLite cache."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            _ensure_table(conn)
            for _, row in df.iterrows():
                conn.execute(f"""
                    INSERT OR REPLACE INTO {TABLE_NAME}
                        (symbol, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (row["symbol"], row["date"], row["open"], row["high"],
                      row["low"], row["close"], row["volume"]))
            conn.commit()
            logger.info("yfinance: saved %d rows to SQLite", len(df))
        finally:
            conn.close()

    def get_indicator_series(self, symbol: str, days_back: int = 180) -> list[dict]:
        """Read cached time series for a symbol. Returns [{t, v}]."""
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(str(self.db_path))
        try:
            _ensure_table(conn)
            cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            rows = conn.execute(f"""
                SELECT date, close FROM {TABLE_NAME}
                WHERE symbol = ? AND date >= ?
                ORDER BY date
            """, (symbol, cutoff)).fetchall()
            return [{"t": r[0], "v": r[1]} for r in rows]
        finally:
            conn.close()

    def get_reits_avg_series(self, days_back: int = 180) -> list[dict]:
        """Average of hotel REITs (PK, HST, RLJ, APLE). Returns [{t, v}]."""
        reit_symbols = ["PK", "HST", "RLJ", "APLE"]
        series_by_date: dict[str, list[float]] = {}

        for sym in reit_symbols:
            for point in self.get_indicator_series(sym, days_back):
                series_by_date.setdefault(point["t"], []).append(point["v"])

        return [
            {"t": date, "v": round(sum(vals) / len(vals), 2)}
            for date, vals in sorted(series_by_date.items())
            if len(vals) >= 2  # need at least 2 REITs for meaningful avg
        ]

    def get_trend(self, symbol: str, window: int = 5) -> str:
        """Get recent trend direction: 'rising', 'falling', or 'flat'."""
        series = self.get_indicator_series(symbol, days_back=window * 3)
        if len(series) < window:
            return "flat"
        recent = [p["v"] for p in series[-window:]]
        change_pct = (recent[-1] - recent[0]) / recent[0] * 100 if recent[0] else 0
        if change_pct > 1.0:
            return "rising"
        elif change_pct < -1.0:
            return "falling"
        return "flat"
