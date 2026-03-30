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
    vote_margin_erosion,
    vote_official_benchmark,
    vote_peers,
    vote_provider_spread,
    vote_scan_drop_risk,
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

    def test_strong_call_average(self):
        """3 CALL + 1 PUT = avg (3-1)/4 = 0.5 -> CALL."""
        votes = [
            SourceVote("a", "CALL", "Leading"),
            SourceVote("b", "CALL", "Coincident"),
            SourceVote("c", "CALL", "Lagging"),
            SourceVote("d", "PUT", "Leading"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "CALL"
        assert result["avg_score"] == pytest.approx(0.5, abs=0.01)
        assert result["call_pct"] == 75.0
        assert result["put_pct"] == 25.0

    def test_weak_call_still_call(self):
        """3 CALL + 2 PUT = avg (3-2)/5 = 0.2 -> CALL (>0.15)."""
        votes = [
            SourceVote("a", "CALL", "Leading"),
            SourceVote("b", "CALL", "Coincident"),
            SourceVote("c", "CALL", "Lagging"),
            SourceVote("d", "PUT", "Leading"),
            SourceVote("e", "PUT", "Coincident"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "CALL"
        assert result["avg_score"] == pytest.approx(0.2, abs=0.01)

    def test_neutral_included_in_average(self):
        """4 CALL + 1 NEUTRAL = avg_score 0.8 -> CALL."""
        votes = [
            SourceVote("a", "CALL", "Leading"),
            SourceVote("b", "CALL", "Coincident"),
            SourceVote("c", "NEUTRAL", "Lagging"),
            SourceVote("d", "CALL", "Leading"),
            SourceVote("e", "CALL", "Coincident"),
        ]
        result = calculate_consensus(votes)
        assert result["signal"] == "CALL"
        assert result["avg_score"] == pytest.approx(0.8, abs=0.01)
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

    def test_average_scoring(self):
        """4 CALL + 2 PUT = avg_score (4-2)/6 = 0.333 -> CALL (>0.15)."""
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
        assert result["avg_score"] == pytest.approx(0.333, abs=0.01)


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
        assert len(result["votes"]) == 14  # 11 original + 3 new data-driven voters

    def test_all_neutral_default_pred(self):
        """A bland prediction should produce mostly NEUTRAL votes."""
        pred = _make_pred()
        result = compute_consensus_signal(pred)
        assert result["signal"] == "NEUTRAL"


# ===================================================================
# Voter enrichment wiring tests (events + peers via compute_consensus_signal)
# ===================================================================

class TestVoterEnrichmentWiring:
    """Tests for events and peer data being properly wired to voters."""

    def test_events_upcoming_produces_call(self):
        """Events voter returns CALL when an upcoming event is present."""
        pred = _make_pred()
        events = [{"name": "Art Basel", "status": "upcoming"}]
        result = compute_consensus_signal(pred, events=events)
        events_vote = [v for v in result["votes"] if v["source"] == "events"]
        assert len(events_vote) == 1
        assert events_vote[0]["vote"] == "CALL"

    def test_events_past_produces_put(self):
        """Events voter returns PUT when a past event is present."""
        pred = _make_pred()
        events = [{"name": "Ultra", "status": "past"}]
        result = compute_consensus_signal(pred, events=events)
        events_vote = [v for v in result["votes"] if v["source"] == "events"]
        assert events_vote[0]["vote"] == "PUT"

    def test_events_none_produces_neutral(self):
        """Events voter returns NEUTRAL when no events provided."""
        pred = _make_pred()
        result = compute_consensus_signal(pred)
        events_vote = [v for v in result["votes"] if v["source"] == "events"]
        assert events_vote[0]["vote"] == "NEUTRAL"

    def test_peers_majority_rising_produces_call(self):
        """Peers voter returns CALL when >= 66% peers are rising."""
        pred = _make_pred()
        peers = [{"direction": "up"}, {"direction": "up"}, {"direction": "down"}]
        result = compute_consensus_signal(pred, peer_prices=peers)
        peers_vote = [v for v in result["votes"] if v["source"] == "peers"]
        assert peers_vote[0]["vote"] == "CALL"

    def test_peers_majority_falling_produces_put(self):
        """Peers voter returns PUT when >= 66% peers are falling."""
        pred = _make_pred()
        peers = [{"direction": "down"}, {"direction": "down"}, {"direction": "up"}]
        result = compute_consensus_signal(pred, peer_prices=peers)
        peers_vote = [v for v in result["votes"] if v["source"] == "peers"]
        assert peers_vote[0]["vote"] == "PUT"

    def test_peers_split_produces_neutral(self):
        """Peers voter returns NEUTRAL when peers are split."""
        pred = _make_pred()
        peers = [{"direction": "up"}, {"direction": "down"}]
        result = compute_consensus_signal(pred, peer_prices=peers)
        peers_vote = [v for v in result["votes"] if v["source"] == "peers"]
        assert peers_vote[0]["vote"] == "NEUTRAL"

    def test_full_consensus_with_events_and_peers(self):
        """Full consensus computation works with events and peers included."""
        pred = _make_pred(
            fc_change_pct=-10.0,
            velocity_24h=-0.05,
            prob_up=30.0,
            prob_down=70.0,
        )
        events = [{"name": "Post-event", "status": "past"}]
        peers = [{"direction": "down"}, {"direction": "down"}, {"direction": "down"}]
        result = compute_consensus_signal(pred, events=events, peer_prices=peers)
        assert result["signal"] in ("CALL", "PUT", "NEUTRAL")
        assert result["sources_voting"] > 0


# ---------------------------------------------------------------------------
# v2.6.0: New Data-Driven Voters
# ---------------------------------------------------------------------------

class TestScanDropRiskVoter:
    """Tests for vote_scan_drop_risk — uses real scan history data."""

    def test_no_scan_history(self):
        pred = {"current_price": 100}
        v = vote_scan_drop_risk(pred)
        assert v.vote == "NEUTRAL"

    def test_few_scans_neutral(self):
        pred = {"scan_history": {"scan_snapshots": 2, "scan_actual_drops": 1, "scan_actual_rises": 0, "scan_trend": "down"}}
        v = vote_scan_drop_risk(pred)
        assert v.vote == "NEUTRAL"
        assert "Only 2 scans" in v.reason

    def test_high_drop_frequency_put(self):
        pred = {"scan_history": {
            "scan_snapshots": 10,
            "scan_actual_drops": 7,
            "scan_actual_rises": 1,
            "scan_trend": "down",
            "scan_max_single_drop": 25,
        }}
        v = vote_scan_drop_risk(pred)
        assert v.vote == "PUT"

    def test_uptrend_no_drops(self):
        pred = {"scan_history": {
            "scan_snapshots": 10,
            "scan_actual_drops": 0,
            "scan_actual_rises": 8,
            "scan_trend": "up",
            "scan_max_single_drop": 0,
        }}
        v = vote_scan_drop_risk(pred)
        assert v.vote != "PUT"


class TestProviderSpreadVoter:
    """Tests for vote_provider_spread — uses SearchResultsPollLog data."""

    def test_no_source_inputs(self):
        pred = {"current_price": 100}
        v = vote_provider_spread(pred)
        assert v.vote == "NEUTRAL"

    def test_strong_undercut_put(self):
        pred = {"source_inputs": {"provider_pressure": -0.4}}
        v = vote_provider_spread(pred)
        assert v.vote == "PUT"
        assert "undercutting" in v.reason

    def test_priced_low_call(self):
        pred = {"source_inputs": {"provider_pressure": 0.35}}
        v = vote_provider_spread(pred)
        assert v.vote == "CALL"

    def test_neutral_range(self):
        pred = {"source_inputs": {"provider_pressure": 0.05}}
        v = vote_provider_spread(pred)
        assert v.vote == "NEUTRAL"


class TestMarginErosionVoter:
    """Tests for vote_margin_erosion — uses MED_Book buy prices."""

    def test_no_buy_price(self):
        pred = {"current_price": 100}
        v = vote_margin_erosion(pred, med_book_buy_price=0)
        assert v.vote == "NEUTRAL"

    def test_margin_eroded_put(self):
        pred = {"current_price": 80}
        v = vote_margin_erosion(pred, med_book_buy_price=100)
        assert v.vote == "PUT"
        assert "erosion" in v.reason

    def test_good_margin_call(self):
        pred = {"current_price": 150}
        v = vote_margin_erosion(pred, med_book_buy_price=100)
        assert v.vote == "CALL"
        assert "margin" in v.reason.lower()

    def test_small_margin_neutral(self):
        pred = {"current_price": 105}
        v = vote_margin_erosion(pred, med_book_buy_price=100)
        assert v.vote == "NEUTRAL"


class TestFullConsensus14Voters:
    """Test that all 14 voters participate in consensus."""

    def test_14_votes_returned(self):
        pred = _make_pred()
        result = compute_consensus_signal(pred)
        assert len(result["votes"]) == 14

    def test_all_voter_names_present(self):
        pred = _make_pred()
        result = compute_consensus_signal(pred)
        names = {v["source"] for v in result["votes"]}
        expected = {
            "forward_curve", "scan_velocity", "competitors", "events",
            "seasonality", "flight_demand", "weather", "peers",
            "booking_momentum", "historical", "official_benchmark",
            "scan_drop_risk", "provider_spread", "margin_erosion",
        }
        assert names == expected
