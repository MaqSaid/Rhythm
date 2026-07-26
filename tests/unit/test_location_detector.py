"""Unit tests for the LocationDetectorService domain logic.

Tests cover all edge cases specified in Requirements 2.1-2.7, 25.3, 25.4:
- Office network matching (SSID + BSSID both required)
- No WiFi connection → home
- Empty office network list → home + config error
- Detection failure/timeout → home + error reason
- SSID/BSSID format validation
- Case-insensitive BSSID comparison
"""

from __future__ import annotations

from shared.enums import LocationType
from tracker.domain.location import LocationDetectorService
from tracker.ports.wifi_detector import WifiInfo

# ---------------------------------------------------------------------------
# Test helpers / fake implementations
# ---------------------------------------------------------------------------


class FakeWifiDetector:
    """Fake WiFi detector that returns a pre-configured result."""

    def __init__(self, result: WifiInfo | None = None, raise_error: bool = False) -> None:
        self._result = result
        self._raise_error = raise_error

    def get_current_network(self) -> WifiInfo | None:
        if self._raise_error:
            raise TimeoutError("WiFi detection timed out")
        return self._result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OFFICE_NETWORKS = [
    ("CorpNet", "AA:BB:CC:DD:EE:FF"),
    ("CorpNet-5G", "11:22:33:44:55:66"),
]


def _make_service(
    wifi_info: WifiInfo | None = None,
    office_networks: list[tuple[str, str]] | None = None,
    raise_error: bool = False,
) -> LocationDetectorService:
    """Helper to build a LocationDetectorService with a fake detector."""
    detector = FakeWifiDetector(result=wifi_info, raise_error=raise_error)
    networks = office_networks if office_networks is not None else OFFICE_NETWORKS
    return LocationDetectorService(wifi_detector=detector, office_networks=networks)


# ---------------------------------------------------------------------------
# R2.1, R2.2: Both SSID and BSSID must match for "office"
# ---------------------------------------------------------------------------


class TestOfficeMatching:
    """Tests for correct office/home determination via network matching."""

    def test_exact_match_returns_office(self) -> None:
        """SSID + BSSID both match → office."""
        wifi = WifiInfo(ssid="CorpNet", bssid="AA:BB:CC:DD:EE:FF")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.OFFICE
        assert error is None

    def test_second_network_match_returns_office(self) -> None:
        """Matching the second entry in the office list works."""
        wifi = WifiInfo(ssid="CorpNet-5G", bssid="11:22:33:44:55:66")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.OFFICE
        assert error is None

    def test_ssid_match_bssid_mismatch_returns_home(self) -> None:
        """SSID matches but BSSID doesn't → home."""
        wifi = WifiInfo(ssid="CorpNet", bssid="00:00:00:00:00:00")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.HOME
        assert error is None

    def test_bssid_match_ssid_mismatch_returns_home(self) -> None:
        """BSSID matches but SSID doesn't → home."""
        wifi = WifiInfo(ssid="HomeNet", bssid="AA:BB:CC:DD:EE:FF")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.HOME
        assert error is None

    def test_no_match_at_all_returns_home(self) -> None:
        """Neither SSID nor BSSID match → home."""
        wifi = WifiInfo(ssid="CoffeeShop", bssid="FF:FF:FF:FF:FF:FF")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.HOME
        assert error is None

    def test_bssid_comparison_is_case_insensitive(self) -> None:
        """BSSID comparison should be case-insensitive."""
        wifi = WifiInfo(ssid="CorpNet", bssid="aa:bb:cc:dd:ee:ff")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.OFFICE
        assert error is None

    def test_bssid_mixed_case_matches(self) -> None:
        """Mixed-case BSSID in both config and detection should match."""
        office_nets = [("MixedNet", "Aa:Bb:Cc:Dd:Ee:Ff")]
        wifi = WifiInfo(ssid="MixedNet", bssid="aA:bB:cC:dD:eE:fF")
        service = _make_service(wifi_info=wifi, office_networks=office_nets)

        location, error = service.detect_location()

        assert location == LocationType.OFFICE
        assert error is None


# ---------------------------------------------------------------------------
# R2.4: No WiFi connection → home
# ---------------------------------------------------------------------------


class TestNoWifiConnection:
    """Tests for when the laptop has no active WiFi connection."""

    def test_no_wifi_returns_home_no_error(self) -> None:
        """No WiFi connection → home with no error (not an error state)."""
        service = _make_service(wifi_info=None)

        location, error = service.detect_location()

        assert location == LocationType.HOME
        assert error is None


# ---------------------------------------------------------------------------
# R2.6: Detection timeout/failure → home + record error
# ---------------------------------------------------------------------------


class TestDetectionFailure:
    """Tests for WiFi detection timeouts and unexpected failures."""

    def test_detection_exception_returns_home_with_error(self) -> None:
        """If the WiFi detector raises an exception → home + error reason."""
        service = _make_service(raise_error=True)

        location, error = service.detect_location()

        assert location == LocationType.HOME
        assert error is not None
        assert "failed" in error.lower()


# ---------------------------------------------------------------------------
# R2.7: Empty/unreadable office list → home + config error
# ---------------------------------------------------------------------------


class TestEmptyOfficeList:
    """Tests for empty or unreadable office network configuration."""

    def test_empty_office_list_returns_home_with_config_error(self) -> None:
        """Empty office network list → home + config error message."""
        wifi = WifiInfo(ssid="CorpNet", bssid="AA:BB:CC:DD:EE:FF")
        service = _make_service(wifi_info=wifi, office_networks=[])

        location, error = service.detect_location()

        assert location == LocationType.HOME
        assert error is not None
        assert "empty" in error.lower() or "unreadable" in error.lower()


# ---------------------------------------------------------------------------
# R25.3: Validate SSID format
# ---------------------------------------------------------------------------


class TestSsidValidation:
    """Tests for SSID format validation."""

    def test_valid_ssid_alphanumeric(self) -> None:
        service = _make_service()
        assert service._validate_ssid("CorpNet") is True

    def test_valid_ssid_with_spaces(self) -> None:
        service = _make_service()
        assert service._validate_ssid("Corp Net 5G") is True

    def test_valid_ssid_with_special_chars(self) -> None:
        service = _make_service()
        assert service._validate_ssid("My-Network_v2.0") is True

    def test_empty_ssid_is_invalid(self) -> None:
        service = _make_service()
        assert service._validate_ssid("") is False

    def test_ssid_too_long_is_invalid(self) -> None:
        """SSID longer than 32 characters is invalid."""
        service = _make_service()
        assert service._validate_ssid("A" * 33) is False

    def test_ssid_exactly_32_chars_is_valid(self) -> None:
        service = _make_service()
        assert service._validate_ssid("A" * 32) is True

    def test_ssid_with_control_chars_is_invalid(self) -> None:
        """Control characters (below 0x20) should be rejected."""
        service = _make_service()
        assert service._validate_ssid("Corp\x01Net") is False

    def test_ssid_with_null_byte_is_invalid(self) -> None:
        service = _make_service()
        assert service._validate_ssid("Corp\x00Net") is False

    def test_malformed_ssid_triggers_home_with_error(self) -> None:
        """If detected SSID is malformed, return home + error."""
        wifi = WifiInfo(ssid="", bssid="AA:BB:CC:DD:EE:FF")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.HOME
        assert error is not None
        assert "malformed" in error.lower()


# ---------------------------------------------------------------------------
# R25.4: Validate BSSID format (XX:XX:XX:XX:XX:XX hex)
# ---------------------------------------------------------------------------


class TestBssidValidation:
    """Tests for BSSID format validation."""

    def test_valid_bssid_uppercase(self) -> None:
        service = _make_service()
        assert service._validate_bssid("AA:BB:CC:DD:EE:FF") is True

    def test_valid_bssid_lowercase(self) -> None:
        service = _make_service()
        assert service._validate_bssid("aa:bb:cc:dd:ee:ff") is True

    def test_valid_bssid_mixed_case(self) -> None:
        service = _make_service()
        assert service._validate_bssid("Aa:Bb:Cc:Dd:Ee:Ff") is True

    def test_empty_bssid_is_invalid(self) -> None:
        service = _make_service()
        assert service._validate_bssid("") is False

    def test_bssid_missing_colons_is_invalid(self) -> None:
        service = _make_service()
        assert service._validate_bssid("AABBCCDDEEFF") is False

    def test_bssid_with_dashes_is_invalid(self) -> None:
        """Only colon-separated format is accepted."""
        service = _make_service()
        assert service._validate_bssid("AA-BB-CC-DD-EE-FF") is False

    def test_bssid_too_short_is_invalid(self) -> None:
        service = _make_service()
        assert service._validate_bssid("AA:BB:CC:DD:EE") is False

    def test_bssid_too_long_is_invalid(self) -> None:
        service = _make_service()
        assert service._validate_bssid("AA:BB:CC:DD:EE:FF:00") is False

    def test_bssid_with_non_hex_chars_is_invalid(self) -> None:
        service = _make_service()
        assert service._validate_bssid("GG:HH:II:JJ:KK:LL") is False

    def test_bssid_with_extra_digits_per_pair_is_invalid(self) -> None:
        service = _make_service()
        assert service._validate_bssid("AAA:BB:CC:DD:EE:FF") is False

    def test_malformed_bssid_triggers_home_with_error(self) -> None:
        """If detected BSSID is malformed, return home + error."""
        wifi = WifiInfo(ssid="CorpNet", bssid="NOT-A-MAC")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.HOME
        assert error is not None
        assert "malformed" in error.lower()


# ---------------------------------------------------------------------------
# Integration-style scenario tests
# ---------------------------------------------------------------------------


class TestIntegrationScenarios:
    """End-to-end scenarios combining multiple requirements."""

    def test_connected_to_home_wifi_returns_home(self) -> None:
        """Employee connected to their home WiFi → home, no error."""
        wifi = WifiInfo(ssid="MyHomeRouter", bssid="12:34:56:78:9A:BC")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.HOME
        assert error is None

    def test_connected_to_office_wifi_returns_office(self) -> None:
        """Employee connected to office WiFi → office, no error."""
        wifi = WifiInfo(ssid="CorpNet", bssid="AA:BB:CC:DD:EE:FF")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.OFFICE
        assert error is None

    def test_spoofed_ssid_wrong_bssid_detected(self) -> None:
        """SSID spoofing attempt (right SSID, wrong BSSID) → home."""
        wifi = WifiInfo(ssid="CorpNet", bssid="DE:AD:BE:EF:00:01")
        service = _make_service(wifi_info=wifi)

        location, error = service.detect_location()

        assert location == LocationType.HOME
        assert error is None

    def test_single_office_network_configured(self) -> None:
        """Works correctly with a single office network in the list."""
        office_nets = [("SingleOffice", "01:02:03:04:05:06")]
        wifi = WifiInfo(ssid="SingleOffice", bssid="01:02:03:04:05:06")
        service = _make_service(wifi_info=wifi, office_networks=office_nets)

        location, error = service.detect_location()

        assert location == LocationType.OFFICE
        assert error is None
