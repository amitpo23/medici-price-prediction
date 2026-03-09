"""HTML generation functions for the options dashboard."""
from __future__ import annotations

import json

def _generate_html(analysis: dict) -> str:
    """Generate the HTML dashboard from analysis results."""
    from src.analytics.report import generate_report
    from config.settings import DATA_DIR

    report_path = generate_report(analysis)

    # Read and return the HTML
    return report_path.read_text(encoding="utf-8")


def _html_escape(s: str) -> str:
    """Minimal HTML escaping for user-provided strings."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _generate_options_html(rows: list[dict], analysis: dict, t_days: int | None) -> str:
    """Generate a self-contained interactive HTML dashboard for options."""
    total = len(rows)
    calls = sum(1 for r in rows if r["option_signal"] == "CALL")
    puts = sum(1 for r in rows if r["option_signal"] == "PUT")
    neutrals = total - calls - puts
    run_ts = analysis.get("run_ts", "")

    # Build table rows HTML
    table_rows = []
    for r in rows:
        sig = r["option_signal"]
        chg = r["expected_change_pct"]
        lvl = r["level"]

        if sig == "CALL":
            sig_cls = "sig-call"
            sig_badge = f'<span class="badge badge-call">CALL L{lvl}</span>'
        elif sig == "PUT":
            sig_cls = "sig-put"
            sig_badge = f'<span class="badge badge-put">PUT L{lvl}</span>'
        else:
            sig_cls = "sig-neutral"
            sig_badge = '<span class="badge badge-neutral">NEUTRAL</span>'

        chg_cls = "pct-up" if chg > 0 else ("pct-down" if chg < 0 else "")
        chg_arrow = "&#9650;" if chg > 0 else ("&#9660;" if chg < 0 else "")

        q_score = r["quality_score"]
        q_cls = "q-high" if q_score >= 0.75 else ("q-med" if q_score >= 0.5 else "q-low")

        put_info = ""
        exp_drops = r.get("expected_future_drops", 0)
        if r["put_decline_count"] > 0:
            put_info = (
                f'{r["put_decline_count"]} drops, '
                f'total ${r["put_total_decline"]:.0f}, '
                f'max ${r["put_largest_decline"]:.0f}'
            )
        elif exp_drops > 0:
            put_info = f'~{exp_drops:.0f} expected drops (prob-based)'

        # Scan history cells
        s_snaps = r.get("scan_snapshots", 0)
        s_drops = r.get("scan_actual_drops", 0)
        s_rises = r.get("scan_actual_rises", 0)
        s_chg = r.get("scan_price_change", 0)
        s_chg_pct = r.get("scan_price_change_pct", 0)
        s_first = r.get("first_scan_price")
        s_latest = r.get("latest_scan_price")
        s_trend = r.get("scan_trend", "no_data")
        s_total_drop = r.get("scan_total_drop_amount", 0)
        s_total_rise = r.get("scan_total_rise_amount", 0)
        s_max_drop = r.get("scan_max_single_drop", 0)
        s_max_rise = r.get("scan_max_single_rise", 0)
        s_first_date = r.get("first_scan_date") or ""
        s_latest_date = r.get("latest_scan_date") or ""

        scan_chg_cls = "pct-up" if s_chg > 0 else ("pct-down" if s_chg < 0 else "")
        scan_chg_arrow = "&#9650;" if s_chg > 0.5 else ("&#9660;" if s_chg < -0.5 else "")
        scan_first_str = f"${s_first:,.0f}" if s_first else "-"

        # Rich Actual D/R: colored pill with drop/rise counts
        if s_snaps > 1:
            dr_title = (
                f"Since {s_first_date[:10]}: "
                f"{s_drops} drops (total ${s_total_drop:.0f}, max ${s_max_drop:.0f}) | "
                f"{s_rises} rises (total ${s_total_rise:.0f}, max ${s_max_rise:.0f})"
            )
            drop_part = f'<span class="scan-drop">{s_drops}&#9660;</span>' if s_drops else '<span class="scan-zero">0&#9660;</span>'
            rise_part = f'<span class="scan-rise">{s_rises}&#9650;</span>' if s_rises else '<span class="scan-zero">0&#9650;</span>'
            scan_hist_str = f'<span class="scan-dr" title="{dr_title}">{drop_part} {rise_part}</span>'
        else:
            scan_hist_str = '<span class="scan-nodata">-</span>'

        # Scan trend badge
        if s_trend == "down":
            trend_badge = '<span class="trend-badge trend-down">&#9660;</span>'
        elif s_trend == "up":
            trend_badge = '<span class="trend-badge trend-up">&#9650;</span>'
        elif s_trend == "stable":
            trend_badge = '<span class="trend-badge trend-stable">&#9644;</span>'
        else:
            trend_badge = ''

        # Chart icon — only show if we have >1 scan
        scan_series = r.get("scan_price_series", [])
        if len(scan_series) > 1:
            series_json = json.dumps(scan_series).replace("'", "&#39;")
            esc_hotel = _html_escape(json.dumps(r["hotel_name"]))
            det_id = r["detail_id"]
            chart_icon = (
                f'<button class="chart-btn" title="View scan price chart" '
                f"onclick='showChart({det_id}, "
                f"{esc_hotel}, "
                f"this.dataset.series)' "
                f"data-series='{series_json}'>"
                f'&#128200;</button>'
            )
        else:
            chart_icon = '<span class="chart-btn-empty" title="Not enough scan data">-</span>'

        # Market benchmark cell (hotel vs same-star avg in same city)
        mkt_avg = r.get("market_avg_price", 0)
        mkt_pressure = r.get("market_pressure", 0)
        mkt_hotels = r.get("market_competitor_hotels", 0)
        mkt_city = r.get("market_city", "")
        mkt_stars = r.get("market_stars", 0)

        # Per-source prediction cells
        fc_p = r.get("fc_price")
        fc_w = r.get("fc_weight", 0)
        fc_c = r.get("fc_confidence", 0)
        ev_adj = r.get("event_adj_total", 0)
        se_adj = r.get("season_adj_total", 0)
        dm_adj = r.get("demand_adj_total", 0)
        mo_adj = r.get("momentum_adj_total", 0)
        if fc_p is not None:
            fc_cls = "pct-up" if fc_p > r["current_price"] else ("pct-down" if fc_p < r["current_price"] else "")
            fc_chg = (fc_p - r["current_price"]) / r["current_price"] * 100 if r["current_price"] > 0 else 0
            fc_title = (
                f"FC predicted: ${fc_p:,.0f} ({fc_chg:+.1f}%) | "
                f"Weight: {fc_w:.0%} | Confidence: {fc_c:.0%} | "
                f"Adjustments: events {ev_adj:+.1f}%, season {se_adj:+.1f}%, "
                f"demand {dm_adj:+.1f}%, momentum {mo_adj:+.1f}%"
            )
            fc_cell = f'${fc_p:,.0f} <small class="{fc_cls}">({fc_chg:+.0f}%)</small>'
        else:
            fc_cls = ""
            fc_title = "No forward curve data"
            fc_cell = "-"

        hist_p = r.get("hist_price")
        hist_w = r.get("hist_weight", 0)
        hist_c = r.get("hist_confidence", 0)
        if hist_p is not None:
            hist_cls = "pct-up" if hist_p > r["current_price"] else ("pct-down" if hist_p < r["current_price"] else "")
            hist_chg = (hist_p - r["current_price"]) / r["current_price"] * 100 if r["current_price"] > 0 else 0
            hist_title = (
                f"Historical predicted: ${hist_p:,.0f} ({hist_chg:+.1f}%) | "
                f"Weight: {hist_w:.0%} | Confidence: {hist_c:.0%}"
            )
            hist_cell = f'${hist_p:,.0f} <small class="{hist_cls}">({hist_chg:+.0f}%)</small>'
        else:
            hist_cls = ""
            hist_title = "No historical pattern data for this hotel/period"
            hist_cell = '<span style="color:#94a3b8">-</span>'
        if mkt_avg and mkt_avg > 0:
            mkt_cls = "pct-up" if r["current_price"] < mkt_avg else ("pct-down" if r["current_price"] > mkt_avg else "")
            mkt_pct = (r["current_price"] - mkt_avg) / mkt_avg * 100
            mkt_arrow = "&#9660;" if mkt_pct < -1 else ("&#9650;" if mkt_pct > 1 else "")
            mkt_title = (
                f"{mkt_city} {mkt_stars}★ avg: ${mkt_avg:,.0f} | "
                f"{mkt_hotels} competitor hotels | "
                f"You are {mkt_pct:+.1f}% vs market"
            )
            mkt_str = f'{mkt_arrow} ${mkt_avg:,.0f} <small>({mkt_pct:+.0f}%)</small>'
        else:
            mkt_cls = ""
            mkt_title = "No market data for this hotel's city/star combo"
            mkt_str = "-"

        # ── Scan min/max from actual monitoring ──
        scan_min = r.get("scan_min_price")
        scan_max = r.get("scan_max_price")
        pred_min = r["expected_min_price"]
        pred_max = r["expected_max_price"]

        if scan_min is not None and s_snaps > 1:
            min_title = f"Scan min: ${scan_min:,.0f} (actual) | Predicted min: ${pred_min:,.0f} (FC path)"
            min_cell = f'<span class="price-dual">${scan_min:,.0f}<small class="pred-sub">pred ${pred_min:,.0f}</small></span>'
        else:
            min_title = f"Predicted min: ${pred_min:,.0f} (forward curve path)"
            min_cell = f'${pred_min:,.2f}'

        if scan_max is not None and s_snaps > 1:
            max_title = f"Scan max: ${scan_max:,.0f} (actual) | Predicted max: ${pred_max:,.0f} (FC path)"
            max_cell = f'<span class="price-dual">${scan_max:,.0f}<small class="pred-sub">pred ${pred_max:,.0f}</small></span>'
        else:
            max_title = f"Predicted max: ${pred_max:,.0f} (forward curve path)"
            max_cell = f'${pred_max:,.2f}'

        # ── Source detail JSON for popup ──
        src_detail = {
            "method": r.get("prediction_method", ""),
            "signals": [],
            "adjustments": {"events": ev_adj, "season": se_adj, "demand": dm_adj, "momentum": mo_adj},
            "factors": r.get("explanation_factors", []),
        }
        if fc_p is not None:
            src_detail["signals"].append({
                "source": "Forward Curve", "price": fc_p, "weight": fc_w,
                "confidence": fc_c, "reasoning": r.get("fc_reasoning", ""),
            })
        if hist_p is not None:
            src_detail["signals"].append({
                "source": "Historical Pattern", "price": hist_p, "weight": hist_w,
                "confidence": hist_c, "reasoning": r.get("hist_reasoning", ""),
            })
        ml_p = r.get("ml_price")
        if ml_p is not None:
            src_detail["signals"].append({
                "source": "ML Forecast", "price": ml_p, "weight": 0,
                "confidence": 0, "reasoning": r.get("ml_reasoning", ""),
            })
        src_json = json.dumps(src_detail).replace("'", "&#39;").replace('"', "&quot;")

        # ── Chart + Sources combined cell ──
        if len(scan_series) > 1:
            chart_cell = (
                f'<button class="chart-btn" title="Scan price chart" '
                f"onclick='showChart({det_id}, "
                f"{esc_hotel}, "
                f"this.dataset.series)' "
                f"data-series='{series_json}'>"
                f'&#128200;</button>'
                f'<button class="src-btn" title="Source detail" '
                f'onclick="showSources(this)" '
                f'data-sources="{src_json}" '
                f'data-hotel="{_html_escape(r["hotel_name"])}" '
                f'data-detail-id="{r["detail_id"]}">'
                f'&#128269;</button>'
            )
        else:
            chart_cell = (
                f'<button class="src-btn" title="Source detail" '
                f'onclick="showSources(this)" '
                f'data-sources="{src_json}" '
                f'data-hotel="{_html_escape(r["hotel_name"])}" '
                f'data-detail-id="{r["detail_id"]}">'
                f'&#128269;</button>'
            )

        # ── AI Intelligence cell ──
        ai_risk_data = r.get("ai_risk", {})
        ai_anomaly_data = r.get("ai_anomaly", {})
        ai_conviction = r.get("ai_conviction", "")
        ai_risk_level = ai_risk_data.get("risk_level", "")
        ai_risk_score = ai_risk_data.get("risk_score", 0)
        ai_is_anomaly = ai_anomaly_data.get("is_anomaly", False)
        ai_anomaly_type = ai_anomaly_data.get("anomaly_type", "")
        ai_anomaly_sev = ai_anomaly_data.get("severity", "none")

        # Build AI badge
        risk_cls_map = {"low": "ai-low", "medium": "ai-med", "high": "ai-high", "extreme": "ai-ext"}
        ai_risk_cls = risk_cls_map.get(ai_risk_level, "ai-low")
        ai_title_parts = [f"Risk: {ai_risk_level} ({ai_risk_score:.0%})"]
        if ai_conviction:
            ai_title_parts.append(f"Conviction: {ai_conviction}")
        if ai_is_anomaly:
            ai_title_parts.append(f"Anomaly: {ai_anomaly_type} ({ai_anomaly_sev})")
        ai_title = " | ".join(ai_title_parts)

        ai_badge = f'<span class="ai-badge {ai_risk_cls}" title="{ai_title}">'
        ai_badge += f'{ai_risk_level[:3].upper()}'
        if ai_is_anomaly:
            ai_badge += f' <span class="ai-anomaly-dot" title="{ai_anomaly_type}: {ai_anomaly_data.get("explanation", "")}">&#9888;</span>'
        ai_badge += '</span>'

        table_rows.append(
            f'<tr class="{sig_cls}" '
            f'data-signal="{sig}" '
            f'data-hotel="{_html_escape(r["hotel_name"])}" '
            f'data-category="{_html_escape(r["category"])}" '
            f'data-change="{chg}" '
            f'data-detail-id="{r["detail_id"]}" '
            f'data-current-price="{r["current_price"]}">'
            f'<td class="col-id sticky-col sc-id"><button class="expand-btn" id="eb-{r["detail_id"]}" onclick="toggleDetail({r["detail_id"]})" title="Expand trading chart">&#9660;</button> {r["detail_id"]}</td>'
            f'<td class="col-hotel sticky-col sc-hotel" title="{_html_escape(r["hotel_name"])}">{_html_escape(r["hotel_name"][:30])}</td>'
            f'<td>{_html_escape(r["category"])}</td>'
            f'<td>{_html_escape(r["board"])}</td>'
            f'<td>{_html_escape(str(r["date_from"] or ""))}</td>'
            f'<td class="num">{r["days_to_checkin"] or ""}</td>'
            f'<td>{sig_badge}</td>'
            f'<td class="num">${r["current_price"]:,.2f}</td>'
            f'<td class="num">${r["predicted_checkin_price"]:,.2f}</td>'
            f'<td class="num {chg_cls}">{chg_arrow} {chg:+.1f}%</td>'
            f'<td class="num {fc_cls}" title="{fc_title}">{fc_cell}</td>'
            f'<td class="num {hist_cls}" title="{hist_title}">{hist_cell}</td>'
            f'<td class="num" title="{min_title}">{min_cell}</td>'
            f'<td class="num" title="{max_title}">{max_cell}</td>'
            f'<td class="num">{r["touches_min"]}/{r["touches_max"]}</td>'
            f'<td class="num">{r["changes_gt_20"]}</td>'
            f'<td class="num">{r["put_decline_count"]}</td>'
            f'<td><span class="q-dot {q_cls}" title="{r["quality_label"]} ({q_score:.2f})">'
            f'{r["quality_label"]}</span></td>'
            f'<td class="num">{s_snaps}</td>'
            f'<td class="num">{scan_first_str}</td>'
            f'<td class="scan-col">{scan_hist_str}</td>'
            f'<td class="num {scan_chg_cls}" title="drop ${s_total_drop:.0f} / rise ${s_total_rise:.0f}">{trend_badge} {scan_chg_arrow} {s_chg_pct:+.1f}%</td>'
            f'<td class="col-chart">{chart_cell}</td>'
            f'<td class="col-put">{put_info}</td>'
            f'<td class="num {mkt_cls}" title="{mkt_title}">{mkt_str}</td>'
            f'<td class="col-rules"><button class="rules-btn" title="Set pricing rules" '
            f'onclick="openRulesPanel(this)" '
            f'data-detail-id="{r["detail_id"]}" '
            f'data-hotel="{_html_escape(r["hotel_name"])}" '
            f'data-category="{_html_escape(r["category"])}" '
            f'data-board="{_html_escape(r["board"])}" '
            f'data-price="{r["current_price"]}" '
            f'data-signal="{sig}">'
            f'&#9881; Rules</button></td>'
            f'<td class="col-ai">{ai_badge}</td>'
            f'</tr>'
        )

# ── Detail row (empty shell — data loaded lazily via AJAX) ──
        table_rows.append(
            f'<tr class="detail-row" id="detail-{r["detail_id"]}">' 
            f'<td colspan="27">'
            f'<div class="detail-panel" id="dp-{r["detail_id"]}">' 
            f'<div class="detail-chart-wrap">'
            f'<div class="detail-chart-title">Price Trajectory &mdash; Forward Curve + Actual Scans</div>'
            f'<canvas class="detail-canvas" id="dc-{r["detail_id"]}" width="700" height="200"></canvas>'
            f'<div class="detail-legend">'
            f'<span><span class="leg-line" style="background:#3b82f6"></span> Forward Curve</span>'
            f'<span><span class="leg-line" style="background:rgba(59,130,246,.15);height:6px"></span> Confidence Band</span>'
            f'<span><span class="leg-dot" style="background:#f97316"></span> Actual Scans</span>'
            f'<span><span class="leg-line" style="background:#10b981;height:1px;border-top:1px dashed #10b981"></span> Current $</span>'
            f'<span><span class="leg-line" style="background:#a855f7;height:1px;border-top:1px dashed #a855f7"></span> Predicted $</span>'
            f'</div></div>'
            f'<div class="detail-info-wrap" id="di-{r["detail_id"]}">' 
            f'</div></div>'
            f'</td></tr>'
        )

    rows_html = "\n".join(table_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SalesOffice Options Dashboard</title>
<style>
  :root {{
    --call: #16a34a; --call-bg: #dcfce7; --call-row: #f0fdf4;
    --put: #dc2626; --put-bg: #fee2e2; --put-row: #fef2f2;
    --neutral: #6b7280; --neutral-bg: #f3f4f6;
    --border: #e5e7eb; --header-bg: #1e293b; --header-fg: #f8fafc;
    --bg: #f8fafc; --card-bg: #fff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: #1e293b; font-size: 13px; }}

  .top-bar {{ background: var(--header-bg); color: var(--header-fg);
              padding: 14px 24px; display: flex; justify-content: space-between;
              align-items: center; }}
  .top-bar h1 {{ font-size: 18px; font-weight: 600; }}
  .top-bar .ts {{ font-size: 11px; opacity: 0.7; }}

  .cards {{ display: flex; gap: 14px; padding: 18px 24px; flex-wrap: wrap; }}
  .card {{ background: var(--card-bg); border-radius: 10px; padding: 16px 22px;
           min-width: 140px; box-shadow: 0 1px 3px rgba(0,0,0,.08);
           border-left: 4px solid var(--border); }}
  .card.c-total {{ border-left-color: #3b82f6; }}
  .card.c-call  {{ border-left-color: var(--call); }}
  .card.c-put   {{ border-left-color: var(--put); }}
  .card.c-neut  {{ border-left-color: var(--neutral); }}
  .card .num-big {{ font-size: 28px; font-weight: 700; }}
  .card .label {{ font-size: 11px; text-transform: uppercase; color: #64748b;
                  margin-top: 2px; letter-spacing: 0.5px; }}

  .controls {{ padding: 8px 24px 12px; display: flex; gap: 10px; flex-wrap: wrap;
               align-items: center; }}
  .controls input, .controls select {{ padding: 7px 12px; border: 1px solid var(--border);
    border-radius: 6px; font-size: 13px; background: #fff; }}
  .controls input {{ width: 260px; }}
  .controls select {{ min-width: 110px; }}
  .controls label {{ font-size: 12px; color: #64748b; margin-right: 2px; }}

  .table-wrap {{ overflow-x: auto; padding: 0 24px 24px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
  thead {{ background: #f1f5f9; position: sticky; top: 0; z-index: 2; }}
  th {{ padding: 10px 10px; text-align: left; font-weight: 600; font-size: 11px;
       text-transform: uppercase; letter-spacing: .4px; color: #475569;
       border-bottom: 2px solid var(--border); cursor: pointer; white-space: nowrap;
       user-select: none; }}
  th:hover {{ background: #e2e8f0; }}
  th .arrow {{ font-size: 10px; margin-left: 3px; opacity: .4; }}
  th.sorted .arrow {{ opacity: 1; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
  tr:hover {{ background: #f1f5f9; }}
  tr.sig-call {{ background: var(--call-row); }}
  tr.sig-put  {{ background: var(--put-row); }}

  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}

  .badge {{ display: inline-block; padding: 3px 9px; border-radius: 12px;
            font-size: 11px; font-weight: 600; letter-spacing: .3px; }}
  .badge-call    {{ background: var(--call-bg); color: var(--call); }}
  .badge-put     {{ background: var(--put-bg);  color: var(--put); }}
  .badge-neutral {{ background: var(--neutral-bg); color: var(--neutral); }}

  .pct-up   {{ color: var(--call); font-weight: 600; }}
  .pct-down {{ color: var(--put);  font-weight: 600; }}

  .q-dot {{ padding: 2px 8px; border-radius: 8px; font-size: 11px; font-weight: 600; }}
  .q-high {{ background: #dcfce7; color: #15803d; }}
  .q-med  {{ background: #fef9c3; color: #a16207; }}
  .q-low  {{ background: #fee2e2; color: #b91c1c; }}

  .col-hotel {{ max-width: 180px; overflow: hidden; text-overflow: ellipsis; }}

  /* ── Sticky first columns ───────────────────────────────────── */
  .sticky-col {{ position: sticky; z-index: 3; background: inherit; }}
  .sc-id {{ left: 0; min-width: 55px; }}
  .sc-hotel {{ left: 55px; min-width: 160px; border-right: 2px solid #cbd5e1; }}
  thead .sticky-col {{ z-index: 5; background: #f1f5f9; }}
  tr.sig-call .sticky-col {{ background: var(--call-row); }}
  tr.sig-put .sticky-col {{ background: var(--put-row); }}
  tr:hover .sticky-col {{ background: #f1f5f9; }}
  td.sticky-col {{ background: #fff; }}
  tr.sig-call td.sticky-col {{ background: var(--call-row); }}
  tr.sig-put td.sticky-col {{ background: var(--put-row); }}

  /* ── Source columns ─────────────────────────────────────────── */
  .src-col {{ background: #f5f3ff !important; }}
  td:nth-child(11), td:nth-child(12) {{ background: rgba(245,243,255,.45); font-size: 12px; }}
  .col-put {{ font-size: 11px; color: #64748b; max-width: 200px;
              overflow: hidden; text-overflow: ellipsis; }}
  .col-id {{ color: #94a3b8; font-size: 11px; }}
  .scan-col {{ font-size: 11px; }}

  .scan-dr {{ display: inline-flex; gap: 6px; align-items: center; }}
  .scan-drop {{ color: var(--put); font-weight: 700; font-size: 12px; }}
  .scan-rise {{ color: var(--call); font-weight: 700; font-size: 12px; }}
  .scan-zero {{ color: #94a3b8; font-size: 12px; }}
  .scan-nodata {{ color: #cbd5e1; }}

  .trend-badge {{ display: inline-block; font-size: 10px; margin-right: 2px; }}
  .trend-down {{ color: var(--put); }}
  .trend-up {{ color: var(--call); }}
  .trend-stable {{ color: #94a3b8; }}

  .chart-btn {{ background: none; border: 1px solid var(--border); border-radius: 5px;
                cursor: pointer; font-size: 14px; padding: 2px 6px; line-height: 1;
                transition: background .15s; }}
  .chart-btn:hover {{ background: #e2e8f0; }}
  .chart-btn-empty {{ color: #cbd5e1; font-size: 12px; }}
  .col-chart {{ text-align: center; }}

  /* ── Source detail button ─── */
  .src-btn {{ background: none; border: 1px solid #c7d2fe; border-radius: 5px;
              cursor: pointer; font-size: 13px; padding: 2px 5px; line-height: 1;
              transition: background .15s; margin-left: 3px; }}
  .src-btn:hover {{ background: #eef2ff; }}

  /* ── Price dual display (scan / pred) ─── */
  .price-dual {{ display: flex; flex-direction: column; line-height: 1.2; }}
  .price-dual .pred-sub {{ font-size: 9px; color: #94a3b8; }}

  /* ── Source detail modal ─── */
  .src-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                  background: rgba(0,0,0,.4); z-index: 150; justify-content: center; align-items: center; }}
  .src-overlay.open {{ display: flex; }}
  .src-box {{ background: #fff; border-radius: 14px; padding: 24px; width: 560px;
              max-width: 95vw; max-height: 85vh; overflow-y: auto;
              box-shadow: 0 12px 40px rgba(0,0,0,.3); position: relative; }}
  .src-close {{ position: absolute; top: 12px; right: 16px; font-size: 20px;
                cursor: pointer; color: #64748b; background: none; border: none; }}
  .src-close:hover {{ color: #1e293b; }}
  .src-title {{ font-size: 15px; font-weight: 700; margin-bottom: 4px; color:#1e293b; }}
  .src-subtitle {{ font-size: 11px; color:#64748b; margin-bottom: 14px; }}
  .src-signals {{ display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }}
  .src-signal {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; }}
  .src-signal-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
  .src-signal-name {{ font-weight: 700; font-size: 13px; color: #1e293b; }}
  .src-signal-price {{ font-size: 15px; font-weight: 700; }}
  .src-signal-bar {{ height: 6px; border-radius: 3px; background: #e2e8f0; margin-bottom: 4px; }}
  .src-signal-fill {{ height: 100%; border-radius: 3px; }}
  .src-signal-meta {{ font-size: 10px; color: #64748b; }}
  .src-signal-reasoning {{ font-size: 10px; color: #475569; margin-top: 4px; padding: 4px 6px;
                           background: #f1f5f9; border-radius: 4px; line-height: 1.4; }}
  .src-adj {{ margin-bottom: 16px; }}
  .src-adj h4 {{ font-size: 12px; font-weight: 700; color: #475569; margin: 0 0 8px; }}
  .src-adj-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }}
  .src-adj-item {{ background: #f1f5f9; border-radius: 8px; padding: 8px; text-align: center; }}
  .src-adj-val {{ font-size: 16px; font-weight: 700; }}
  .src-adj-val.pos {{ color: var(--call); }}
  .src-adj-val.neg {{ color: var(--put); }}
  .src-adj-label {{ font-size: 9px; color: #64748b; text-transform: uppercase; }}
  .src-factors {{ font-size: 10px; color: #64748b; margin-top: 8px; }}

  /* Modal overlay */
  .modal-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(0,0,0,.45); z-index: 100; justify-content: center;
                    align-items: center; }}
  .modal-overlay.open {{ display: flex; }}
  .modal-box {{ background: #fff; border-radius: 12px; padding: 24px; width: 680px;
                max-width: 95vw; max-height: 90vh; overflow-y: auto;
                box-shadow: 0 8px 32px rgba(0,0,0,.25); position: relative; }}
  .modal-close {{ position: absolute; top: 12px; right: 16px; font-size: 20px;
                  cursor: pointer; color: #64748b; background: none; border: none; }}
  .modal-close:hover {{ color: #1e293b; }}
  .modal-title {{ font-size: 16px; font-weight: 700; margin-bottom: 8px; color: #1e293b; }}
  .modal-subtitle {{ font-size: 12px; color: #64748b; margin-bottom: 16px; }}
  .modal-stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
  .modal-stat {{ background: #f1f5f9; border-radius: 8px; padding: 10px 14px; min-width: 90px; }}
  .modal-stat .val {{ font-size: 20px; font-weight: 700; }}
  .modal-stat .lbl {{ font-size: 10px; text-transform: uppercase; color: #64748b; }}
  .modal-stat.drop .val {{ color: var(--put); }}
  .modal-stat.rise .val {{ color: var(--call); }}

  .footer {{ text-align: center; padding: 18px; font-size: 11px; color: #94a3b8; }}

  /* ── Info-icon tooltips ─────────────────────────────────────── */
  .info-icon {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 14px; height: 14px; border-radius: 50%; background: #94a3b8;
    color: #fff; font-size: 9px; font-weight: 700; font-style: normal;
    margin-left: 4px; cursor: help; position: relative; vertical-align: middle;
    flex-shrink: 0; line-height: 1;
  }}
  .info-icon:hover {{ background: #3b82f6; }}
  .info-tip {{
    display: none; position: absolute; bottom: calc(100% + 8px); left: 50%;
    transform: translateX(-50%); width: 290px; padding: 10px 12px;
    background: #1e293b; color: #f1f5f9; font-size: 11px; font-weight: 400;
    line-height: 1.45; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,.3);
    z-index: 200; text-transform: none; letter-spacing: 0; white-space: normal;
    pointer-events: auto;
  }}
  .info-tip::after {{
    content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
    border: 6px solid transparent; border-top-color: #1e293b;
  }}
  .info-icon:hover .info-tip, .info-tip.active {{ display: block; }}
  /* Right-edge tooltips: shift left so they don't overflow */
  th:nth-child(n+18) .info-tip {{ left: auto; right: 0; transform: none; }}
  th:nth-child(n+18) .info-tip::after {{ left: auto; right: 12px; transform: none; }}
  .info-tip b {{ color: #93c5fd; }}
  .info-tip .src-tag {{ display: inline-block; background: #334155; padding: 1px 5px;
    border-radius: 3px; font-size: 10px; margin: 2px 2px 0 0; }}

  @media (max-width: 900px) {{
    .cards {{ padding: 12px; gap: 8px; }}
    .controls {{ padding: 8px 12px; }}
    .table-wrap {{ padding: 0 8px 16px; }}
    .controls input {{ width: 100%; }}
    .info-tip {{ width: 220px; }}
  }}

  /* ── Rules Column ───────────────────────────────────────────── */
  .col-rules {{ text-align: center; white-space: nowrap; }}
  .rules-btn {{
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #fff; border: none; border-radius: 6px; padding: 4px 10px;
    font-size: 11px; font-weight: 600; cursor: pointer; letter-spacing: .3px;
    transition: all .2s; display: inline-flex; align-items: center; gap: 4px;
  }}
  .rules-btn:hover {{ background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); transform: translateY(-1px); box-shadow: 0 2px 8px rgba(99,102,241,.35); }}

  /* ── AI Intelligence Column ─────────────────────────────────── */
  .col-ai {{ text-align: center; white-space: nowrap; }}
  .ai-badge {{
    display: inline-flex; align-items: center; gap: 3px;
    padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700;
    letter-spacing: .4px; border: 1.5px solid transparent;
  }}
  .ai-low {{ background: #dcfce7; color: #166534; border-color: #86efac; }}
  .ai-med {{ background: #fef9c3; color: #854d0e; border-color: #fde047; }}
  .ai-high {{ background: #fee2e2; color: #991b1b; border-color: #fca5a5; }}
  .ai-ext {{ background: #dc2626; color: #fff; border-color: #b91c1c; animation: ai-pulse 1.5s infinite; }}
  @keyframes ai-pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
  .ai-anomaly-dot {{ color: #f59e0b; font-size: 12px; cursor: help; }}
  .ai-ext .ai-anomaly-dot {{ color: #fef08a; }}

  /* ── Inline Trading Detail Row ──────────────────────────────── */
  .detail-row {{ display: none; }}
  .detail-row.open {{ display: table-row; }}
  .detail-row > td {{ padding: 0 !important; border-bottom: 2px solid #3b82f6; background: #f8fafc; }}
  .detail-panel {{
    display: flex; gap: 0; padding: 16px 20px; min-height: 220px;
    border-top: 2px solid #3b82f6;
  }}
  .detail-chart-wrap {{
    flex: 1 1 60%; min-width: 0; position: relative;
  }}
  .detail-chart-title {{
    font-size: 11px; font-weight: 700; color: #475569; margin-bottom: 6px;
    text-transform: uppercase; letter-spacing: .5px;
  }}
  .detail-canvas {{
    width: 100%; height: 200px; border: 1px solid #e2e8f0; border-radius: 8px;
    background: #fff;
  }}
  .detail-legend {{
    display: flex; gap: 14px; margin-top: 6px; font-size: 10px; color: #64748b;
  }}
  .detail-legend span {{ display: flex; align-items: center; gap: 4px; }}
  .detail-legend .leg-dot {{
    width: 8px; height: 8px; border-radius: 50%; display: inline-block;
  }}
  .detail-legend .leg-line {{
    width: 16px; height: 2px; display: inline-block; border-radius: 1px;
  }}
  .detail-info-wrap {{
    flex: 0 0 320px; padding-left: 20px; border-left: 1px solid #e2e8f0;
    display: flex; flex-direction: column; gap: 10px; overflow-y: auto; max-height: 260px;
  }}
  .detail-section {{ }}
  .detail-section h4 {{
    font-size: 10px; font-weight: 700; color: #94a3b8; text-transform: uppercase;
    letter-spacing: .6px; margin: 0 0 6px; border-bottom: 1px solid #e2e8f0; padding-bottom: 3px;
  }}
  .detail-signals {{ display: flex; flex-direction: column; gap: 4px; }}
  .detail-sig-row {{
    display: flex; align-items: center; gap: 6px; font-size: 11px;
  }}
  .detail-sig-name {{ width: 80px; font-weight: 600; color: #475569; white-space: nowrap; }}
  .detail-sig-bar {{ flex: 1; height: 10px; background: #e2e8f0; border-radius: 5px; overflow: hidden; position: relative; }}
  .detail-sig-fill {{ height: 100%; border-radius: 5px; transition: width .3s; }}
  .detail-sig-fill.fc {{ background: linear-gradient(90deg, #3b82f6, #60a5fa); }}
  .detail-sig-fill.hist {{ background: linear-gradient(90deg, #f59e0b, #fbbf24); }}
  .detail-sig-fill.ml {{ background: linear-gradient(90deg, #8b5cf6, #a78bfa); }}
  .detail-sig-val {{ font-size: 10px; color: #64748b; width: 60px; text-align: right; white-space: nowrap; }}
  .detail-adj-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
  }}
  .detail-adj-item {{
    background: #fff; border: 1px solid #e2e8f0; border-radius: 6px;
    padding: 5px 8px; text-align: center;
  }}
  .detail-adj-val {{ font-size: 13px; font-weight: 700; }}
  .detail-adj-val.pos {{ color: var(--call); }}
  .detail-adj-val.neg {{ color: var(--put); }}
  .detail-adj-val.zero {{ color: #94a3b8; }}
  .detail-adj-label {{ font-size: 8px; color: #94a3b8; text-transform: uppercase; letter-spacing: .3px; }}
  .detail-meta-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 3px; font-size: 10px;
  }}
  .detail-meta-item {{ display: flex; justify-content: space-between; padding: 2px 0; }}
  .detail-meta-key {{ color: #94a3b8; }}
  .detail-meta-val {{ font-weight: 600; color: #475569; }}
  .expand-btn {{
    background: none; border: none; cursor: pointer; font-size: 11px;
    color: #64748b; padding: 0 3px; transition: transform .2s;
  }}
  .expand-btn:hover {{ color: #3b82f6; }}
  .expand-btn.open {{ transform: rotate(180deg); }}
  @media (max-width: 900px) {{
    .detail-panel {{ flex-direction: column; }}
    .detail-info-wrap {{ flex: auto; padding-left: 0; padding-top: 12px; border-left: none; border-top: 1px solid #e2e8f0; max-height: none; }}
  }}

  /* ── Rules Modal / Panel ────────────────────────────────────── */
  .rules-overlay {{
    display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0,0,0,.5); z-index: 300; justify-content: center; align-items: flex-start;
    padding-top: 60px;
  }}
  .rules-overlay.open {{ display: flex; }}
  .rules-panel {{
    background: #fff; border-radius: 14px; padding: 0; width: 520px;
    max-width: 95vw; max-height: 80vh; overflow-y: auto;
    box-shadow: 0 12px 48px rgba(0,0,0,.3); position: relative;
  }}
  .rules-panel-header {{
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #fff; padding: 18px 24px; border-radius: 14px 14px 0 0;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .rules-panel-header h2 {{ font-size: 16px; font-weight: 700; margin: 0; }}
  .rules-panel-header .rules-close {{
    background: rgba(255,255,255,.2); border: none; color: #fff; font-size: 18px;
    cursor: pointer; border-radius: 50%; width: 28px; height: 28px;
    display: flex; align-items: center; justify-content: center;
  }}
  .rules-panel-header .rules-close:hover {{ background: rgba(255,255,255,.35); }}
  .rules-panel-body {{ padding: 20px 24px; }}

  .rules-context {{
    background: #f1f5f9; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px;
    font-size: 12px; color: #475569; line-height: 1.5;
  }}
  .rules-context .ctx-label {{ font-weight: 700; color: #1e293b; }}
  .rules-context .ctx-val {{ color: #6366f1; font-weight: 600; }}

  /* Scope selector */
  .rules-scope {{ margin-bottom: 18px; }}
  .rules-scope h3 {{ font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
  .scope-options {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .scope-opt {{
    flex: 1; min-width: 130px; padding: 10px 12px; border: 2px solid var(--border);
    border-radius: 8px; cursor: pointer; text-align: center; transition: all .15s;
    background: #fff;
  }}
  .scope-opt:hover {{ border-color: #a5b4fc; background: #eef2ff; }}
  .scope-opt.selected {{ border-color: #6366f1; background: #eef2ff; box-shadow: 0 0 0 3px rgba(99,102,241,.15); }}
  .scope-opt .scope-icon {{ font-size: 20px; display: block; margin-bottom: 4px; }}
  .scope-opt .scope-label {{ font-size: 12px; font-weight: 600; color: #1e293b; }}
  .scope-opt .scope-desc {{ font-size: 10px; color: #64748b; margin-top: 2px; }}

  /* Preset buttons */
  .rules-presets {{ margin-bottom: 18px; }}
  .rules-presets h3 {{ font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
  .preset-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }}
  .preset-card {{
    padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px;
    cursor: pointer; transition: all .15s; background: #fff; text-align: center;
  }}
  .preset-card:hover {{ border-color: #a5b4fc; background: #eef2ff; transform: translateY(-1px); }}
  .preset-card.selected {{ border-color: #6366f1; background: #eef2ff; box-shadow: 0 0 0 2px rgba(99,102,241,.2); }}
  .preset-card .preset-icon {{ font-size: 22px; display: block; margin-bottom: 2px; }}
  .preset-card .preset-name {{ font-size: 11px; font-weight: 700; color: #1e293b; }}
  .preset-card .preset-desc {{ font-size: 10px; color: #64748b; margin-top: 3px; line-height: 1.3; }}

  /* Custom rules section */
  .rules-custom {{ margin-bottom: 18px; }}
  .rules-custom h3 {{ font-size: 13px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }}
  .custom-rule-row {{
    display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
    padding: 8px 12px; background: #f8fafc; border-radius: 6px; border: 1px solid var(--border);
  }}
  .custom-rule-row label {{ font-size: 11px; font-weight: 600; color: #475569; min-width: 90px; }}
  .custom-rule-row input, .custom-rule-row select {{
    padding: 5px 8px; border: 1px solid var(--border); border-radius: 5px;
    font-size: 12px; width: 120px;
  }}
  .custom-rule-row .rule-toggle {{
    width: 36px; height: 20px; border-radius: 10px; border: none;
    background: #cbd5e1; cursor: pointer; position: relative; transition: background .2s;
  }}
  .custom-rule-row .rule-toggle.on {{ background: #6366f1; }}
  .custom-rule-row .rule-toggle::after {{
    content: ''; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px;
    border-radius: 50%; background: #fff; transition: left .2s;
  }}
  .custom-rule-row .rule-toggle.on::after {{ left: 18px; }}

  /* Action buttons */
  .rules-actions {{
    display: flex; gap: 10px; justify-content: flex-end; padding-top: 14px;
    border-top: 1px solid var(--border);
  }}
  .rules-actions button {{
    padding: 8px 20px; border-radius: 8px; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: all .15s;
  }}
  .btn-cancel {{
    background: #fff; color: #64748b; border: 1px solid var(--border);
  }}
  .btn-cancel:hover {{ background: #f1f5f9; }}
  .btn-apply {{
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: #fff; border: none;
  }}
  .btn-apply:hover {{ background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); box-shadow: 0 2px 8px rgba(99,102,241,.35); }}

  /* Toast notification */
  .rules-toast {{
    position: fixed; bottom: 24px; right: 24px; background: #1e293b; color: #f8fafc;
    padding: 12px 20px; border-radius: 10px; font-size: 13px; font-weight: 500;
    box-shadow: 0 4px 16px rgba(0,0,0,.25); z-index: 400;
    transform: translateY(80px); opacity: 0; transition: all .3s ease;
  }}
  .rules-toast.show {{ transform: translateY(0); opacity: 1; }}
  .rules-toast .toast-icon {{ margin-right: 8px; }}
</style>
</head>
<body>

<div class="top-bar">
  <h1>SalesOffice &mdash; Options Board</h1>
  <span class="ts">Last run: {_html_escape(str(run_ts))}</span>
</div>

<div class="cards">
  <div class="card c-total"><div class="num-big">{total}</div><div class="label">Total Options</div></div>
  <div class="card c-call"><div class="num-big">{calls}</div><div class="label">CALL</div></div>
  <div class="card c-put"><div class="num-big">{puts}</div><div class="label">PUT</div></div>
  <div class="card c-neut"><div class="num-big">{neutrals}</div><div class="label">Neutral</div></div>
</div>

<div class="controls">
  <label for="search">Search:</label>
  <input id="search" type="text" placeholder="Filter by hotel name, category...">
  <label for="sig-filter">Signal:</label>
  <select id="sig-filter">
    <option value="">All</option>
    <option value="CALL">CALL</option>
    <option value="PUT">PUT</option>
    <option value="NEUTRAL">NEUTRAL</option>
  </select>
  <label for="q-filter">Quality:</label>
  <select id="q-filter">
    <option value="">All</option>
    <option value="HIGH">HIGH</option>
    <option value="MEDIUM">MEDIUM</option>
    <option value="LOW">LOW</option>
  </select>
</div>

<div class="table-wrap">
<table id="opts-table">
<thead><tr>
  <th data-col="0" data-type="num" class="sticky-col sc-id">ID<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Detail ID</b><br>Unique room identifier from SalesOffice DB.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="1" data-type="str" class="sticky-col sc-hotel">Hotel<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Hotel Name</b><br>Property name from Med_Hotels table joined via HotelID.<br><span class="src-tag">Med_Hotels</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="2" data-type="str">Category<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Room Category</b><br>Mapped from RoomCategoryID: 1=Standard, 2=Superior, 4=Deluxe, 12=Suite. Affects forward-curve category offset in prediction.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="3" data-type="str">Board<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Board Type</b><br>Meal plan from BoardId: RO, BB, HB, FB, AI, etc. Adds a board offset to the forward curve prediction.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="4" data-type="str">Check-in<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Check-in Date</b><br>Booked arrival date from the order. This is the target date (T=0) for the forward curve walk.<br><span class="src-tag">SalesOffice.Orders</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="5" data-type="num">Days<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Days to Check-in</b><br>Calendar days from today to check-in. This is the T value &mdash; how many steps the forward curve walks.<br>Formula: <b>check_in_date &minus; today</b></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="6" data-type="str">Signal<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Option Signal (CALL / PUT / NEUTRAL)</b><br>&bull; <b>CALL</b>: price expected to rise (&ge;0.5%) or prob_up &gt; prob_down+0.1<br>&bull; <b>PUT</b>: price expected to drop (&le;&minus;0.5%) or prob_down &gt; prob_up+0.1<br>&bull; <b>L1-L10</b>: confidence level (65% change magnitude + 35% probability &times; quality)<br><span class="src-tag">Forward Curve 50%</span> <span class="src-tag">Historical 30%</span> <span class="src-tag">ML 20%</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="7" data-type="num">Current $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Current Room Price</b><br>Latest price from the most recent hourly scan of SalesOffice.Details. This is the starting point for the forward curve.<br><span class="src-tag">SalesOffice.Details</span> <span class="src-tag">Hourly scan</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="8" data-type="num">Predicted $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Predicted Check-in Price (Ensemble)</b><br>Weighted ensemble of 2-3 signals:<br>&bull; <b>Forward Curve (50%)</b>: day-by-day walk with decay + events + season + weather adjustments<br>&bull; <b>Historical Pattern (30%)</b>: same-month prior-year average + lead-time adjustment<br>&bull; <b>ML Model (20%)</b>: if trained model exists (currently inactive)<br>Weights are scaled by each signal's confidence then normalized.<br><span class="src-tag">SalesOffice DB</span> <span class="src-tag">Open-Meteo</span> <span class="src-tag">Events</span> <span class="src-tag">Seasonality</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="9" data-type="num">Change %<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Price Change %</b><br>Percentage difference between predicted check-in price and current price.<br>Formula: <b>(predicted &divide; current &minus; 1) &times; 100</b><br>Green = price expected to rise, Red = expected to drop.</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="10" data-type="num" class="src-col">FC $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Forward Curve Prediction</b><br>Price predicted by the <b>Forward Curve</b> model alone (weight ~50%).<br>Day-by-day random walk with:<br>&bull; Decay rate from {'{'}model_info.total_tracks{'}'} price tracks<br>&bull; Event adjustments (Miami events, holidays)<br>&bull; Season adjustments (monthly ADR patterns)<br>&bull; Demand adjustments (flight demand index)<br>&bull; Momentum adjustments (recent price trend)<br>Hover for full adjustment breakdown.<br><span class="src-tag">SalesOffice DB</span> <span class="src-tag">Events</span> <span class="src-tag">Seasonality</span> <span class="src-tag">Flights</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="11" data-type="num" class="src-col">Hist $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Historical Pattern Prediction</b><br>Price predicted by <b>Historical Patterns</b> alone (weight ~30%).<br>Same-month prior-year average price adjusted by:<br>&bull; Lead-time offset (how far from check-in)<br>&bull; Day-of-week patterns<br>&bull; Year-over-year trend<br>Only available when historical data exists for this hotel/period combination.<br><span class="src-tag">medici-db Historical</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="12" data-type="num">Min $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Minimum Price</b><br>Lowest price point on the forward curve between now and check-in.<br>Formula: <b>min(all daily predicted prices)</b><br>This is the predicted best buying opportunity in the path.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="13" data-type="num">Max $<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Maximum Price</b><br>Highest price point on the forward curve between now and check-in.<br>Formula: <b>max(all daily predicted prices)</b><br>Peak predicted price before check-in.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="14" data-type="str">Touches<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Touches Min / Max</b><br>How many times the forward curve touches the min and max price levels (within $0.01).<br>Format: <b>min_touches / max_touches</b><br>High touch count = price lingers at that level (support/resistance).</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="15" data-type="num">Big Moves<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Big Price Moves (&gt;$20)</b><br>Count of day-to-day predicted price changes greater than $20 on the forward curve.<br>More big moves = higher volatility expected.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="16" data-type="num">Exp Drops<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Expected Price Drops</b><br>Number of day-to-day drops predicted by the forward curve between now and check-in.<br>Higher count for PUT signals = more predicted decline episodes.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="17" data-type="str">Quality<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Prediction Quality Score</b><br>Blended confidence metric:<br>&bull; 60% from data availability (scan count, price history depth, hotel coverage)<br>&bull; 40% from mean signal confidence<br>Levels: <b>HIGH</b> (&ge;0.75), <b>MEDIUM</b> (&ge;0.50), <b>LOW</b> (&lt;0.50)<br>Higher = more data backing the prediction.</span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="18" data-type="num">Scans<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Scan Count (Actual)</b><br>Number of real price snapshots collected from medici-db since tracking started (Feb 23).<br>Scanned every ~3 hours. More scans = better trend visibility.<br><span class="src-tag">SalesOffice.Details.DateCreated</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="19" data-type="num">1st Price<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>First Scan Price</b><br>The room price at the earliest recorded scan. Used as baseline to measure actual price movement since tracking began.<br><span class="src-tag">SalesOffice.Details</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="20" data-type="str">Actual D/R<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Actual Drops / Rises (Observed)</b><br>Real price drops and rises observed across actual scans &mdash; NOT predictions.<br>&bull; <b style="color:#ef4444">Red number&#9660;</b> = count of scans where price decreased<br>&bull; <b style="color:#22c55e">Green number&#9650;</b> = count of scans where price increased<br>Hover for total $ amounts and max single move.<br><span class="src-tag">medici-db scans</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="21" data-type="num">Scan Chg%<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Scan Price Change %</b><br>Actual price change from first scan to current price.<br>Formula: <b>(latest &minus; first) &divide; first &times; 100</b><br>Trend badge: &#9650; up, &#9660; down, &#9644; stable.<br>This is REAL observed data, not a prediction.<br><span class="src-tag">medici-db scans</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="22" data-type="str">Chart<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Scan Price Chart</b><br>Click &#128200; to view price history chart showing all actual scan prices over time with colored dots (red=drop, green=rise).<br>Requires &ge;2 scans.</span></span></th>
  <th data-col="23" data-type="str">PUT Detail<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>PUT Decline Details</b><br>Breakdown of predicted downward moves on the forward curve:<br>&bull; <b>drops</b>: count of decline days<br>&bull; <b>total $</b>: sum of all daily drops<br>&bull; <b>max $</b>: largest single-day drop<br>Only shown for rooms with predicted declines.<br><span class="src-tag">Forward Curve</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="24" data-type="num">Mkt &#9733;$<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Market Benchmark (same &#9733; avg)</b><br>Average price of all other hotels with the <b>same star rating</b> in the <b>same city</b> from AI_Search_HotelData (8.5M records, 6K+ hotels, 323 cities).<br>&bull; <b style="color:#22c55e">Green</b>: our price &lt; market avg (well-positioned)<br>&bull; <b style="color:#ef4444">Red</b>: our price &gt; market avg (premium priced)<br>Hover for N competitor hotels and city.<br><span class="src-tag">AI_Search_HotelData</span></span></span> <span class="arrow">&#9650;</span></th>
  <th data-col="25" data-type="str">Rules<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>Pricing Rules</b><br>Set pricing rules for this room, hotel, or all hotels.<br>&bull; <b>Scope</b>: This row / This hotel / All hotels<br>&bull; <b>Presets</b>: Conservative, Moderate, Aggressive, Seasonal High, Fire Sale, Wait for Drop, Exclude AI<br>&bull; <b>Custom</b>: Price ceiling/floor, markup %, target price, category/board exclusions<br>Rules are applied at Step 5 (Flatten &amp; Group) of the SalesOffice scanning pipeline.<br><span class="src-tag">Rules Engine</span></span></span></th>
  <th data-col="26" data-type="str">AI<span class="info-icon" onclick="toggleTip(this, event)">i<span class="info-tip"><b>AI Intelligence</b><br>Claude-powered risk assessment and anomaly detection.<br>&bull; <b style="color:#22c55e">LOW</b>: Standard conditions, low risk<br>&bull; <b style="color:#f59e0b">MED</b>: Moderate risk, some uncertainty<br>&bull; <b style="color:#ef4444">HIG</b>: High risk, large predicted moves or limited data<br>&bull; <b style="color:#dc2626">EXT</b>: Extreme risk, urgent review needed<br>&bull; &#9888; = Anomaly detected (spike, dip, stale, divergence)<br>Click <a href="/api/v1/salesoffice/options/ai-insights" style="color:#60a5fa">AI Insights</a> for full analysis.<br><span class="src-tag">AI Intelligence Engine</span></span></span></th>
</tr></thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>

<div class="footer">
  Medici Price Prediction &mdash; Options Dashboard
  &bull; {total} rows
  &bull; T={t_days or "all"} days
  &bull; <a href="/api/v1/salesoffice/options?profile=lite" style="color:#3b82f6">JSON API</a>
  &bull; <a href="/api/v1/salesoffice/options/legend" style="color:#3b82f6">Legend</a>
  &bull; <a href="/api/v1/salesoffice/options/ai-insights" style="color:#a78bfa">&#129302; AI Insights</a>
</div>

<!-- Scan Chart Modal -->
<div id="chart-modal" class="modal-overlay">
  <div class="modal-box">
    <button class="modal-close" onclick="closeChart()">&times;</button>
    <div class="modal-title" id="chart-title"></div>
    <div class="modal-subtitle" id="chart-subtitle"></div>
    <div class="modal-stats" id="chart-stats"></div>
    <canvas id="chart-canvas" width="620" height="260" style="width:100%;border:1px solid #e5e7eb;border-radius:8px"></canvas>
  </div>
</div>

<!-- Source Detail Modal -->
<div id="src-overlay" class="src-overlay">
  <div class="src-box">
    <button class="src-close" onclick="closeSources()">&times;</button>
    <div class="src-title" id="src-title">Prediction Sources</div>
    <div class="src-subtitle" id="src-subtitle"></div>
    <div class="src-signals" id="src-signals"></div>
    <div class="src-adj">
      <h4>&#128200; Forward Curve Adjustments</h4>
      <div class="src-adj-grid" id="src-adjustments"></div>
    </div>
    <div class="src-factors" id="src-factors" style="display:none"></div>
  </div>
</div>

<!-- Rules Panel Modal -->
<div id="rules-overlay" class="rules-overlay">
  <div class="rules-panel">
    <div class="rules-panel-header">
      <h2>&#9881; Pricing Rules</h2>
      <button class="rules-close" onclick="closeRulesPanel()">&times;</button>
    </div>
    <div class="rules-panel-body">
      <!-- Context info -->
      <div class="rules-context" id="rules-context">
        <span class="ctx-label">Room:</span> <span class="ctx-val" id="rc-room">-</span> &nbsp;|&nbsp;
        <span class="ctx-label">Hotel:</span> <span class="ctx-val" id="rc-hotel">-</span> &nbsp;|&nbsp;
        <span class="ctx-label">Price:</span> <span class="ctx-val" id="rc-price">-</span> &nbsp;|&nbsp;
        <span class="ctx-label">Signal:</span> <span class="ctx-val" id="rc-signal">-</span>
      </div>

      <!-- Scope selector -->
      <div class="rules-scope">
        <h3>&#127919; Apply Scope</h3>
        <div class="scope-options">
          <div class="scope-opt selected" data-scope="row" onclick="selectScope(this)">
            <span class="scope-icon">&#128196;</span>
            <span class="scope-label">This Room</span>
            <span class="scope-desc">Only this specific room option</span>
          </div>
          <div class="scope-opt" data-scope="hotel" onclick="selectScope(this)">
            <span class="scope-icon">&#127976;</span>
            <span class="scope-label" id="scope-hotel-label">This Hotel</span>
            <span class="scope-desc">All rooms for this hotel</span>
          </div>
          <div class="scope-opt" data-scope="all" onclick="selectScope(this)">
            <span class="scope-icon">&#127758;</span>
            <span class="scope-label">All Hotels</span>
            <span class="scope-desc">Apply to every hotel</span>
          </div>
        </div>
      </div>

      <!-- Preset selection -->
      <div class="rules-presets">
        <h3>&#9889; Quick Presets</h3>
        <div class="preset-grid">
          <div class="preset-card" data-preset="conservative" onclick="selectPreset(this)">
            <span class="preset-icon">&#128737;</span>
            <span class="preset-name">Conservative</span>
            <span class="preset-desc">Low markup, tight ceiling, safe floor</span>
          </div>
          <div class="preset-card" data-preset="moderate" onclick="selectPreset(this)">
            <span class="preset-icon">&#9878;</span>
            <span class="preset-name">Moderate</span>
            <span class="preset-desc">Balanced markup with reasonable bounds</span>
          </div>
          <div class="preset-card" data-preset="aggressive" onclick="selectPreset(this)">
            <span class="preset-icon">&#128640;</span>
            <span class="preset-name">Aggressive</span>
            <span class="preset-desc">Higher markup, wider price range</span>
          </div>
          <div class="preset-card" data-preset="seasonal_high" onclick="selectPreset(this)">
            <span class="preset-icon">&#9728;</span>
            <span class="preset-name">Seasonal High</span>
            <span class="preset-desc">Peak season premium pricing</span>
          </div>
          <div class="preset-card" data-preset="fire_sale" onclick="selectPreset(this)">
            <span class="preset-icon">&#128293;</span>
            <span class="preset-name">Fire Sale</span>
            <span class="preset-desc">Deep discount, move inventory fast</span>
          </div>
          <div class="preset-card" data-preset="wait_for_drop" onclick="selectPreset(this)">
            <span class="preset-icon">&#9202;</span>
            <span class="preset-name">Wait for Drop</span>
            <span class="preset-desc">Hold until price drops below threshold</span>
          </div>
          <div class="preset-card" data-preset="exclude_ai" onclick="selectPreset(this)">
            <span class="preset-icon">&#128683;</span>
            <span class="preset-name">Exclude AI</span>
            <span class="preset-desc">No AI pricing &mdash; use supplier price</span>
          </div>
        </div>
      </div>

      <!-- Custom rules -->
      <div class="rules-custom">
        <h3>&#128295; Custom Rules</h3>
        <div class="custom-rule-row">
          <label>Price Ceiling</label>
          <input type="number" id="rule-ceiling" placeholder="Max price $" step="1">
          <span style="font-size:11px;color:#64748b">Maximum allowed price</span>
        </div>
        <div class="custom-rule-row">
          <label>Price Floor</label>
          <input type="number" id="rule-floor" placeholder="Min price $" step="1">
          <span style="font-size:11px;color:#64748b">Minimum allowed price</span>
        </div>
        <div class="custom-rule-row">
          <label>Markup %</label>
          <input type="number" id="rule-markup" placeholder="e.g. 5" step="0.5" min="-50" max="100">
          <span style="font-size:11px;color:#64748b">Add/subtract % from predicted</span>
        </div>
        <div class="custom-rule-row">
          <label>Target Price</label>
          <input type="number" id="rule-target" placeholder="Override price $" step="1">
          <span style="font-size:11px;color:#64748b">Force a specific price</span>
        </div>
      </div>

      <!-- Summary of what will be applied -->
      <div id="rules-summary" style="display:none; background:#eef2ff; border-radius:8px; padding:12px 16px; margin-bottom:14px; font-size:12px; color:#4338ca; border:1px solid #c7d2fe;">
        <strong>&#9989; Rules to apply:</strong> <span id="rules-summary-text"></span>
      </div>

      <!-- Actions -->
      <div class="rules-actions">
        <button class="btn-cancel" onclick="closeRulesPanel()">Cancel</button>
        <button class="btn-apply" onclick="applyRules()">&#9889; Apply Rules</button>
      </div>
    </div>
  </div>
</div>

<!-- Toast notification -->
<div id="rules-toast" class="rules-toast">
  <span class="toast-icon">&#9989;</span> <span id="toast-msg">Rules applied</span>
</div>

<script>
/* ── Info-tip click toggle (global) ──────────────────────── */
function toggleTip(el, e) {{
  if (!e) e = window.event;
  /* If clicked on the tooltip text itself, stop propagation and return (don't close) */
  if (e && e.target && e.target.closest && e.target.closest('.info-tip')) {{
    if (e.stopPropagation) e.stopPropagation();
    return;
  }}
  var tip = el.querySelector('.info-tip');
  if (!tip) return;
  var isOpen = tip.classList.contains('active');
  document.querySelectorAll('.info-tip.active').forEach(function(t) {{ t.classList.remove('active'); }});
  if (!isOpen) tip.classList.add('active');
  if (e && e.stopPropagation) e.stopPropagation();
}}
document.addEventListener('click', function() {{
  document.querySelectorAll('.info-tip.active').forEach(function(t) {{ t.classList.remove('active'); }});
}});

(function() {{
  const table = document.getElementById('opts-table');
  const tbody = table.querySelector('tbody');
  const headers = table.querySelectorAll('th');
  const searchBox = document.getElementById('search');
  const sigFilter = document.getElementById('sig-filter');
  const qFilter = document.getElementById('q-filter');

  // Sort
  let sortCol = -1, sortAsc = true;
  headers.forEach(th => {{
    th.addEventListener('click', function(e) {{
      if (e.target.closest('.info-icon')) return;   /* skip sort when clicking info */
      const col = parseInt(this.dataset.col);
      const type = this.dataset.type;
      if (sortCol === col) {{ sortAsc = !sortAsc; }} else {{ sortCol = col; sortAsc = true; }}
      headers.forEach(h => h.classList.remove('sorted'));
      this.classList.add('sorted');
      const arrow = this.querySelector('.arrow');
      if (arrow) arrow.innerHTML = sortAsc ? '&#9650;' : '&#9660;';

      const rowsArr = Array.from(tbody.querySelectorAll('tr'));
      rowsArr.sort((a, b) => {{
        let av = a.children[col].textContent.trim();
        let bv = b.children[col].textContent.trim();
        if (type === 'num') {{
          av = parseFloat(av.replace(/[$,%,\\s,\\u25B2,\\u25BC,\\u2594]/g, '')) || 0;
          bv = parseFloat(bv.replace(/[$,%,\\s,\\u25B2,\\u25BC,\\u2594]/g, '')) || 0;
          return sortAsc ? av - bv : bv - av;
        }}
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      }});
      rowsArr.forEach(r => tbody.appendChild(r));
    }});
  }});

  // Filter
  function applyFilters() {{
    const q = searchBox.value.toLowerCase();
    const sig = sigFilter.value;
    const qual = qFilter.value;
    const allRows = tbody.querySelectorAll('tr');
    allRows.forEach(r => {{
      const text = r.textContent.toLowerCase();
      const rSig = r.dataset.signal || '';
      const rQual = r.querySelector('.q-dot') ? r.querySelector('.q-dot').textContent.trim() : '';
      const matchQ = !q || text.includes(q);
      const matchSig = !sig || rSig === sig;
      const matchQual = !qual || rQual === qual;
      r.style.display = (matchQ && matchSig && matchQual) ? '' : 'none';
    }});
  }}
  searchBox.addEventListener('input', applyFilters);
  sigFilter.addEventListener('change', applyFilters);
  qFilter.addEventListener('change', applyFilters);
}})();

/* ── Chart Modal Functions ──────────────────────────────────────── */
function showChart(detailId, hotelName, seriesJson) {{
  let series;
  try {{ series = JSON.parse(seriesJson); }} catch(e) {{ return; }}
  if (!series || series.length < 2) return;

  const modal = document.getElementById('chart-modal');
  const canvas = document.getElementById('chart-canvas');
  const ctx = canvas.getContext('2d');

  // Title
  document.getElementById('chart-title').textContent =
    'Scan Price History — ' + hotelName + ' (ID: ' + detailId + ')';
  document.getElementById('chart-subtitle').textContent =
    series.length + ' scans from ' + series[0].date.substring(0,10) +
    ' to ' + series[series.length-1].date.substring(0,10);

  // Stats
  const prices = series.map(s => s.price);
  const firstP = prices[0], lastP = prices[prices.length-1];
  const minP = Math.min(...prices), maxP = Math.max(...prices);
  let drops=0, rises=0;
  for (let i=1; i<prices.length; i++) {{
    if (prices[i] < prices[i-1] - 0.01) drops++;
    else if (prices[i] > prices[i-1] + 0.01) rises++;
  }}
  const chg = lastP - firstP;
  const chgPct = firstP > 0 ? (chg / firstP * 100) : 0;

  document.getElementById('chart-stats').innerHTML =
    '<div class="modal-stat"><div class="val">$' + firstP.toFixed(0) + '</div><div class="lbl">First Scan</div></div>' +
    '<div class="modal-stat"><div class="val">$' + lastP.toFixed(0) + '</div><div class="lbl">Latest</div></div>' +
    '<div class="modal-stat drop"><div class="val">' + drops + '</div><div class="lbl">Drops &#9660;</div></div>' +
    '<div class="modal-stat rise"><div class="val">' + rises + '</div><div class="lbl">Rises &#9650;</div></div>' +
    '<div class="modal-stat"><div class="val">$' + minP.toFixed(0) + '</div><div class="lbl">Min</div></div>' +
    '<div class="modal-stat"><div class="val">$' + maxP.toFixed(0) + '</div><div class="lbl">Max</div></div>' +
    '<div class="modal-stat ' + (chg < 0 ? 'drop' : 'rise') + '">' +
    '<div class="val">' + (chg >= 0 ? '+' : '') + chgPct.toFixed(1) + '%</div>' +
    '<div class="lbl">Total Change</div></div>';

  // Draw chart on canvas
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  const padL = 60, padR = 20, padT = 20, padB = 40;
  const cw = W - padL - padR, ch = H - padT - padB;
  const pRange = maxP - minP || 1;
  const n = prices.length;

  // Grid
  ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 0.5;
  for (let i=0; i<=4; i++) {{
    const y = padT + ch * i / 4;
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(padL + cw, y); ctx.stroke();
    const pLabel = maxP - (pRange * i / 4);
    ctx.fillStyle = '#94a3b8'; ctx.font = '10px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText('$' + pLabel.toFixed(0), padL - 6, y + 4);
  }}

  // X axis labels
  ctx.fillStyle = '#94a3b8'; ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(n / 6));
  for (let i=0; i<n; i+=step) {{
    const x = padL + (i / (n-1)) * cw;
    ctx.fillText(series[i].date.substring(5,10), x, H - 8);
  }}

  // Price line
  ctx.beginPath();
  ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2;
  for (let i=0; i<n; i++) {{
    const x = padL + (i / (n-1)) * cw;
    const y = padT + ch - ((prices[i] - minP) / pRange) * ch;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }}
  ctx.stroke();

  // Fill under
  const lastX = padL + cw;
  ctx.lineTo(lastX, padT + ch); ctx.lineTo(padL, padT + ch); ctx.closePath();
  ctx.fillStyle = 'rgba(59,130,246,.08)'; ctx.fill();

  // Dots on price changes
  for (let i=0; i<n; i++) {{
    const x = padL + (i / (n-1)) * cw;
    const y = padT + ch - ((prices[i] - minP) / pRange) * ch;
    let color = '#3b82f6';
    if (i > 0 && prices[i] < prices[i-1] - 0.01) color = '#dc2626';
    else if (i > 0 && prices[i] > prices[i-1] + 0.01) color = '#16a34a';
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fillStyle = color; ctx.fill();
  }}

  modal.classList.add('open');
}}

function closeChart() {{
  document.getElementById('chart-modal').classList.remove('open');
}}
document.getElementById('chart-modal').addEventListener('click', function(e) {{
  if (e.target === this) closeChart();
}});
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') {{ closeChart(); closeRulesPanel(); closeSources(); }}
}});

/* ── Inline Trading Detail Panel ────────────────────────────── */
function toggleDetail(detailId) {{
  var row = document.getElementById('detail-' + detailId);
  var btn = document.getElementById('eb-' + detailId);
  if (!row) return;
  var isOpen = row.classList.contains('open');
  if (isOpen) {{
    row.classList.remove('open');
    if (btn) btn.classList.remove('open');
  }} else {{
    row.classList.add('open');
    if (btn) btn.classList.add('open');
    // Fetch detail data lazily on first open
    if (!row.dataset.drawn) {{
      row.dataset.drawn = '1';
      var infoWrap = document.getElementById('di-' + detailId);
      if (infoWrap) infoWrap.innerHTML = '<div style="padding:20px;color:#94a3b8;font-size:12px">Loading...</div>';
      fetch('/api/v1/salesoffice/options/detail/' + detailId)
        .then(function(r) {{ return r.json(); }})
        .then(function(dd) {{
          drawTradingChart(detailId, dd);
          buildDetailInfo(detailId, dd);
        }})
        .catch(function(err) {{
          console.error('Detail fetch failed:', err);
          if (infoWrap) infoWrap.innerHTML = '<div style="padding:20px;color:#dc2626;font-size:12px">Failed to load detail data</div>';
        }});
    }}
  }}
}}

function drawTradingChart(detailId, dd) {{
  var canvas = document.getElementById('dc-' + detailId);
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var dpr = window.devicePixelRatio || 1;
  var W = canvas.clientWidth, H = canvas.clientHeight;
  canvas.width = W * dpr; canvas.height = H * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  var fc = dd.fc || [];
  var scan = dd.scan || [];
  if (fc.length === 0 && scan.length === 0) {{
    ctx.fillStyle = '#94a3b8'; ctx.font = '13px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('No chart data available', W/2, H/2);
    return;
  }}

  // Collect all prices to determine Y range
  var allP = [];
  fc.forEach(function(pt) {{ allP.push(pt.p, pt.lo, pt.hi); }});
  scan.forEach(function(pt) {{ allP.push(pt.p); }});
  allP.push(dd.cp, dd.pp);
  var minP = Math.min.apply(null, allP.filter(function(v){{return v>0;}}));
  var maxP = Math.max.apply(null, allP);
  var pPad = (maxP - minP) * 0.08 || 5;
  minP -= pPad; maxP += pPad;
  var pRange = maxP - minP || 1;

  // All dates for X axis (forward curve dates are the main timeline)
  var allDates = fc.map(function(pt){{return pt.d;}});

  // Scans are PAST data, FC is FUTURE. Scans go on the LEFT, FC on the RIGHT
  // Build a unified timeline: [scan dates] + [fc dates]
  var scanDates = scan.map(function(s){{return s.d;}});
  // Remove duplicate dates
  var seen = {{}};
  var timeline = [];
  scanDates.forEach(function(d) {{ if (!seen[d]) {{ seen[d]=1; timeline.push({{d:d, src:'scan'}}); }} }});
  allDates.forEach(function(d) {{ if (!seen[d]) {{ seen[d]=1; timeline.push({{d:d, src:'fc'}}); }} }});

  var n = timeline.length;
  if (n === 0) return;

  var padL = 56, padR = 16, padT = 14, padB = 28;
  var cw = W - padL - padR, ch = H - padT - padB;

  // Helper: date to X
  var dateIdx = {{}};
  timeline.forEach(function(t, i) {{ dateIdx[t.d] = i; }});
  function dateToX(d) {{ var idx = dateIdx[d]; return idx !== undefined ? padL + (idx / Math.max(n-1,1)) * cw : -1; }}
  function priceToY(p) {{ return padT + ch - ((p - minP) / pRange) * ch; }}

  // Background
  ctx.fillStyle = '#fafbfc'; ctx.fillRect(padL, padT, cw, ch);

  // Grid lines
  ctx.strokeStyle = '#f1f5f9'; ctx.lineWidth = 0.5;
  for (var gi=0; gi<=5; gi++) {{
    var gy = padT + ch * gi / 5;
    ctx.beginPath(); ctx.moveTo(padL, gy); ctx.lineTo(padL + cw, gy); ctx.stroke();
    var gp = maxP - (pRange * gi / 5);
    ctx.fillStyle = '#94a3b8'; ctx.font = '9px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText('$' + gp.toFixed(0), padL - 4, gy + 3);
  }}

  // X axis labels (strip #N suffixes used for uniqueness)
  ctx.fillStyle = '#94a3b8'; ctx.font = '8px sans-serif'; ctx.textAlign = 'center';
  var xStep = Math.max(1, Math.floor(n / 8));
  for (var xi=0; xi<n; xi+=xStep) {{
    var xx = padL + (xi / Math.max(n-1,1)) * cw;
    var lbl = timeline[xi].d.split('#')[0];
    ctx.fillText(lbl, xx, H - 6);
  }}

  // Vertical divider between scan period and FC period
  var firstFcDate = allDates[0];
  var divX = dateToX(firstFcDate);
  if (divX > padL + 10 && scanDates.length > 0) {{
    ctx.save();
    ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 1; ctx.setLineDash([3,3]);
    ctx.beginPath(); ctx.moveTo(divX, padT); ctx.lineTo(divX, padT+ch); ctx.stroke();
    ctx.restore();
    // Labels
    ctx.fillStyle = '#94a3b8'; ctx.font = 'bold 8px sans-serif';
    ctx.textAlign = 'right'; ctx.fillText('ACTUAL', divX - 4, padT + 10);
    ctx.textAlign = 'left'; ctx.fillText('FORECAST', divX + 4, padT + 10);
  }}

  // ── Confidence band (FC) ──
  if (fc.length > 1) {{
    ctx.beginPath();
    fc.forEach(function(pt, i) {{
      var x = dateToX(pt.d); if (x < 0) return;
      var y = priceToY(pt.hi);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }});
    for (var i=fc.length-1; i>=0; i--) {{
      var x = dateToX(fc[i].d); if (x < 0) continue;
      ctx.lineTo(x, priceToY(fc[i].lo));
    }}
    ctx.closePath();
    ctx.fillStyle = 'rgba(59,130,246,.10)'; ctx.fill();
  }}

  // ── Forward Curve line ──
  if (fc.length > 0) {{
    ctx.beginPath();
    ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2;
    var started = false;
    fc.forEach(function(pt) {{
      var x = dateToX(pt.d); if (x < 0) return;
      var y = priceToY(pt.p);
      if (!started) {{ ctx.moveTo(x, y); started = true; }} else ctx.lineTo(x, y);
    }});
    ctx.stroke();
  }}

  // ── Actual scan line ──
  if (scan.length > 1) {{
    ctx.beginPath();
    ctx.strokeStyle = '#f97316'; ctx.lineWidth = 1.5;
    var started2 = false;
    scan.forEach(function(pt) {{
      var x = dateToX(pt.d); if (x < 0) return;
      var y = priceToY(pt.p);
      if (!started2) {{ ctx.moveTo(x, y); started2 = true; }} else ctx.lineTo(x, y);
    }});
    ctx.stroke();
  }}

  // ── Scan dots ──
  scan.forEach(function(pt, i) {{
    var x = dateToX(pt.d); if (x < 0) return;
    var y = priceToY(pt.p);
    var clr = '#f97316';
    if (i > 0) {{
      if (pt.p < scan[i-1].p - 0.01) clr = '#dc2626';
      else if (pt.p > scan[i-1].p + 0.01) clr = '#16a34a';
    }}
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2);
    ctx.fillStyle = clr; ctx.fill();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 0.5; ctx.stroke();
  }});

  // ── Current price dashed line ──
  ctx.save();
  ctx.strokeStyle = '#10b981'; ctx.lineWidth = 1; ctx.setLineDash([4,3]);
  var cpY = priceToY(dd.cp);
  ctx.beginPath(); ctx.moveTo(padL, cpY); ctx.lineTo(padL+cw, cpY); ctx.stroke();
  ctx.restore();
  ctx.fillStyle = '#10b981'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('$' + dd.cp.toFixed(0), padL+cw+2, cpY+3);

  // ── Predicted price dashed line ──
  ctx.save();
  ctx.strokeStyle = '#a855f7'; ctx.lineWidth = 1; ctx.setLineDash([4,3]);
  var ppY = priceToY(dd.pp);
  ctx.beginPath(); ctx.moveTo(padL, ppY); ctx.lineTo(padL+cw, ppY); ctx.stroke();
  ctx.restore();
  ctx.fillStyle = '#a855f7'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'left';
  ctx.fillText('$' + dd.pp.toFixed(0), padL+cw+2, ppY+3);

  // ── Min/Max markers on FC ──
  if (fc.length > 0) {{
    var mnPt = fc.reduce(function(a,b){{return a.p < b.p ? a : b;}});
    var mxPt = fc.reduce(function(a,b){{return a.p > b.p ? a : b;}});
    // Min marker
    var mnX = dateToX(mnPt.d), mnY = priceToY(mnPt.p);
    if (mnX > 0) {{
      ctx.beginPath(); ctx.arc(mnX, mnY, 4, 0, Math.PI*2);
      ctx.fillStyle = '#ef4444'; ctx.fill();
      ctx.fillStyle = '#ef4444'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('$' + mnPt.p.toFixed(0), mnX, mnY + 13);
    }}
    // Max marker
    var mxX = dateToX(mxPt.d), mxY = priceToY(mxPt.p);
    if (mxX > 0) {{
      ctx.beginPath(); ctx.arc(mxX, mxY, 4, 0, Math.PI*2);
      ctx.fillStyle = '#3b82f6'; ctx.fill();
      ctx.fillStyle = '#3b82f6'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('$' + mxPt.p.toFixed(0), mxX, mxY - 8);
    }}
  }}
}}

function buildDetailInfo(detailId, dd) {{
  var wrap = document.getElementById('di-' + detailId);
  if (!wrap) return;
  var h = '';

  // ── Signal Weights ──
  h += '<div class="detail-section"><h4>Signal Weights</h4><div class="detail-signals">';
  if (dd.fcP) {{
    h += '<div class="detail-sig-row"><span class="detail-sig-name">Forward Curve</span>' +
         '<div class="detail-sig-bar"><div class="detail-sig-fill fc" style="width:' + (dd.fcW*100).toFixed(0) + '%"></div></div>' +
         '<span class="detail-sig-val">$' + dd.fcP.toFixed(0) + ' (' + (dd.fcW*100).toFixed(0) + '%)</span></div>';
  }}
  if (dd.hiP) {{
    h += '<div class="detail-sig-row"><span class="detail-sig-name">Historical</span>' +
         '<div class="detail-sig-bar"><div class="detail-sig-fill hist" style="width:' + (dd.hiW*100).toFixed(0) + '%"></div></div>' +
         '<span class="detail-sig-val">$' + dd.hiP.toFixed(0) + ' (' + (dd.hiW*100).toFixed(0) + '%)</span></div>';
  }}
  h += '</div></div>';

  // ── Adjustments ──
  var adj = dd.adj || {{}};
  h += '<div class="detail-section"><h4>FC Adjustments (cumulative %)</h4><div class="detail-adj-grid">';
  var adjItems = [
    {{k:'Events', v:adj.ev}}, {{k:'Season', v:adj.se}},
    {{k:'Demand', v:adj.dm}}, {{k:'Momentum', v:adj.mo}}
  ];
  adjItems.forEach(function(a) {{
    var cls = a.v > 0.01 ? 'pos' : (a.v < -0.01 ? 'neg' : 'zero');
    h += '<div class="detail-adj-item"><div class="detail-adj-val ' + cls + '">' +
         (a.v >= 0 ? '+' : '') + a.v.toFixed(1) + '%</div>' +
         '<div class="detail-adj-label">' + a.k + '</div></div>';
  }});
  h += '</div></div>';

  // ── Market & Signals ──
  h += '<div class="detail-section"><h4>Key Metrics</h4><div class="detail-meta-grid">';
  var sigClr = dd.sig === 'CALL' ? 'var(--call)' : (dd.sig === 'PUT' ? 'var(--put)' : 'var(--neutral)');
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Signal</span><span class="detail-meta-val" style="color:' + sigClr + '">' + dd.sig + '</span></div>';
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Change</span><span class="detail-meta-val" style="color:' + (dd.chg>=0?'var(--call)':'var(--put)') + '">' + (dd.chg>=0?'+':'') + dd.chg.toFixed(1) + '%</span></div>';
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Quality</span><span class="detail-meta-val">' + dd.q + '</span></div>';
  if (dd.mkt > 0) {{
    h += '<div class="detail-meta-item"><span class="detail-meta-key">Mkt Avg</span><span class="detail-meta-val">$' + dd.mkt.toFixed(0) + '</span></div>';
  }}
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Scans</span><span class="detail-meta-val">' + dd.scans + '</span></div>';
  h += '<div class="detail-meta-item"><span class="detail-meta-key">Actual D/R</span><span class="detail-meta-val">' +
       '<span style="color:var(--put)">' + dd.drops + '&#9660;</span> ' +
       '<span style="color:var(--call)">' + dd.rises + '&#9650;</span></span></div>';
  h += '</div></div>';

  // ── Momentum & Regime ──
  var mom = dd.mom || {{}};
  var reg = dd.reg || {{}};
  if (mom.signal || reg.regime) {{
    h += '<div class="detail-section"><h4>Momentum &amp; Regime</h4><div class="detail-meta-grid">';
    if (mom.signal) {{
      h += '<div class="detail-meta-item"><span class="detail-meta-key">Momentum</span><span class="detail-meta-val">' + mom.signal + '</span></div>';
      if (mom.velocity_24h !== undefined) {{
        h += '<div class="detail-meta-item"><span class="detail-meta-key">Velocity 24h</span><span class="detail-meta-val">' + (mom.velocity_24h >= 0 ? '+' : '') + Number(mom.velocity_24h).toFixed(1) + '%</span></div>';
      }}
    }}
    if (reg.regime) {{
      h += '<div class="detail-meta-item"><span class="detail-meta-key">Regime</span><span class="detail-meta-val">' + reg.regime + '</span></div>';
    }}
    h += '</div></div>';
  }}

  wrap.innerHTML = h;
}}

/* ── Source Detail Modal Functions ───────────────────────────── */
function showSources(btn) {{
  var raw = btn.getAttribute('data-sources');
  if (!raw) return;
  raw = raw.replace(/&quot;/g, '"').replace(/&#39;/g, "'");
  var data;
  try {{ data = JSON.parse(raw); }} catch(e) {{ console.error('src parse', e); return; }}

  var hotel = btn.getAttribute('data-hotel') || '';
  var detId = btn.getAttribute('data-detail-id') || '';

  document.getElementById('src-title').textContent = 'Prediction Sources \u2014 ' + hotel;
  document.getElementById('src-subtitle').textContent = 'ID: ' + detId + ' | Method: ' + (data.method || 'ensemble');

  /* Signals */
  var sigHtml = '';
  var colors = {{'Forward Curve':'#3b82f6', 'Historical Pattern':'#f59e0b', 'ML Forecast':'#8b5cf6'}};
  (data.signals || []).forEach(function(s) {{
    var c = colors[s.source] || '#64748b';
    var wPct = Math.round((s.weight || 0) * 100);
    var confPct = Math.round((s.confidence || 0) * 100);
    var priceCls = '';
    sigHtml += '<div class="src-signal">';
    sigHtml += '<div class="src-signal-header">';
    sigHtml += '<span class="src-signal-name" style="color:' + c + '">' + s.source + '</span>';
    sigHtml += '<span class="src-signal-price">$' + (s.price ? s.price.toFixed(0) : '-') + '</span>';
    sigHtml += '</div>';
    sigHtml += '<div class="src-signal-bar"><div class="src-signal-fill" style="width:' + wPct + '%;background:' + c + '"></div></div>';
    sigHtml += '<div class="src-signal-meta">Weight: ' + wPct + '% | Confidence: ' + confPct + '%</div>';
    if (s.reasoning) {{
      sigHtml += '<div class="src-signal-reasoning">' + s.reasoning + '</div>';
    }}
    sigHtml += '</div>';
  }});
  document.getElementById('src-signals').innerHTML = sigHtml || '<div style="color:#94a3b8">No signal data available</div>';

  /* Adjustments */
  var adj = data.adjustments || {{}};
  var adjHtml = '';
  ['events','season','demand','momentum'].forEach(function(k) {{
    var v = adj[k] || 0;
    var pct = (v * 100).toFixed(1);
    var cls = v > 0.001 ? 'pos' : (v < -0.001 ? 'neg' : '');
    adjHtml += '<div class="src-adj-item"><div class="src-adj-val ' + cls + '">' + (v >= 0 ? '+' : '') + pct + '%</div>';
    adjHtml += '<div class="src-adj-label">' + k + '</div></div>';
  }});
  document.getElementById('src-adjustments').innerHTML = adjHtml;

  /* Factors */
  var factors = data.factors || [];
  if (factors.length > 0) {{
    document.getElementById('src-factors').innerHTML = '<strong>Key factors:</strong> ' + factors.join(' &bull; ');
    document.getElementById('src-factors').style.display = '';
  }} else {{
    document.getElementById('src-factors').style.display = 'none';
  }}

  document.getElementById('src-overlay').classList.add('open');
}}

function closeSources() {{
  document.getElementById('src-overlay').classList.remove('open');
}}
document.getElementById('src-overlay').addEventListener('click', function(e) {{
  if (e.target === this) closeSources();
}});

/* ── Rules Panel Logic ──────────────────────────────────────── */
var _rulesState = {{
  detailId: null,
  hotel: '',
  category: '',
  board: '',
  price: 0,
  signal: '',
  scope: 'row',
  preset: null,
}};

function openRulesPanel(btn) {{
  _rulesState.detailId = btn.dataset.detailId;
  _rulesState.hotel = btn.dataset.hotel;
  _rulesState.category = btn.dataset.category;
  _rulesState.board = btn.dataset.board;
  _rulesState.price = parseFloat(btn.dataset.price) || 0;
  _rulesState.signal = btn.dataset.signal;
  _rulesState.scope = 'row';
  _rulesState.preset = null;

  // Fill context
  document.getElementById('rc-room').textContent = '#' + _rulesState.detailId + ' (' + _rulesState.category + ' / ' + _rulesState.board + ')';
  document.getElementById('rc-hotel').textContent = _rulesState.hotel;
  document.getElementById('rc-price').textContent = '$' + _rulesState.price.toFixed(2);
  var sigEl = document.getElementById('rc-signal');
  sigEl.textContent = _rulesState.signal;
  sigEl.style.color = _rulesState.signal === 'CALL' ? 'var(--call)' : (_rulesState.signal === 'PUT' ? 'var(--put)' : 'var(--neutral)');

  // Update hotel scope label
  document.getElementById('scope-hotel-label').textContent = _rulesState.hotel.substring(0, 20) || 'This Hotel';

  // Reset selections
  document.querySelectorAll('.scope-opt').forEach(function(el) {{ el.classList.remove('selected'); }});
  document.querySelector('.scope-opt[data-scope="row"]').classList.add('selected');
  document.querySelectorAll('.preset-card').forEach(function(el) {{ el.classList.remove('selected'); }});

  // Clear custom inputs
  document.getElementById('rule-ceiling').value = '';
  document.getElementById('rule-floor').value = '';
  document.getElementById('rule-markup').value = '';
  document.getElementById('rule-target').value = '';
  document.getElementById('rules-summary').style.display = 'none';

  document.getElementById('rules-overlay').classList.add('open');
}}

function closeRulesPanel() {{
  document.getElementById('rules-overlay').classList.remove('open');
}}

document.getElementById('rules-overlay').addEventListener('click', function(e) {{
  if (e.target === this) closeRulesPanel();
}});

function selectScope(el) {{
  document.querySelectorAll('.scope-opt').forEach(function(s) {{ s.classList.remove('selected'); }});
  el.classList.add('selected');
  _rulesState.scope = el.dataset.scope;
  updateRulesSummary();
}}

function selectPreset(el) {{
  var wasSelected = el.classList.contains('selected');
  document.querySelectorAll('.preset-card').forEach(function(c) {{ c.classList.remove('selected'); }});
  if (!wasSelected) {{
    el.classList.add('selected');
    _rulesState.preset = el.dataset.preset;
  }} else {{
    _rulesState.preset = null;
  }}
  updateRulesSummary();
}}

function updateRulesSummary() {{
  var parts = [];
  var scopeText = _rulesState.scope === 'row' ? 'Room #' + _rulesState.detailId :
                  _rulesState.scope === 'hotel' ? 'All rooms in ' + _rulesState.hotel :
                  'All hotels';

  if (_rulesState.preset) {{
    parts.push('Preset: <b>' + _rulesState.preset + '</b>');
  }}

  var ceiling = document.getElementById('rule-ceiling').value;
  var floor = document.getElementById('rule-floor').value;
  var markup = document.getElementById('rule-markup').value;
  var target = document.getElementById('rule-target').value;

  if (ceiling) parts.push('Ceiling: $' + ceiling);
  if (floor) parts.push('Floor: $' + floor);
  if (markup) parts.push('Markup: ' + markup + '%');
  if (target) parts.push('Target: $' + target);

  var summaryEl = document.getElementById('rules-summary');
  if (parts.length > 0) {{
    document.getElementById('rules-summary-text').innerHTML =
      '<b>Scope:</b> ' + scopeText + ' &nbsp;|&nbsp; ' + parts.join(' &nbsp;|&nbsp; ');
    summaryEl.style.display = 'block';
  }} else {{
    summaryEl.style.display = 'none';
  }}
}}

// Update summary when custom inputs change
['rule-ceiling', 'rule-floor', 'rule-markup', 'rule-target'].forEach(function(id) {{
  document.getElementById(id).addEventListener('input', updateRulesSummary);
}});

function applyRules() {{
  var scopeText = _rulesState.scope === 'row' ? 'Room #' + _rulesState.detailId :
                  _rulesState.scope === 'hotel' ? _rulesState.hotel :
                  'All Hotels';

  var rulesCount = 0;
  var rulesList = [];

  if (_rulesState.preset) {{
    rulesCount++;
    rulesList.push(_rulesState.preset);
  }}
  if (document.getElementById('rule-ceiling').value) {{
    rulesCount++;
    rulesList.push('ceiling=$' + document.getElementById('rule-ceiling').value);
  }}
  if (document.getElementById('rule-floor').value) {{
    rulesCount++;
    rulesList.push('floor=$' + document.getElementById('rule-floor').value);
  }}
  if (document.getElementById('rule-markup').value) {{
    rulesCount++;
    rulesList.push('markup=' + document.getElementById('rule-markup').value + '%');
  }}
  if (document.getElementById('rule-target').value) {{
    rulesCount++;
    rulesList.push('target=$' + document.getElementById('rule-target').value);
  }}

  if (rulesCount === 0) {{
    showToast('&#9888; Please select a preset or set custom rules', '#f59e0b');
    return;
  }}

  // Update button(s) in the table to show rules are set
  var targetBtns = [];
  if (_rulesState.scope === 'row') {{
    var btn = document.querySelector('.rules-btn[data-detail-id="' + _rulesState.detailId + '"]');
    if (btn) targetBtns.push(btn);
  }} else if (_rulesState.scope === 'hotel') {{
    document.querySelectorAll('.rules-btn[data-hotel="' + _rulesState.hotel.replace(/"/g, '\\\\"') + '"]').forEach(function(b) {{ targetBtns.push(b); }});
  }} else {{
    document.querySelectorAll('.rules-btn').forEach(function(b) {{ targetBtns.push(b); }});
  }}

  targetBtns.forEach(function(b) {{
    b.innerHTML = '&#9881; ' + rulesCount + ' rule' + (rulesCount > 1 ? 's' : '');
    b.style.background = 'linear-gradient(135deg, #16a34a 0%, #15803d 100%)';
    b.title = 'Active rules: ' + rulesList.join(', ') + ' | Scope: ' + scopeText;
  }});

  closeRulesPanel();
  showToast('&#9989; ' + rulesCount + ' rule' + (rulesCount > 1 ? 's' : '') + ' set for ' + scopeText, '#16a34a');

  // TODO: Wire to API  POST /api/v1/salesoffice/rules/
  // The backend connection will be wired in the next step
  console.log('Rules applied:', {{
    scope: _rulesState.scope,
    detailId: _rulesState.detailId,
    hotel: _rulesState.hotel,
    preset: _rulesState.preset,
    ceiling: document.getElementById('rule-ceiling').value,
    floor: document.getElementById('rule-floor').value,
    markup: document.getElementById('rule-markup').value,
    target: document.getElementById('rule-target').value,
  }});
}}

function showToast(msg, bgColor) {{
  var toast = document.getElementById('rules-toast');
  document.getElementById('toast-msg').innerHTML = msg;
  if (bgColor) toast.style.background = bgColor;
  toast.classList.add('show');
  setTimeout(function() {{ toast.classList.remove('show'); }}, 3000);
}}
</script>
</body>
</html>"""

