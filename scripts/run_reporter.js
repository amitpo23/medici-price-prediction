/**
 * RunReporter (Node port) — single source-of-truth for per-agent run metadata.
 *
 * Mirror of skills/_shared/run_reporter.py from medici-hotels.
 * CEO mandate 2026-04-22: 0 report files. Every agent run inserts one row
 * into [SalesOffice.AgentRunLog], updates it on completion with duration +
 * status + summary metrics.
 *
 * Usage (agent-side):
 *
 *     const RunReporter = require('./run_reporter');
 *     const reporter = new RunReporter(pool, {
 *         agentName: 'browser-scan',
 *         createdBy: process.env.CREATED_BY,        // optional
 *         summary: { venues_scanned: 0 },           // optional initial
 *     });
 *     await reporter.start();
 *     try {
 *         // ... do work ...
 *         reporter.summary.venues_scanned = N;
 *         await reporter.finish('success');
 *     } catch (err) {
 *         await reporter.finish('failure', err);
 *         throw err;
 *     }
 *
 * `pool` is an mssql ConnectionPool. We piggyback on the existing scan-DB
 * connection rather than opening a separate one.
 */

const crypto = require('crypto');

const TABLE = '[SalesOffice.AgentRunLog]';

function utcStamp() {
    return new Date().toISOString().replace(/[-:T]/g, '').replace(/\..+/, 'Z');
}

class RunReporter {
    constructor(pool, opts) {
        this.pool = pool;
        this.agentName = opts.agentName;
        this.createdBy = opts.createdBy
            || process.env.CREATED_BY
            || `${this.agentName}@local`;
        this.summary = { ...(opts.summary || {}) };
        this.runId = opts.runId
            || `${this.agentName}_${utcStamp()}_${crypto.randomBytes(4).toString('hex')}`;
        this._startedAt = null;
        this._finished = false;
    }

    async start() {
        this._startedAt = new Date();
        const sql = require('mssql');
        await this.pool.request()
            .input('agent', sql.NVarChar(100), this.agentName)
            .input('runId', sql.NVarChar(100), this.runId)
            .input('ts', sql.DateTime, this._startedAt)
            .input('summary', sql.NVarChar(sql.MAX), JSON.stringify(this.summary))
            .input('createdBy', sql.NVarChar(100), this.createdBy)
            .query(`
                INSERT INTO ${TABLE}
                    (AgentName, RunId, RunTimestamp, Status, SummaryMetrics, CreatedBy)
                VALUES (@agent, @runId, @ts, 'running', @summary, @createdBy)
            `);
    }

    async finish(status, err = null) {
        if (this._finished) return;
        const duration = Math.round((Date.now() - this._startedAt.getTime()) / 1000);
        const errorText = err
            ? (err.stack || String(err)).slice(0, 4000)
            : null;
        const sql = require('mssql');
        await this.pool.request()
            .input('status', sql.NVarChar(20), status)
            .input('duration', sql.Int, duration)
            .input('summary', sql.NVarChar(sql.MAX), JSON.stringify(this.summary))
            .input('error', sql.NVarChar(sql.MAX), errorText)
            .input('runId', sql.NVarChar(100), this.runId)
            .query(`
                UPDATE ${TABLE}
                   SET Status         = @status,
                       DurationSeconds = @duration,
                       SummaryMetrics  = @summary,
                       ErrorText       = @error
                 WHERE RunId = @runId
            `);
        this._finished = true;
    }
}

module.exports = RunReporter;
