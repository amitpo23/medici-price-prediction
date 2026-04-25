"""
RunReporter — single source-of-truth for per-agent run metadata.

CEO mandate 2026-04-22: 0 report files. Every agent run inserts one row
into `SalesOffice.AgentRunLog`, updates it on completion with duration +
status + summary metrics. Per-agent structured detail (e.g. VisibilityRun)
is written by each agent through the same connection.

Usage (agent-side):

    from skills._shared.run_reporter import RunReporter

    with RunReporter(
        conn,                           # existing pyodbc connection
        agent_name="visibility-truth",
        created_by="visibility-truth@local",
        summary={"hotels_checked": 0},  # initial; update via reporter.update()
    ) as reporter:
        for hotel in hotels:
            ...
            reporter.summary["hotels_checked"] += 1
            # write detail rows using reporter.run_id as FK:
            cur.execute("INSERT INTO [SalesOffice.VisibilityRun] (RunId, ...) VALUES (?, ...)",
                        reporter.run_id, ...)

    # On exit: reporter writes duration + final summary + status to AgentRunLog.
    # If an exception propagated, status='failure' + ErrorText saved.
"""
from __future__ import annotations

import json
import os
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any


class RunReporter:
    """Context manager that logs a single agent run to [SalesOffice.AgentRunLog].

    Writes once on enter (row with Status='running'), once on exit
    (duration, final status, summary). An uncaught exception flips status
    to 'failure' and stores the traceback in ErrorText.
    """

    TABLE = "[SalesOffice.AgentRunLog]"

    def __init__(
        self,
        conn: Any,
        *,
        agent_name: str,
        created_by: str | None = None,
        summary: dict | None = None,
        run_id: str | None = None,
    ) -> None:
        self.conn = conn
        self.agent_name = agent_name
        self.created_by = created_by or self._default_created_by(agent_name)
        self.summary: dict = dict(summary or {})
        self.run_id = run_id or self._generate_run_id(agent_name)
        self._started_at: datetime | None = None
        self._finished = False

    @staticmethod
    def _default_created_by(agent_name: str) -> str:
        # Env-driven — ACA sets CREATED_BY explicitly; local defaults to @local.
        env_value = os.environ.get("CREATED_BY")
        if env_value:
            return env_value
        return f"{agent_name}@local"

    @staticmethod
    def _generate_run_id(agent_name: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        short = uuid.uuid4().hex[:8]
        return f"{agent_name}_{ts}_{short}"

    # -- context manager --

    def __enter__(self) -> "RunReporter":
        self._started_at = datetime.now(timezone.utc)
        self._insert_running_row()
        return self

    def __exit__(self, exc_type, exc_value, tb) -> bool:
        if self._finished:
            return False
        duration = int((datetime.now(timezone.utc) - (self._started_at or datetime.now(timezone.utc))).total_seconds())
        if exc_type is None:
            self._finish(status="success", duration=duration, error_text=None)
        else:
            err = "".join(traceback.format_exception(exc_type, exc_value, tb))
            self._finish(status="failure", duration=duration, error_text=err)
        # Never swallow the exception — let the agent's outer handler see it.
        return False

    # -- explicit finish (when the agent wants to mark 'partial' itself) --

    def mark_partial(self, error_text: str | None = None) -> None:
        duration = int((datetime.now(timezone.utc) - (self._started_at or datetime.now(timezone.utc))).total_seconds())
        self._finish(status="partial", duration=duration, error_text=error_text)

    # -- internals --

    def _insert_running_row(self) -> None:
        sql = f"""
            INSERT INTO {self.TABLE}
                (AgentName, RunId, RunTimestamp, Status, SummaryMetrics, CreatedBy)
            VALUES (?, ?, ?, 'running', ?, ?)
        """
        cur = self.conn.cursor()
        cur.execute(
            sql,
            self.agent_name,
            self.run_id,
            self._started_at,
            json.dumps(self.summary, default=str),
            self.created_by,
        )
        self.conn.commit()

    def _finish(self, *, status: str, duration: int, error_text: str | None) -> None:
        sql = f"""
            UPDATE {self.TABLE}
               SET Status         = ?,
                   DurationSeconds = ?,
                   SummaryMetrics = ?,
                   ErrorText      = ?
             WHERE RunId = ?
        """
        cur = self.conn.cursor()
        cur.execute(
            sql,
            status,
            duration,
            json.dumps(self.summary, default=str),
            error_text,
            self.run_id,
        )
        self.conn.commit()
        self._finished = True
