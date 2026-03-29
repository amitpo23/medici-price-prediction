"""Real-Time Streaming Alerts — proactive alerts on price movements and model state.

Alert types:
  - BAND_BREACH: Price exits confidence band
  - REGIME_CHANGE: Room transitions to different regime
  - MOMENTUM_SHIFT: Acceleration reverses direction
  - STALE_DATA: Source hasn't updated in expected interval
  - MODEL_DEGRADATION: Rolling accuracy drops below threshold
  - SIGNAL_FLIP: CALL → PUT or PUT → CALL

Each alert type has configurable severity and suppression rules.
Deduplication: same (alert_type, detail_id) suppressed within cooldown window.

This module is READ-ONLY on predictions — it only generates alert records.
"""
from __future__ import annotations

import hashlib
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

ALERT_COOLDOWN_MINUTES = 60     # suppress duplicate alerts within this window
MAX_ALERTS_PER_SCAN = 500       # safety cap per analysis run
STALE_THRESHOLD_HOURS = 6       # data older than this → STALE_DATA alert
ACCURACY_DEGRADATION_PCT = 40   # rolling accuracy below this → MODEL_DEGRADATION
BAND_BREACH_MARGIN = 0.02       # 2% outside band = breach

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ALERTS_DB_PATH = _DB_DIR / "streaming_alerts.db"

# Alert severity levels
SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class StreamingAlert:
    """A single streaming alert."""
    alert_id: str = ""          # hash of (type + detail_id + timestamp_bucket)
    alert_type: str = ""        # BAND_BREACH, REGIME_CHANGE, etc.
    severity: str = "info"      # critical / warning / info
    detail_id: int = 0
    hotel_id: int = 0
    hotel_name: str = ""
    category: str = ""
    message: str = ""
    data: dict = field(default_factory=dict)  # alert-specific payload
    created_at: str = ""
    suppressed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AlertSummary:
    """Summary of alerts from one analysis run."""
    timestamp: str = ""
    total_generated: int = 0
    total_suppressed: int = 0
    total_new: int = 0

    by_type: dict = field(default_factory=dict)    # type → count
    by_severity: dict = field(default_factory=dict)  # severity → count

    alerts: list[StreamingAlert] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_generated": self.total_generated,
            "total_suppressed": self.total_suppressed,
            "total_new": self.total_new,
            "by_type": self.by_type,
            "by_severity": self.by_severity,
            "alerts": [a.to_dict() for a in self.alerts],
        }


# ── Database ─────────────────────────────────────────────────────────

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS alerts (
    alert_id    TEXT PRIMARY KEY,
    alert_type  TEXT NOT NULL,
    severity    TEXT DEFAULT 'info',
    detail_id   INTEGER DEFAULT 0,
    hotel_id    INTEGER DEFAULT 0,
    hotel_name  TEXT DEFAULT '',
    category    TEXT DEFAULT '',
    message     TEXT DEFAULT '',
    data_json   TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL,
    acknowledged INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_alert_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alert_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alert_time ON alerts(created_at);
"""


@contextmanager
def _get_alerts_db(db_path: Path | None = None):
    """Thread-safe connection to streaming_alerts.db."""
    path = db_path or ALERTS_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_alerts_db(db_path: Path | None = None) -> None:
    """Create alerts table if needed."""
    with _get_alerts_db(db_path) as conn:
        conn.executescript(_CREATE_TABLES)


# ── Alert Generation ─────────────────────────────────────────────────

def generate_alerts(
    analysis: dict,
    previous_analysis: dict | None = None,
    db_path: Path | None = None,
) -> AlertSummary:
    """Generate streaming alerts from current analysis.

    Args:
        analysis: Current analysis predictions.
        previous_analysis: Previous cycle's analysis (for flip/change detection).
        db_path: Optional alerts DB path.

    Returns:
        AlertSummary with generated alerts.
    """
    init_alerts_db(db_path)
    now = datetime.utcnow()
    now_str = now.isoformat() + "Z"

    summary = AlertSummary(timestamp=now_str)
    all_alerts: list[StreamingAlert] = []

    predictions = analysis.get("predictions", {})
    prev_predictions = (previous_analysis or {}).get("predictions", {})

    for detail_id, pred in predictions.items():
        try:
            hotel_id = int(pred.get("hotel_id", 0) or 0)
            hotel_name = str(pred.get("hotel_name", ""))
            category = str(pred.get("category", ""))
            current_price = float(pred.get("current_price", 0) or 0)
            signal = pred.get("option_signal", "NONE") or "NONE"

            if current_price <= 0:
                continue

            fc = pred.get("forward_curve") or []

            # 1. BAND_BREACH
            alert = _check_band_breach(
                detail_id, hotel_id, hotel_name, category,
                current_price, fc, now_str,
            )
            if alert:
                all_alerts.append(alert)

            # 2. REGIME_CHANGE
            regime_info = pred.get("regime") or {}
            regime = regime_info.get("regime", "NORMAL")
            if regime in ("VOLATILE", "STALE"):
                all_alerts.append(StreamingAlert(
                    alert_type="REGIME_CHANGE",
                    severity=SEVERITY_WARNING,
                    detail_id=int(detail_id),
                    hotel_id=hotel_id,
                    hotel_name=hotel_name,
                    category=category,
                    message=f"Regime is {regime} — predictions may be unreliable",
                    data={"regime": regime},
                    created_at=now_str,
                ))

            # 3. SIGNAL_FLIP
            prev_pred = prev_predictions.get(str(detail_id))
            if prev_pred:
                prev_signal = prev_pred.get("option_signal", "NONE") or "NONE"
                flip = _check_signal_flip(
                    int(detail_id), hotel_id, hotel_name, category,
                    prev_signal, signal, now_str,
                )
                if flip:
                    all_alerts.append(flip)

            # 4. MOMENTUM_SHIFT
            momentum = pred.get("momentum") or {}
            mom_signal = momentum.get("signal", "")
            if mom_signal in ("ACCELERATING_UP", "ACCELERATING_DOWN"):
                prev_mom = (prev_pred or {}).get("momentum", {}).get("signal", "")
                if prev_mom and prev_mom != mom_signal:
                    all_alerts.append(StreamingAlert(
                        alert_type="MOMENTUM_SHIFT",
                        severity=SEVERITY_INFO,
                        detail_id=int(detail_id),
                        hotel_id=hotel_id,
                        hotel_name=hotel_name,
                        category=category,
                        message=f"Momentum shifted: {prev_mom} → {mom_signal}",
                        data={"from": prev_mom, "to": mom_signal},
                        created_at=now_str,
                    ))

        except (ValueError, TypeError, KeyError) as exc:
            logger.debug("Alert gen skip %s: %s", detail_id, exc)
            continue

        if len(all_alerts) >= MAX_ALERTS_PER_SCAN:
            break

    # 5. STALE_DATA (system-level)
    data_quality = analysis.get("data_quality") or {}
    for source, quality in data_quality.items():
        if isinstance(quality, dict):
            freshness_hours = float(quality.get("freshness_hours", 0) or 0)
            if freshness_hours > STALE_THRESHOLD_HOURS:
                all_alerts.append(StreamingAlert(
                    alert_type="STALE_DATA",
                    severity=SEVERITY_WARNING,
                    message=f"Data source '{source}' is {freshness_hours:.1f}h old",
                    data={"source": source, "freshness_hours": freshness_hours},
                    created_at=now_str,
                ))

    # Deduplicate and persist
    summary.total_generated = len(all_alerts)
    new_alerts = _deduplicate_and_save(all_alerts, db_path)
    summary.total_new = len(new_alerts)
    summary.total_suppressed = summary.total_generated - summary.total_new
    summary.alerts = new_alerts

    # Aggregate
    for a in new_alerts:
        summary.by_type[a.alert_type] = summary.by_type.get(a.alert_type, 0) + 1
        summary.by_severity[a.severity] = summary.by_severity.get(a.severity, 0) + 1

    return summary


def get_recent_alerts(
    hours_back: int = 24,
    alert_type: str | None = None,
    severity: str | None = None,
    db_path: Path | None = None,
) -> list[StreamingAlert]:
    """Retrieve recent alerts from the database.

    Args:
        hours_back: How far back to look.
        alert_type: Filter by type (None = all).
        severity: Filter by severity (None = all).
        db_path: Optional DB path.

    Returns:
        List of StreamingAlert objects.
    """
    init_alerts_db(db_path)
    cutoff = (datetime.utcnow() - timedelta(hours=hours_back)).isoformat() + "Z"

    clauses = ["created_at >= ?"]
    params: list = [cutoff]

    if alert_type:
        clauses.append("alert_type = ?")
        params.append(alert_type)
    if severity:
        clauses.append("severity = ?")
        params.append(severity)

    where = " AND ".join(clauses)
    sql = f"SELECT * FROM alerts WHERE {where} ORDER BY created_at DESC LIMIT 200"

    with _get_alerts_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    return [_row_to_alert(dict(r)) for r in rows]


# ── Internal Helpers ─────────────────────────────────────────────────

def _check_band_breach(
    detail_id, hotel_id, hotel_name, category,
    current_price, fc, now_str,
) -> StreamingAlert | None:
    """Check if current price is outside confidence band."""
    if not fc:
        return None

    first_pt = fc[0]
    lower = float(first_pt.get("lower_bound", 0) or 0)
    upper = float(first_pt.get("upper_bound", 0) or 0)

    if lower <= 0 or upper <= 0:
        return None

    # Check breach with margin
    margin = current_price * BAND_BREACH_MARGIN
    if current_price < lower - margin:
        return StreamingAlert(
            alert_type="BAND_BREACH",
            severity=SEVERITY_CRITICAL,
            detail_id=int(detail_id),
            hotel_id=hotel_id,
            hotel_name=hotel_name,
            category=category,
            message=f"Price ${current_price:.0f} below lower band ${lower:.0f}",
            data={"price": current_price, "lower": lower, "upper": upper},
            created_at=now_str,
        )
    elif current_price > upper + margin:
        return StreamingAlert(
            alert_type="BAND_BREACH",
            severity=SEVERITY_WARNING,
            detail_id=int(detail_id),
            hotel_id=hotel_id,
            hotel_name=hotel_name,
            category=category,
            message=f"Price ${current_price:.0f} above upper band ${upper:.0f}",
            data={"price": current_price, "lower": lower, "upper": upper},
            created_at=now_str,
        )
    return None


def _check_signal_flip(
    detail_id, hotel_id, hotel_name, category,
    prev_signal, curr_signal, now_str,
) -> StreamingAlert | None:
    """Detect CALL↔PUT signal flip."""
    prev_dir = "CALL" if prev_signal in ("CALL", "STRONG_CALL") else (
        "PUT" if prev_signal in ("PUT", "STRONG_PUT") else None
    )
    curr_dir = "CALL" if curr_signal in ("CALL", "STRONG_CALL") else (
        "PUT" if curr_signal in ("PUT", "STRONG_PUT") else None
    )

    if prev_dir and curr_dir and prev_dir != curr_dir:
        return StreamingAlert(
            alert_type="SIGNAL_FLIP",
            severity=SEVERITY_CRITICAL,
            detail_id=detail_id,
            hotel_id=hotel_id,
            hotel_name=hotel_name,
            category=category,
            message=f"Signal flipped: {prev_signal} → {curr_signal}",
            data={"from": prev_signal, "to": curr_signal},
            created_at=now_str,
        )
    return None


def _make_alert_id(alert: StreamingAlert) -> str:
    """Generate dedup key for an alert."""
    # Bucket by hour for cooldown
    bucket = alert.created_at[:13] if alert.created_at else ""  # YYYY-MM-DDTHH
    raw = f"{alert.alert_type}:{alert.detail_id}:{alert.hotel_id}:{bucket}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _deduplicate_and_save(
    alerts: list[StreamingAlert],
    db_path: Path | None = None,
) -> list[StreamingAlert]:
    """Deduplicate alerts and save new ones to DB."""
    if not alerts:
        return []

    import json
    new_alerts: list[StreamingAlert] = []

    with _get_alerts_db(db_path) as conn:
        for alert in alerts:
            alert.alert_id = _make_alert_id(alert)

            # Check if already exists
            existing = conn.execute(
                "SELECT 1 FROM alerts WHERE alert_id = ?", (alert.alert_id,)
            ).fetchone()
            if existing:
                alert.suppressed = True
                continue

            conn.execute("""
                INSERT OR IGNORE INTO alerts
                (alert_id, alert_type, severity, detail_id, hotel_id,
                 hotel_name, category, message, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id, alert.alert_type, alert.severity,
                alert.detail_id, alert.hotel_id, alert.hotel_name,
                alert.category, alert.message,
                json.dumps(alert.data),
                alert.created_at,
            ))
            new_alerts.append(alert)

    return new_alerts


def _row_to_alert(row: dict) -> StreamingAlert:
    """Convert DB row to StreamingAlert."""
    import json
    data = {}
    try:
        data = json.loads(row.get("data_json", "{}") or "{}")
    except (json.JSONDecodeError, TypeError) as exc:
        logger.debug("Streaming alert data_json parse failed: %s", exc)

    return StreamingAlert(
        alert_id=row.get("alert_id", ""),
        alert_type=row.get("alert_type", ""),
        severity=row.get("severity", "info"),
        detail_id=int(row.get("detail_id", 0) or 0),
        hotel_id=int(row.get("hotel_id", 0) or 0),
        hotel_name=row.get("hotel_name", ""),
        category=row.get("category", ""),
        message=row.get("message", ""),
        data=data,
        created_at=row.get("created_at", ""),
    )
