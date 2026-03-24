"""Tests for the Consensus Signal Engine."""
from __future__ import annotations

import pytest

from src.analytics.consensus_signal import (
    SourceVote,
    calculate_consensus,
    compute_consensus_signal,
    vote_booking_momentum,
    vote_competitors,
    vote_events,
    vote_flight_demand,
    vote_forward_curve,
    vote_historical,
    vote_official_benchmark,
    vote_peers,
    vote_scan_velocity,
    vote_seasonality,
    vote_weather,
)


# ---------------------------------------------------------------------------
# Helpers — real prediction objects, no mocks
# ---------------------------------------------------------------------------

def _make_pred(
    current_price=200.0,
    hotel_name="Test Hotel",
    detail_id=1001,
    T=14,
    fc_change_pct=0.0,
    season_adj_pct=0.0,
    demand_adj_pct=0.0,
    weather_adj_pct=0.0,
    cancellation_adj_pct=0.0,
    velocity_24h=0.0,
    acceleration=0.0,
    prob_up=50.0,
    prob_down=50.0,
):
    """Build a realistic prediction dict for testing."""
    return {
        "current_price": current_price,
        "hotel_name": hotel_name,
        "detail_id": detail_id,
        "T": T,
        "forward_curve": [
            {
                "change_pct": fc_change_pct,
                "season_adj_pct": season_adj_pct,
                "demand_adj_pct": demand_adj_pct,
                "weather_adj_pct": weather_adj_pct,
                "cancellation_adj_pct": cancellation_adj_pct,
            }
        ],
        "momentum": {
            "velocity_24h": velocity_24h,
            "acceleration": acceleration,
        },
        "probability": {
            "up": prob_up,
            "down": prob_down,
        },
    }


# ===================================================================
# Coordinator tests
# ===================================================================

class TestCalculateConsensus:
    """Tests for calculate_consensus."""

    def test_unanimous_call(self):
        votes = [
            SourceVote("a", "CALL", "Leading", "reason"),
            SourceVote("b", "CALL", "Coincident", "reason"),
            SourceVote("c", "CALL", "Lagging", "reason"),
            SourceVote("d", "CALL", "Leading", "reason"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "CALL"
        assert result["probability"] == 100.0
        assert result["sources_voting"] == 4
        assert result["sources_neutral"] == 0
        assert result["sources_agree"] == 4
        assert result["sources_disagree"] == 0

    def test_unanimous_put(self):
        votes = [
            SourceVote("a", "PUT", "Leading"),
            SourceVote("b", "PUT", "Coincident"),
            SourceVote("c", "PUT", "Lagging"),
            SourceVote("d", "PUT", "Leading"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "PUT"
        assert result["probability"] == 100.0

    def test_majority_above_threshold(self):
        """3 CALL + 1 PUT = 75% -> CALL."""
        votes = [
            SourceVote("a", "CALL", "Leading"),
            SourceVote("b", "CALL", "Coincident"),
            SourceVote("c", "CALL", "Lagging"),
            SourceVote("d", "PUT", "Leading"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "CALL"
        assert result["probability"] == 75.0
        assert result["call_pct"] == 75.0
        assert result["put_pct"] == 25.0

    def test_split_below_threshold(self):
        """3 CALL + 2 PUT = 60% -> NEUTRAL (below 66%)."""
        votes = [
            SourceVote("a", "CALL", "Leading"),
            SourceVote("b", "CALL", "Coincident"),
            SourceVote("c", "CALL", "Lagging"),
            SourceVote("d", "PUT", "Leading"),
            SourceVote("e", "PUT", "Coincident"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "NEUTRAL"
        assert result["probability"] == 60.0

    def test_neutral_excluded_from_voting(self):
        """4 CALL + 1 NEUTRAL = 4 voting, 100% CALL."""
        votes = [
            SourceVote("a", "CALL", "Leading"),
            SourceVote("b", "CALL", "Coincident"),
            SourceVote("c", "NEUTRAL", "Lagging"),
            SourceVote("d", "CALL", "Leading"),
            SourceVote("e", "CALL", "Coincident"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "CALL"
        assert result["probability"] == 100.0
        assert result["sources_voting"] == 4
        assert result["sources_neutral"] == 1

    def test_all_neutral(self):
        votes = [
            SourceVote("a", "NEUTRAL", "Leading"),
            SourceVote("b", "NEUTRAL", "Coincident"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "NEUTRAL"
        assert result["probability"] == 0.0
        assert result["sources_voting"] == 0
        assert result["sources_neutral"] == 2

    def test_empty_votes(self):
        result = calculate_consensus([])
        assert result["signal"] == "NEUTRAL"
        assert result["probability"] == 0.0
        assert result["sources_voting"] == 0
        assert result["votes"] == []

    def test_category_breakdown(self):
        votes = [
            SourceVote("a", "CALL", "Leading"),
            SourceVote("b", "PUT", "Leading"),
            SourceVote("c", "CALL", "Coincident"),
            SourceVote("d", "NEUTRAL", "Lagging"),
        ]
        result = calculate_consensus(votes)
        assert "Leading" in result["by_category"]
        assert result["by_category"]["Leading"]["call"] == 1
        assert result["by_category"]["Leading"]["put"] == 1
        assert result["by_category"]["Coincident"]["call"] == 1
        assert result["by_category"]["Lagging"]["neutral"] == 1

    def test_exact_threshold_66_percent(self):
        """4 CALL + 2 PUT = 66.7% -> CALL (above 66%)."""
        votes = [
            SourceVote("a", "CALL", "Leading"),
            SourceVote("b", "CALL", "Coincident"),
            SourceVote("c", "PUT", "Lagging"),
            SourceVote("d", "CALL", "Leading"),
            SourceVote("e", "CALL", "Coincident"),
            SourceVote("f", "PUT", "Lagging"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "CALL"
        assert result["probability"] == pytest.approx(66.7, abs=0.1)


# ===================================================================
# Voter tests
# ===================================================================

class TestVoteForwardCurve:
    def test_fc_rise_call(self):
        pred = _make_pred(fc_change_pct=35.0)
        v = vote_forward_curve(pred)
        assert v.vote == "CALL"
        assert v.category == "Lagging"

    def test_fc_drop_put(self):
        pred = _make_pred(fc_change_pct=-8.0)
        v = vote_forward_curve(pred)
        assert v.vote == "PUT"

    def test_fc_flat_neutral(self):
        pred = _make_pred(fc_change_pct=2.0)
        v = vote_forward_curve(pred)
        assert v.vote == "NEUTRAL"

    def test_fc_no_data(self):
        v = vote_forward_curve({})
        assert v.vote == "NEUTRAL"


class TestVoteScanVelocity:
    def test_velocity_up_call(self):
        pred = _make_pred(velocity_24h=0.05)  # 5%
        v = vote_scan_velocity(pred)
        assert v.vote == "CALL"

    def test_velocity_down_put(self):
        pred = _make_pred(velocity_24h=-0.04)  # -4%
        v = vote_scan_velocity(pred)
        assert v.vote == "PUT"

    def test_velocity_flat_neutral(self):
        pred = _make_pred(velocity_24h=0.01)  # 1%
        v = vote_scan_velocity(pred)
        assert v.vote == "NEUTRAL"


class TestVoteCompetitors:
    def test_below_zone_call(self):
        pred = _make_pred(current_price=80.0)
        v = vote_competitors(pred, zone_avg=100.0)  # -20%
        assert v.vote == "CALL"

    def test_above_zone_put(self):
        pred = _make_pred(current_price=115.0)
        v = vote_competitors(pred, zone_avg=100.0)  # +15%
        assert v.vote == "PUT"

    def test_no_zone_avg_neutral(self):
        pred = _make_pred(current_price=100.0)
        v = vote_competitors(pred, zone_avg=0.0)
        assert v.vote == "NEUTRAL"


class TestVoteEvents:
    def test_upcoming_event_call(self):
        events = [{"name": "Art Basel", "status": "upcoming"}]
        v = vote_events({}, events)
        assert v.vote == "CALL"
        assert "Art Basel" in v.reason

    def test_past_event_put(self):
        events = [{"name": "Ultra", "status": "past"}]
        v = vote_events({}, events)
        assert v.vote == "PUT"

    def test_no_events_neutral(self):
        v = vote_events({}, None)
        assert v.vote == "NEUTRAL"


class TestVoteSeasonality:
    def test_positive_season_call(self):
        pred = _make_pred(season_adj_pct=0.06)  # 6% (above 5% threshold)
        v = vote_seasonality(pred)
        assert v.vote == "CALL"

    def test_negative_season_put(self):
        pred = _make_pred(season_adj_pct=-0.06)  # -6% (below -5% threshold)
        v = vote_seasonality(pred)
        assert v.vote == "PUT"


class TestVoteOfficialBenchmark:
    def test_below_adr_call(self):
        pred = _make_pred(current_price=75.0)
        v = vote_official_benchmark(pred, official_adr=100.0)  # -25%
        assert v.vote == "CALL"

    def test_above_adr_put(self):
        pred = _make_pred(current_price=120.0)
        v = vote_official_benchmark(pred, official_adr=100.0)  # +20%
        assert v.vote == "PUT"

    def test_no_adr_neutral(self):
        v = vote_official_benchmark(_make_pred(), official_adr=0.0)
        assert v.vote == "NEUTRAL"


class TestVoteHistorical:
    def test_prob_up_call(self):
        pred = _make_pred(prob_up=72.0, prob_down=28.0)
        v = vote_historical(pred)
        assert v.vote == "CALL"

    def test_prob_down_put(self):
        pred = _make_pred(prob_up=30.0, prob_down=70.0)
        v = vote_historical(pred)
        assert v.vote == "PUT"

    def test_no_data_neutral(self):
        v = vote_historical({})
        assert v.vote == "NEUTRAL"


class TestVoteWeather:
    def test_bad_weather_put(self):
        pred = _make_pred(weather_adj_pct=-0.06)  # -6% (below -5% threshold)
        v = vote_weather(pred)
        assert v.vote == "PUT"

    def test_good_weather_call(self):
        pred = _make_pred(weather_adj_pct=0.04)  # 4% (above 3% threshold)
        v = vote_weather(pred)
        assert v.vote == "CALL"


class TestVotePeers:
    def test_peers_rising_call(self):
        peers = [{"direction": "up"}, {"direction": "up"}, {"direction": "down"}]
        v = vote_peers({}, peers)
        assert v.vote == "CALL"

    def test_peers_falling_put(self):
        peers = [{"direction": "down"}, {"direction": "down"}, {"direction": "up"}]
        v = vote_peers({}, peers)
        assert v.vote == "PUT"

    def test_no_peers_neutral(self):
        v = vote_peers({}, None)
        assert v.vote == "NEUTRAL"


class TestVoteBookingMomentum:
    def test_high_cancellation_put(self):
        pred = _make_pred(cancellation_adj_pct=-0.03)  # -3%
        v = vote_booking_momentum(pred)
        assert v.vote == "PUT"

    def test_low_cancellation_neutral(self):
        pred = _make_pred(cancellation_adj_pct=-0.01)  # -1%
        v = vote_booking_momentum(pred)
        assert v.vote == "NEUTRAL"


# ===================================================================
# Master function test
# ===================================================================

class TestComputeConsensusSignal:
    def test_mixed_votes_returns_structure(self):
        """Verify compute_consensus_signal returns all expected keys."""
        pred = _make_pred(
            current_price=150.0,
            hotel_name="W South Beach",
            detail_id=5001,
            T=7,
            fc_change_pct=-10.0,    # PUT
            season_adj_pct=-0.05,   # PUT
            demand_adj_pct=-0.02,   # PUT
            weather_adj_pct=-0.04,  # PUT
            cancellation_adj_pct=-0.03,  # PUT
            velocity_24h=-0.05,     # PUT
            prob_up=25.0,
            prob_down=75.0,         # PUT
        )
        result = compute_consensus_signal(
            pred,
            zone_avg=100.0,   # +50% -> PUT
            official_adr=100.0,  # +50% -> PUT
            events=[{"name": "Past Event", "status": "past"}],  # PUT
            peer_prices=[{"direction": "down"}, {"direction": "down"}, {"direction": "up"}],  # PUT
        )
        assert result["signal"] == "PUT"
        assert result["current_price"] == 150.0
        assert result["hotel_name"] == "W South Beach"
        assert result["detail_id"] == 5001
        assert result["T"] == 7
        assert "votes" in result
        assert "by_category" in result
        assert len(result["votes"]) == 11

    def test_all_neutral_default_pred(self):
        """A bland prediction should produce mostly NEUTRAL votes."""
        pred = _make_pred()
        result = compute_consensus_signal(pred)
        assert result["signal"] == "NEUTRAL"
