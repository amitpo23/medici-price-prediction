"""Generate the Options Trading HTML page.

Two main sections:
  Section A: Tomorrow — daily CALL/PUT/NONE signals per active contract (ex-ante)
  Section B: Vs Expiry — 6-month drawdown/breach analytics (ex-post)
  Section C: Signal Validation — hit-rate placeholder
"""
from __future__ import annotations

from datetime import datetime

from src.analytics.options_engine import compute_next_day_signals
from src.utils.template_engine import render_template

HOTEL_NAMES: dict[int, str] = {
    66814: "Breakwater South Beach",
    854881: "citizenM Miami Brickell",
    20702: "Embassy Suites Miami Airport",
    24982: "Hilton Miami Downtown",
}


def generate_options_html(analysis: dict, expiry_data: dict) -> str:
    """Build the full Options Trading HTML page."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    signals = compute_next_day_signals(analysis)
    sec_a = _build_section_a(signals)
    sec_b = _build_section_b(expiry_data)
    sec_c = _build_section_c()
    return render_template(
        "options.html",
        now=now,
        sec_a_html=sec_a,
        sec_b_html=sec_b,
        sec_c_html=sec_c,
    )


# ── Section A: Tomorrow — CALL/PUT/NONE ──────────────────────────────

def _build_section_a(signals: list[dict]) -> str:
    if not signals:
        return """<div class="empty-state">
            <p>No active contract signals available. The analysis cache may still be warming up.</p>
        </div>"""

    calls = sum(1 for s in signals if s["recommendation"] == "CALL")
    puts  = sum(1 for s in signals if s["recommendation"] == "PUT")
    nones = sum(1 for s in signals if s["recommendation"] == "NONE")

    summary_html = f"""
    <div class="summary-bar">
        <span class="pill-call">{calls} CALL</span>
        <span class="pill-put">{puts} PUT</span>
        <span class="pill-none">{nones} NONE</span>
        <span class="summary-note">signals for {len(set(s["checkin_date"] for s in signals))} check-in dates</span>
    </div>"""

    by_hotel: dict[int, list[dict]] = {}
    for s in signals:
        hid = s["hotel_id"] or 0
        by_hotel.setdefault(hid, []).append(s)

    html = summary_html
    for hid, hotel_signals in sorted(by_hotel.items()):
        hotel_name = HOTEL_NAMES.get(hid, f"Hotel {hid}")
        h_calls = sum(1 for s in hotel_signals if s["recommendation"] == "CALL")
        h_puts  = sum(1 for s in hotel_signals if s["recommendation"] == "PUT")

        rows = ""
        for s in hotel_signals:
            rec   = s["recommendation"]
            conf  = s["confidence"]
            row_cls = (
                "row-call" if rec == "CALL" else
                "row-put"  if rec == "PUT"  else ""
            )
            sig_badge = (
                f'<span class="badge-call">{rec}</span>' if rec == "CALL" else
                f'<span class="badge-put">{rec}</span>'  if rec == "PUT"  else
                f'<span class="badge-none">{rec}</span>'
            )
            conf_cls = "conf-high" if conf == "High" else "conf-med" if conf == "Med" else "conf-low"

            exp_r = s["expected_return_1d"]
            exp_html = f'<span class="{"pos" if exp_r >= 0 else "neg"}">{exp_r:+.2f}%</span>'
            mom_cls = {
                "ACCELERATING_UP": "mom-up",
                "ACCELERATING_DOWN": "mom-down",
            }.get(s["momentum_signal"], "")
            regime_cls = {
                "VOLATILE": "reg-bad",
                "STALE": "reg-bad",
                "TRENDING_UP": "reg-up",
                "TRENDING_DOWN": "reg-down",
            }.get(s["regime"], "")

            rows += f"""<tr class="{row_cls}">
                <td class="date-cell">{s["checkin_date"]}</td>
                <td class="t-cell">{s["T"]}d</td>
                <td>{s["category"].title()}</td>
                <td>{s["board"].upper()}</td>
                <td class="price-cell">${s["S_t"]:,.0f}</td>
                <td>{exp_html}</td>
                <td class="sigma-cell">{s["sigma_1d"]:.3f}%</td>
                <td class="prob-cell">{s["P_up"]:.0f}%</td>
                <td class="prob-cell">{s["P_down"]:.0f}%</td>
                <td><span class="{mom_cls}">{s["momentum_signal"]}</span></td>
                <td><span class="{regime_cls}">{s["regime"]}</span></td>
                <td>{sig_badge}</td>
                <td class="{conf_cls}">{conf}</td>
            </tr>"""

        html += f"""
        <div class="hotel-section">
            <div class="hotel-header-row">
                <span class="hotel-title">{hotel_name}</span>
                <span class="pill-call sm">{h_calls} CALL</span>
                <span class="pill-put sm">{h_puts} PUT</span>
            </div>
            <div class="table-wrap">
            <table class="signals-table">
                <thead><tr>
                    <th>Check-in</th><th>T</th><th>Category</th><th>Board</th>
                    <th>Price</th><th>E[r_1d]</th><th>&sigma;</th>
                    <th>P_up</th><th>P_down</th>
                    <th>Momentum</th><th>Regime</th>
                    <th>Signal</th><th>Conf</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
            </div>
        </div>"""

    return html


# ── Section B: Vs Expiry ──────────────────────────────────────────────

def _build_section_b(expiry_data: dict) -> str:
    if not expiry_data:
        return """<div class="loading-panel">
            <div class="loading-icon">&#9203;</div>
            <p><strong>Historical analysis is loading in the background.</strong></p>
            <p class="dim">The 6-month expiry-relative metrics are being computed from the database.
            Refresh in ~30 seconds to see results.</p>
        </div>"""

    summaries_raw = expiry_data.get("summaries", [])
    rollups = expiry_data.get("rollups", {})

    if not summaries_raw:
        return '<p class="dim">No completed contracts found in the last 6 months.</p>'

    import pandas as pd
    summaries = pd.DataFrame(summaries_raw)

    html = ""

    for hid_key, rollup in sorted(rollups.items()):
        hid = int(hid_key)
        hotel_name = HOTEL_NAMES.get(hid, f"Hotel {hid}")
        n = rollup["total_contracts"]

        med = rollup.get("median_min_rel")
        p10 = rollup.get("p10_min_rel")
        med_str = f"{med:+.1f}%" if med is not None else "N/A"
        p10_str = f"{p10:+.1f}%" if p10 is not None else "N/A"
        insight = (
            f"Over 6 months, <strong>{rollup['pct_below_10']}%</strong> of contracts "
            f"dropped &gt;10% below their final check-in price at some point. "
            f"Median drawdown vs expiry: <strong>{med_str}</strong> &middot; "
            f"Worst 10th percentile: <strong>{p10_str}</strong>."
        )

        kpi_html = f"""
        <div class="kpi-strip">
            <div class="kpi-card"><div class="kpi-val">{n}</div><div class="kpi-label">contracts</div></div>
            <div class="kpi-card highlight-5"><div class="kpi-val">{rollup['pct_below_5']}%</div><div class="kpi-label">had day below &minus;5%</div></div>
            <div class="kpi-card highlight-10"><div class="kpi-val">{rollup['pct_below_10']}%</div><div class="kpi-label">had day below &minus;10%</div></div>
            <div class="kpi-card"><div class="kpi-val">{rollup['avg_days_below_5']:.1f}</div><div class="kpi-label">avg days below &minus;5%</div></div>
            <div class="kpi-card"><div class="kpi-val">{rollup['total_events_10']}</div><div class="kpi-label">total events at &minus;10%</div></div>
        </div>
        <p class="insight-text">{insight}</p>"""

        hotel_summ = summaries[summaries["hotel_id"] == hid]
        contract_sections = ""

        for cat, cat_grp in sorted(hotel_summ.groupby("category")):
            uid = f"exp_{hid}_{cat}"
            cnt_5  = int((cat_grp["min_rel"] <= -5.0).sum())
            cnt_10 = int((cat_grp["min_rel"] <= -10.0).sum())
            badge5  = f'<span class="badge-breach5">{cnt_5} below &minus;5%</span>' if cnt_5 else ""
            badge10 = f'<span class="badge-breach10">{cnt_10} below &minus;10%</span>' if cnt_10 else ""

            rows = ""
            for _, row in cat_grp.sort_values("checkin_date", ascending=False).iterrows():
                min_r = row["min_rel"]
                max_r = row["max_rel"]
                min_cls = "breach-10" if min_r <= -10 else "breach-5" if min_r <= -5 else "breach-0" if min_r < 0 else ""
                fallback_flag = "&#9888;" if row.get("settlement_fallback") else ""
                rows += f"""<tr>
                    <td class="date-cell">{row["checkin_date"]}</td>
                    <td>{row["board"].upper()}</td>
                    <td>${row["S_exp"]:,.0f}</td>
                    <td class="{min_cls}">{min_r:+.1f}%</td>
                    <td class="{"pos" if max_r > 0 else ""}">{max_r:+.1f}%</td>
                    <td>{row["days_below_5"]}</td>
                    <td>{row["days_below_10"]}</td>
                    <td>{row["events_below_5"]}</td>
                    <td>{row["events_below_10"]}</td>
                    <td>{row["n_scans"]}</td>
                    <td class="flag-cell">{fallback_flag}</td>
                </tr>"""

            contract_sections += f"""
            <div class="comp-row">
                <div class="comp-row-header" onclick="toggle('{uid}')">
                    <span class="comp-room">{cat.title()}</span>
                    <span class="dim">{len(cat_grp)} contracts</span>
                    <span>{badge5} {badge10}</span>
                    <span class="comp-toggle" id="arrow_{uid}">&#9654;</span>
                </div>
                <div class="comp-detail" id="{uid}" style="display:none">
                    <table class="comp-table">
                        <thead><tr>
                            <th>Check-in</th><th>Board</th><th>S_exp</th>
                            <th>Min Rel</th><th>Max Rel</th>
                            <th>Days&lt;&minus;5%</th><th>Days&lt;&minus;10%</th>
                            <th>Ev&lt;&minus;5%</th><th>Ev&lt;&minus;10%</th>
                            <th>Scans</th><th></th>
                        </tr></thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>
            </div>"""

        html += f"""
        <div class="hotel-section">
            <div class="hotel-header-row">
                <span class="hotel-title">{hotel_name}</span>
            </div>
            {kpi_html}
            {contract_sections}
        </div>"""

    return html


# ── Section C: Signal Validation ─────────────────────────────────────

def _build_section_c() -> str:
    return """
    <div class="comp-row">
        <div class="comp-row-header" onclick="toggle('validation_panel')">
            <span class="comp-room">Hit-Rate Tracking</span>
            <span class="dim">Coming soon</span>
            <span class="comp-toggle" id="arrow_validation_panel">&#9654;</span>
        </div>
        <div class="comp-detail" id="validation_panel" style="display:none">
            <div class="validation-stub">
                <p><strong>What this will show:</strong></p>
                <ul>
                    <li>For each CALL signal issued: did the price go up the next day? &rarr; hit_rate_call</li>
                    <li>For each PUT signal issued: did the price go down? &rarr; hit_rate_put</li>
                    <li>Accuracy breakdown by hotel, T-bucket, confidence level</li>
                </ul>
                <p class="dim">Requires daily signal history. Currently, signals are computed fresh on each request.
                Persistent signal storage will be added in a future update.</p>
            </div>
        </div>
    </div>"""
