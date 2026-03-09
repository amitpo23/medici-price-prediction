"""Generate the Insights page — price up/down analysis with 3 tabs.

Tab 1: Insights — when prices go up / down, turning points, best windows
Tab 2: Days Below Today — all dates where predicted price < current price
Tab 3: Days Above Today — all dates where predicted price > current price

Optimized: renders summary rows per hotel, with collapsible detail tables
to keep the page under 500KB even with 1000+ rooms.
"""
from __future__ import annotations

from datetime import datetime

from src.utils.template_engine import render_template


def generate_insights_html(analysis: dict) -> str:
    """Build the full insights HTML page from analysis predictions."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    predictions = analysis.get("predictions", {})

    if not predictions:
        return render_template("insights.html", empty=True, now=now)

    # Group predictions by hotel, only keep rooms that have daily data
    hotels: dict[str, list[dict]] = {}
    for detail_id, pred in predictions.items():
        hotel = pred.get("hotel_name", "Unknown")
        entry = {"detail_id": detail_id, **pred}
        hotels.setdefault(hotel, []).append(entry)

    # Sort rooms within each hotel by check-in date
    for rooms in hotels.values():
        rooms.sort(key=lambda r: (r.get("date_from", ""), r.get("category", "")))

    insights_hotels = _build_insights_data(hotels)
    below_hotels = _build_comparison_data(hotels, mode="below")
    above_hotels = _build_comparison_data(hotels, mode="above")

    total_rooms = sum(len(r) for r in hotels.values())
    below_count = sum(h["total_count"] for h in below_hotels)
    above_count = sum(h["total_count"] for h in above_hotels)

    return render_template(
        "insights.html",
        empty=False,
        now=now,
        total_rooms=total_rooms,
        below_count=below_count,
        above_count=above_count,
        insights_hotels=insights_hotels,
        below_hotels=below_hotels,
        above_hotels=above_hotels,
    )


def _build_insights_data(hotels: dict[str, list[dict]]) -> list[dict]:
    """Pre-process hotel data for the Insights tab."""
    result = []
    for hotel_name, rooms in hotels.items():
        changes = [r.get("expected_change_pct", 0) or 0 for r in rooms]
        avg_change = sum(changes) / len(changes) if changes else 0
        rising = sum(1 for c in changes if c > 1)
        dropping = sum(1 for c in changes if c < -1)
        stable = len(changes) - rising - dropping

        by_date: dict[str, list[dict]] = {}
        for room in rooms:
            dt = room.get("date_from", "N/A")
            by_date.setdefault(dt, []).append(room)

        date_groups = []
        for date_from, date_rooms in by_date.items():
            days = date_rooms[0].get("days_to_checkin", 0) if date_rooms else 0
            processed = [_preprocess_insight_row(r) for r in date_rooms]
            date_groups.append({"date_from": date_from, "days": days, "rooms": processed})

        result.append({
            "name": hotel_name, "n_rooms": len(rooms),
            "avg_change": avg_change, "rising": rising,
            "dropping": dropping, "stable": stable,
            "date_groups": date_groups,
        })
    return result


def _preprocess_insight_row(room: dict) -> dict:
    """Preprocess a single room into template-friendly dict."""
    current = room.get("current_price", 0)
    predicted = room.get("predicted_checkin_price", current)
    change_pct = room.get("expected_change_pct", 0) or 0
    daily = room.get("daily", [])
    momentum = room.get("momentum", {})
    regime = room.get("regime", {})

    if change_pct > 1:
        trend_cls, trend_icon, trend_text = "trend-up", "&#9650;", f"+{change_pct:.1f}%"
    elif change_pct < -1:
        trend_cls, trend_icon, trend_text = "trend-down", "&#9660;", f"{change_pct:.1f}%"
    else:
        trend_cls, trend_icon, trend_text = "trend-stable", "&#9654;", f"{change_pct:+.1f}%"

    best_low = None
    best_high = None
    if daily:
        prices = [(d.get("predicted_price", 0), d.get("date", "")) for d in daily if d.get("predicted_price")]
        if prices:
            best_p, best_d = min(prices, key=lambda x: x[0])
            worst_p, worst_d = max(prices, key=lambda x: x[0])
            if best_p < current:
                best_low = {"price": best_p, "date": best_d}
            if worst_p > current:
                best_high = {"price": worst_p, "date": worst_d}

    alert = regime.get("alert_level", "none")
    row_cls = "alert-warning" if alert == "warning" else "alert-watch" if alert == "watch" else ""

    return {
        "detail_id": room.get("detail_id", "?"),
        "category": room.get("category", "N/A"),
        "board": room.get("board", "N/A"),
        "current": current,
        "predicted": predicted,
        "trend_cls": trend_cls,
        "trend_icon": trend_icon,
        "trend_text": trend_text,
        "mom_signal": momentum.get("signal", "N/A").replace("_", " "),
        "regime_name": regime.get("regime", "N/A").replace("_", " "),
        "row_cls": row_cls,
        "best_low": best_low,
        "best_high": best_high,
    }


def _build_comparison_data(hotels: dict[str, list[dict]], mode: str) -> list[dict]:
    """Pre-process hotel data for the Below/Above comparison tabs."""
    result = []

    for hotel_name, rooms in hotels.items():
        hotel_rooms = []
        hotel_count = 0

        for room in rooms:
            current = room.get("current_price", 0)
            daily = room.get("daily", [])
            if not daily or not current:
                continue

            matching = []
            for d in daily:
                price = d.get("predicted_price", 0)
                if not price:
                    continue
                diff = price - current
                if mode == "below" and price < current:
                    matching.append({**d, "diff": diff, "diff_pct": diff / current * 100})
                elif mode == "above" and price > current:
                    matching.append({**d, "diff": diff, "diff_pct": diff / current * 100})

            if not matching:
                continue

            hotel_count += len(matching)
            detail_id = room.get("detail_id", "?")

            if mode == "below":
                best = min(matching, key=lambda r: r["predicted_price"])
                summary_text = f'Best: ${best["predicted_price"]:,.0f} (save ${abs(best["diff"]):,.0f})'
                summary_cls = "savings"
            else:
                best = max(matching, key=lambda r: r["predicted_price"])
                summary_text = f'Peak: ${best["predicted_price"]:,.0f} (+${best["diff"]:,.0f})'
                summary_cls = "premium"

            highlight_price = best["predicted_price"]
            processed_matching = []
            for r in matching:
                is_hl = abs(r.get("predicted_price", 0) - highlight_price) < 0.01
                diff_cls = "savings" if r["diff"] < 0 else "premium"
                processed_matching.append({
                    "date": r.get("date", ""),
                    "dow": r.get("dow", ""),
                    "days_remaining": r.get("days_remaining", ""),
                    "predicted_price": r.get("predicted_price", 0),
                    "diff": r["diff"],
                    "diff_pct": r["diff_pct"],
                    "diff_cls": diff_cls,
                    "lower_bound": r.get("lower_bound", 0),
                    "upper_bound": r.get("upper_bound", 0),
                    "is_highlight": is_hl,
                })

            uid = f"{mode}_{detail_id}"
            hotel_rooms.append({
                "uid": uid,
                "category": room.get("category", "N/A"),
                "board": room.get("board", "N/A"),
                "date_from": room.get("date_from", "N/A"),
                "days": room.get("days_to_checkin", 0),
                "current": current,
                "n_matching": len(matching),
                "summary_text": summary_text,
                "summary_cls": summary_cls,
                "matching": processed_matching,
            })

        if hotel_rooms:
            result.append({
                "name": hotel_name,
                "total_count": hotel_count,
                "rooms": hotel_rooms,
            })

    return result
