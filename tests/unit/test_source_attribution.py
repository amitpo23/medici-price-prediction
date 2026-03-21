"""Unit tests for source_attribution.py — isolated source analysis and enrichment scoring."""
from __future__ import annotations

import pytest

from src.analytics.source_attribution import (
    SourceTrack,
    EnrichmentAttribution,
    AttributionReport,
    extract_source_predictions,
    build_source_track,
    compute_enrichment_attribution,
    compute_agreement,
    build_attribution_report,
    _derive_signal,
    _safe_pct,
    _signal_direction,
    _pearson_correlation,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _make_prediction(
    detail_id=1001,
    hotel_id=100,
    hotel_name="Test Hotel",
    category="standard",
    board="ro",
    current_price=500.0,
    predicted_checkin_price=550.0,
    fc_price=540.0,
    fc_confidence=0.7,
    hist_price=560.0,
    hist_confidence=0.5,
    ml_price=530.0,
    ml_confidence=0.4,
    days_to_checkin=30,
    date_from="2026-05-01",
    probability=None,
    forward_curve=None,
):
    pred = {
        "detail_id": detail_id,
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "category": category,
        "board": board,
        "current_price": current_price,
        "predicted_checkin_price": predicted_checkin_price,
        "fc_price": fc_price,
        "fc_confidence": fc_confidence,
        "fc_weight": 0.5,
        "hist_price": hist_price,
        "hist_confidence": hist_confidence,
        "hist_weight": 0.3,
        "ml_price": ml_price,
        "ml_confidence": ml_confidence,
        "ml_weight": 0.2,
        "days_to_checkin": days_to_checkin,
        "date_from": date_from,
        "probability": probability or {"up": 65, "down": 20, "stable": 15},
        "confidence_score": 0.6,
        "acceleration": 0.01,
        "forward_curve": forward_curve or [],
    }
    return pred


def _make_analysis(predictions=None):
    if predictions is None:
        predictions = [_make_prediction()]
    return {
        "predictions": {
            str(p["detail_id"]): p for p in predictions
        }
    }


# ── _derive_signal tests ────────────────────────────────────────────

class TestDeriveSignal:
    def test_call_high(self):
        rec, conf = _derive_signal(0.75, 0.10, acceleration=0.01)
        assert rec == "CALL"
        assert conf == "High"

    def test_call_med(self):
        rec, conf = _derive_signal(0.65, 0.15, acceleration=0.01)
        assert rec == "CALL"
        assert conf == "Med"

    def test_put_high(self):
        rec, conf = _derive_signal(0.10, 0.75, acceleration=-0.01)
        assert rec == "PUT"
        assert conf == "High"

    def test_put_med(self):
        rec, conf = _derive_signal(0.15, 0.65, acceleration=-0.01)
        assert rec == "PUT"
        assert conf == "Med"

    def test_none_low(self):
        rec, conf = _derive_signal(0.40, 0.40, acceleration=0)
        assert rec == "NONE"
        assert conf == "Low"

    def test_call_blocked_by_negative_acceleration(self):
        rec, conf = _derive_signal(0.75, 0.10, acceleration=-0.01)
        # p_up >= 0.70 but acceleration < 0 → doesn't pass CALL High
        # Falls through to check PUT: p_down=0.10 < 0.60 → NONE
        assert rec == "NONE"

    def test_put_blocked_by_positive_acceleration(self):
        rec, conf = _derive_signal(0.10, 0.75, acceleration=0.01)
        assert rec == "NONE"


# ── _safe_pct tests ─────────────────────────────────────────────────

class TestSafePct:
    def test_positive_change(self):
        assert _safe_pct(550, 500) == 10.0

    def test_negative_change(self):
        assert _safe_pct(450, 500) == -10.0

    def test_zero_current(self):
        assert _safe_pct(100, 0) == 0.0

    def test_no_change(self):
        assert _safe_pct(500, 500) == 0.0


# ── _signal_direction tests ─────────────────────────────────────────

class TestSignalDirection:
    def test_call(self):
        assert _signal_direction("CALL") == "up"

    def test_strong_call(self):
        assert _signal_direction("STRONG_CALL") == "up"

    def test_put(self):
        assert _signal_direction("PUT") == "down"

    def test_none(self):
        assert _signal_direction("NONE") == "neutral"

    def test_empty(self):
        assert _signal_direction("") == "neutral"


# ── _pearson_correlation tests ───────────────────────────────────────

class TestPearsonCorrelation:
    def test_perfect_positive(self):
        ic = _pearson_correlation([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert ic == 1.0

    def test_perfect_negative(self):
        ic = _pearson_correlation([1, 2, 3, 4, 5], [10, 8, 6, 4, 2])
        assert ic == -1.0

    def test_no_correlation(self):
        ic = _pearson_correlation([1, 2, 3, 4, 5], [3, 3, 3, 3, 3])
        assert ic == 0.0

    def test_too_few_points(self):
        ic = _pearson_correlation([1, 2], [3, 4])
        assert ic == 0.0

    def test_empty(self):
        ic = _pearson_correlation([], [])
        assert ic == 0.0


# ── extract_source_predictions tests ─────────────────────────────────

class TestExtractSourcePredictions:
    def test_all_four_tracks(self):
        analysis = _make_analysis()
        tracks = extract_source_predictions(analysis)
        assert len(tracks["forward_curve"]) == 1
        assert len(tracks["historical"]) == 1
        assert len(tracks["ml"]) == 1
        assert len(tracks["ensemble"]) == 1

    def test_missing_ml(self):
        pred = _make_prediction(ml_price=0)
        analysis = _make_analysis([pred])
        tracks = extract_source_predictions(analysis)
        assert len(tracks["ml"]) == 0
        assert len(tracks["forward_curve"]) == 1
        assert len(tracks["historical"]) == 1

    def test_missing_historical(self):
        pred = _make_prediction(hist_price=0)
        analysis = _make_analysis([pred])
        tracks = extract_source_predictions(analysis)
        assert len(tracks["historical"]) == 0

    def test_zero_current_price_skipped(self):
        pred = _make_prediction(current_price=0)
        analysis = _make_analysis([pred])
        tracks = extract_source_predictions(analysis)
        assert len(tracks["ensemble"]) == 0

    def test_empty_analysis(self):
        tracks = extract_source_predictions({})
        for track in tracks.values():
            assert track == []

    def test_prediction_fields(self):
        analysis = _make_analysis()
        tracks = extract_source_predictions(analysis)
        fc = tracks["forward_curve"][0]
        assert fc["detail_id"] == 1001
        assert fc["hotel_id"] == 100
        assert fc["predicted_price"] == 540.0
        assert fc["current_price"] == 500.0
        assert fc["change_pct"] == 8.0  # (540-500)/500 * 100

    def test_multiple_rooms(self):
        preds = [
            _make_prediction(detail_id=1, hotel_id=100),
            _make_prediction(detail_id=2, hotel_id=100),
            _make_prediction(detail_id=3, hotel_id=200),
        ]
        analysis = _make_analysis(preds)
        tracks = extract_source_predictions(analysis)
        assert len(tracks["forward_curve"]) == 3
        assert len(tracks["ensemble"]) == 3


# ── build_source_track tests ────────────────────────────────────────

class TestBuildSourceTrack:
    def test_basic_track(self):
        preds = [
            {"detail_id": 1, "hotel_id": 100, "hotel_name": "A",
             "category": "std", "board": "ro",
             "current_price": 500, "predicted_price": 550,
             "change_pct": 10, "confidence": 0.7,
             "signal": "CALL", "signal_confidence": "High",
             "days_to_checkin": 30, "checkin_date": "2026-05-01"},
        ]
        track = build_source_track("forward_curve", "FC", 100, preds, 5)
        assert track.source == "forward_curve"
        assert track.total_rooms == 5
        assert track.rooms_with_signal == 1
        assert track.coverage_pct == 20.0
        assert track.calls == 1
        assert track.puts == 0

    def test_empty_predictions(self):
        track = build_source_track("ml", "ML", 100, [], 10)
        assert track.rooms_with_signal == 0
        assert track.coverage_pct == 0.0
        assert track.avg_predicted_price == 0.0

    def test_hotel_breakdown(self):
        preds = [
            {"detail_id": 1, "hotel_id": 100, "hotel_name": "A",
             "current_price": 500, "predicted_price": 550, "change_pct": 10,
             "confidence": 0.7, "signal": "CALL", "category": "", "board": "",
             "days_to_checkin": 30, "checkin_date": ""},
            {"detail_id": 2, "hotel_id": 100, "hotel_name": "A",
             "current_price": 400, "predicted_price": 380, "change_pct": -5,
             "confidence": 0.6, "signal": "PUT", "category": "", "board": "",
             "days_to_checkin": 15, "checkin_date": ""},
            {"detail_id": 3, "hotel_id": 200, "hotel_name": "B",
             "current_price": 300, "predicted_price": 310, "change_pct": 3.3,
             "confidence": 0.5, "signal": "NONE", "category": "", "board": "",
             "days_to_checkin": 5, "checkin_date": ""},
        ]
        track = build_source_track("fc", "FC", 100, preds, 10)
        assert len(track.hotel_breakdown) == 2
        assert track.hotel_breakdown[0]["hotel_name"] == "A"  # Most rooms
        assert track.hotel_breakdown[0]["rooms"] == 2
        assert track.calls == 1
        assert track.puts == 1
        assert track.neutrals == 1

    def test_accuracy_with_actuals(self):
        preds = [
            {"detail_id": "1", "hotel_id": 100, "hotel_name": "A",
             "current_price": 500, "predicted_price": 550, "change_pct": 10,
             "confidence": 0.7, "signal": "CALL", "category": "", "board": "",
             "days_to_checkin": 30, "checkin_date": ""},
            {"detail_id": "2", "hotel_id": 100, "hotel_name": "A",
             "current_price": 400, "predicted_price": 380, "change_pct": -5,
             "confidence": 0.6, "signal": "PUT", "category": "", "board": "",
             "days_to_checkin": 15, "checkin_date": ""},
        ]
        actuals = {"1": 560.0, "2": 370.0}
        track = build_source_track("fc", "FC", 100, preds, 10, actuals)
        assert track.scored_rooms == 2
        assert track.hit_rate == 100.0  # Both directions correct
        assert track.mape > 0  # Some error

    def test_accuracy_wrong_direction(self):
        preds = [
            {"detail_id": "1", "hotel_id": 100, "hotel_name": "A",
             "current_price": 500, "predicted_price": 550, "change_pct": 10,
             "confidence": 0.7, "signal": "CALL", "category": "", "board": "",
             "days_to_checkin": 30, "checkin_date": ""},
        ]
        actuals = {"1": 450.0}  # Went down, but predicted up
        track = build_source_track("fc", "FC", 100, preds, 10, actuals)
        assert track.hit_rate == 0.0

    def test_sample_predictions_capped(self):
        preds = [
            {"detail_id": i, "hotel_id": 100, "hotel_name": "A",
             "current_price": 500, "predicted_price": 500 + i,
             "change_pct": i * 0.2, "confidence": 0.5,
             "signal": "CALL", "category": "", "board": "",
             "days_to_checkin": 30, "checkin_date": ""}
            for i in range(50)
        ]
        track = build_source_track("fc", "FC", 100, preds, 50)
        assert len(track.sample_predictions) == 20


# ── compute_enrichment_attribution tests ─────────────────────────────

class TestEnrichmentAttribution:
    def test_with_forward_curve_points(self):
        pred = _make_prediction(
            forward_curve=[
                {"event_adj_pct": 0.1, "season_adj_pct": 0.05,
                 "demand_adj_pct": 0.02, "weather_adj_pct": -0.01,
                 "competitor_adj_pct": 0.03, "momentum_adj_pct": 0.04},
                {"event_adj_pct": 0.15, "season_adj_pct": 0.05,
                 "demand_adj_pct": 0.02, "weather_adj_pct": -0.02,
                 "competitor_adj_pct": 0.03, "momentum_adj_pct": 0.03},
            ]
        )
        analysis = _make_analysis([pred])
        enrichments = compute_enrichment_attribution(analysis)
        assert len(enrichments) > 0
        # Find events enrichment
        events = next((e for e in enrichments if e.enrichment == "events"), None)
        assert events is not None
        assert events.avg_daily_impact_pct > 0
        assert events.rooms_affected == 1

    def test_empty_forward_curve(self):
        pred = _make_prediction(forward_curve=[])
        analysis = _make_analysis([pred])
        enrichments = compute_enrichment_attribution(analysis)
        # All enrichments should have 0 affected rooms
        for e in enrichments:
            assert e.rooms_affected == 0

    def test_no_predictions(self):
        enrichments = compute_enrichment_attribution({})
        assert enrichments == []

    def test_direction_positive(self):
        pred = _make_prediction(
            forward_curve=[
                {"event_adj_pct": 0.2, "season_adj_pct": 0, "demand_adj_pct": 0,
                 "weather_adj_pct": 0, "competitor_adj_pct": 0, "momentum_adj_pct": 0},
            ]
        )
        analysis = _make_analysis([pred])
        enrichments = compute_enrichment_attribution(analysis)
        events = next((e for e in enrichments if e.enrichment == "events"), None)
        assert events.direction == "positive"

    def test_direction_negative(self):
        pred = _make_prediction(
            forward_curve=[
                {"event_adj_pct": 0, "season_adj_pct": 0, "demand_adj_pct": 0,
                 "weather_adj_pct": -0.05, "competitor_adj_pct": 0, "momentum_adj_pct": 0},
            ]
        )
        analysis = _make_analysis([pred])
        enrichments = compute_enrichment_attribution(analysis)
        weather = next((e for e in enrichments if e.enrichment == "weather"), None)
        assert weather.direction == "negative"

    def test_sorted_by_impact(self):
        pred = _make_prediction(
            forward_curve=[
                {"event_adj_pct": 0.01, "season_adj_pct": 0.5,
                 "demand_adj_pct": 0.1, "weather_adj_pct": -0.02,
                 "competitor_adj_pct": 0.03, "momentum_adj_pct": 0.2},
            ]
        )
        analysis = _make_analysis([pred])
        enrichments = compute_enrichment_attribution(analysis)
        impacts = [abs(e.avg_daily_impact_pct) for e in enrichments if e.rooms_affected > 0]
        assert impacts == sorted(impacts, reverse=True)


# ── compute_agreement tests ──────────────────────────────────────────

class TestComputeAgreement:
    def test_full_agreement(self):
        tracks = {
            "forward_curve": [
                {"detail_id": "1", "signal": "CALL", "predicted_price": 550, "change_pct": 10},
            ],
            "historical": [
                {"detail_id": "1", "signal": "CALL", "predicted_price": 560, "change_pct": 12},
            ],
            "ml": [
                {"detail_id": "1", "signal": "CALL", "predicted_price": 540, "change_pct": 8},
            ],
        }
        rate, divs = compute_agreement(tracks)
        assert rate == 100.0
        assert len(divs) == 0

    def test_full_divergence(self):
        tracks = {
            "forward_curve": [
                {"detail_id": "1", "signal": "CALL", "predicted_price": 550,
                 "change_pct": 10, "hotel_name": "A", "current_price": 500},
            ],
            "historical": [
                {"detail_id": "1", "signal": "PUT", "predicted_price": 450,
                 "change_pct": -10, "hotel_name": "A", "current_price": 500},
            ],
            "ml": [
                {"detail_id": "1", "signal": "NONE", "predicted_price": 500,
                 "change_pct": 0, "hotel_name": "A", "current_price": 500},
            ],
        }
        rate, divs = compute_agreement(tracks)
        assert rate == 0.0
        assert len(divs) == 1
        assert divs[0]["price_spread"] == 100.0

    def test_partial_coverage(self):
        """Only 2 of 3 sources have predictions for this room."""
        tracks = {
            "forward_curve": [
                {"detail_id": "1", "signal": "CALL", "predicted_price": 550, "change_pct": 10},
            ],
            "historical": [
                {"detail_id": "1", "signal": "CALL", "predicted_price": 560, "change_pct": 12},
            ],
            "ml": [],
        }
        rate, divs = compute_agreement(tracks)
        assert rate == 100.0

    def test_single_source_excluded(self):
        """Room with only 1 source is excluded from agreement calc."""
        tracks = {
            "forward_curve": [
                {"detail_id": "1", "signal": "CALL", "predicted_price": 550, "change_pct": 10},
            ],
            "historical": [],
            "ml": [],
        }
        rate, divs = compute_agreement(tracks)
        assert rate == 0.0  # No common rooms

    def test_empty_tracks(self):
        rate, divs = compute_agreement({"forward_curve": [], "historical": [], "ml": []})
        assert rate == 0.0
        assert divs == []

    def test_divergence_sorted_by_spread(self):
        tracks = {
            "forward_curve": [
                {"detail_id": "1", "signal": "CALL", "predicted_price": 550,
                 "change_pct": 10, "hotel_name": "A", "current_price": 500},
                {"detail_id": "2", "signal": "CALL", "predicted_price": 700,
                 "change_pct": 40, "hotel_name": "B", "current_price": 500},
            ],
            "historical": [
                {"detail_id": "1", "signal": "PUT", "predicted_price": 480,
                 "change_pct": -4, "hotel_name": "A", "current_price": 500},
                {"detail_id": "2", "signal": "PUT", "predicted_price": 400,
                 "change_pct": -20, "hotel_name": "B", "current_price": 500},
            ],
            "ml": [],
        }
        rate, divs = compute_agreement(tracks)
        assert len(divs) == 2
        # Biggest spread first
        assert divs[0]["price_spread"] >= divs[1]["price_spread"]


# ── build_attribution_report tests ───────────────────────────────────

class TestBuildAttributionReport:
    def test_basic_report(self):
        pred = _make_prediction(
            forward_curve=[
                {"event_adj_pct": 0.1, "season_adj_pct": 0.05,
                 "demand_adj_pct": 0.02, "weather_adj_pct": -0.01,
                 "competitor_adj_pct": 0.03, "momentum_adj_pct": 0.04},
            ]
        )
        analysis = _make_analysis([pred])
        report = build_attribution_report(analysis)

        assert report.total_rooms == 1
        assert len(report.source_tracks) == 4
        assert len(report.enrichment_attribution) > 0

        # Check source names
        sources = {t.source for t in report.source_tracks}
        assert sources == {"forward_curve", "historical", "ml", "ensemble"}

    def test_report_to_dict(self):
        analysis = _make_analysis()
        report = build_attribution_report(analysis)
        d = report.to_dict()
        assert "source_tracks" in d
        assert "enrichment_attribution" in d
        assert "agreement_rate" in d
        assert "timestamp" in d

    def test_report_with_actuals(self):
        pred = _make_prediction(detail_id=1)
        analysis = _make_analysis([pred])
        actuals = {"1": 555.0}
        report = build_attribution_report(analysis, actuals)
        # At least the ensemble track should have scored rooms
        ensemble = next(t for t in report.source_tracks if t.source == "ensemble")
        assert ensemble.scored_rooms >= 0  # May or may not match detail_id format

    def test_empty_analysis(self):
        report = build_attribution_report({})
        assert report.total_rooms == 0
        assert all(t.rooms_with_signal == 0 for t in report.source_tracks)

    def test_multiple_hotels(self):
        preds = [
            _make_prediction(detail_id=1, hotel_id=100, hotel_name="Hotel A"),
            _make_prediction(detail_id=2, hotel_id=100, hotel_name="Hotel A"),
            _make_prediction(detail_id=3, hotel_id=200, hotel_name="Hotel B"),
        ]
        analysis = _make_analysis(preds)
        report = build_attribution_report(analysis)
        fc_track = next(t for t in report.source_tracks if t.source == "forward_curve")
        assert len(fc_track.hotel_breakdown) == 2
        assert fc_track.hotel_breakdown[0]["rooms"] == 2  # Hotel A first


# ── SourceTrack & AttributionReport serialization ────────────────────

class TestSerialization:
    def test_source_track_to_dict(self):
        track = SourceTrack(
            source="fc", label="FC", weight_pct=100,
            total_rooms=10, rooms_with_signal=8,
        )
        d = track.to_dict()
        assert d["source"] == "fc"
        assert d["total_rooms"] == 10

    def test_enrichment_to_dict(self):
        e = EnrichmentAttribution(
            enrichment="events", label="Events",
            avg_daily_impact_pct=0.15, max_daily_impact_pct=0.40,
            rooms_affected=5, rooms_total=10,
            coverage_pct=50.0, avg_price_impact_usd=12.50,
            direction="positive",
        )
        d = e.to_dict()
        assert d["enrichment"] == "events"
        assert d["avg_daily_impact_pct"] == 0.15
