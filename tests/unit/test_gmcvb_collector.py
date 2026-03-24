"""Tests for GMCVB official benchmarks collector."""
import pytest
from src.collectors.gmcvb_collector import (
    get_official_adr,
    get_market_summary,
    OFFICIAL_ADR,
    OFFICIAL_OCCUPANCY,
    OFFICIAL_REVPAR,
)


class TestGmcvbCollector:
    """GMCVB benchmark tests."""

    def test_get_official_adr_miami_dade(self):
        """County-wide ADR should return known value."""
        assert get_official_adr("miami_dade") == 315.14

    def test_get_official_adr_south_beach(self):
        """South Beach ADR."""
        assert get_official_adr("south_beach") == 380.0

    def test_get_official_adr_mid_beach(self):
        """Mid-Beach luxury strip ADR."""
        assert get_official_adr("mid_beach") == 420.0

    def test_get_official_adr_downtown(self):
        """Downtown Miami ADR."""
        assert get_official_adr("downtown") == 220.0

    def test_get_official_adr_unknown_zone(self):
        """Unknown zone should return 0."""
        assert get_official_adr("atlantis") == 0

    def test_get_market_summary_structure(self):
        """Market summary should have all expected keys."""
        summary = get_market_summary()
        assert "adr" in summary
        assert "occupancy" in summary
        assert "revpar" in summary
        assert "source" in summary
        assert "last_updated" in summary

    def test_get_market_summary_source(self):
        """Source should be GMCVB."""
        summary = get_market_summary()
        assert "GMCVB" in summary["source"]

    def test_official_adr_all_zones_positive(self):
        """All zone ADRs should be positive."""
        for zone, adr in OFFICIAL_ADR.items():
            assert adr > 0, f"Zone {zone} has non-positive ADR: {adr}"

    def test_official_occupancy_range(self):
        """Occupancy should be between 0 and 100."""
        for zone, occ in OFFICIAL_OCCUPANCY.items():
            assert 0 < occ <= 100, f"Zone {zone} occupancy out of range: {occ}"

    def test_official_revpar_positive(self):
        """RevPAR should be positive."""
        for zone, revpar in OFFICIAL_REVPAR.items():
            assert revpar > 0, f"Zone {zone} has non-positive RevPAR: {revpar}"
