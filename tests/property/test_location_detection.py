# Feature: fraud-proof-hybrid-timesheet, Property 4/31
"""Property tests for location detection and output validation.

**Validates: Requirements 2.1-2.7, 25.3, 25.4**

Property 4: Location detection correctness — For any WiFi state and office list,
LocationDetector returns "office" iff BOTH SSID and BSSID exactly match an entry;
"home" in ALL other cases (no WiFi, empty list, timeout, mismatch).

Property 31: SSID/BSSID output format validation — SSID: printable ASCII 1-32 chars
accepted; BSSID: XX:XX:XX:XX:XX:XX hex format accepted; malformed → rejected.
"""

from __future__ import annotations

import string

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from shared.enums import LocationType
from tracker.domain.location import LocationDetectorService
from tracker.ports.wifi_detector import WifiInfo

# --- Fakes ---


class FakeWifiDetector:
    """A fake WifiDetectionPort that returns a preconfigured WifiInfo or None."""

    def __init__(self, wifi_info: WifiInfo | None, should_raise: bool = False) -> None:
        self._wifi_info = wifi_info
        self._should_raise = should_raise

    def get_current_network(self) -> WifiInfo | None:
        if self._should_raise:
            raise TimeoutError("WiFi detection timed out")
        return self._wifi_info


# --- Strategies ---

# Valid SSID: printable ASCII characters (0x20-0x7E), 1-32 chars
printable_ascii_chars = st.characters(
    min_codepoint=0x20, max_codepoint=0x7E
)
valid_ssid = st.text(alphabet=printable_ascii_chars, min_size=1, max_size=32)

# Valid BSSID: XX:XX:XX:XX:XX:XX where XX is a hex pair
hex_octet = st.text(
    alphabet=string.hexdigits[:16],  # 0-9, a-f
    min_size=2,
    max_size=2,
)


def build_bssid(octets: list[str]) -> str:
    """Build a BSSID string from 6 hex octets."""
    return ":".join(octets)


valid_bssid = st.lists(hex_octet, min_size=6, max_size=6).map(build_bssid)

# Invalid SSIDs: empty, too long, or non-printable characters
invalid_ssid_empty = st.just("")
invalid_ssid_too_long = st.text(alphabet=printable_ascii_chars, min_size=33, max_size=64)
invalid_ssid_non_printable = st.text(
    alphabet=st.characters(min_codepoint=0x00, max_codepoint=0x1F),
    min_size=1,
    max_size=32,
)

# Invalid BSSIDs: wrong format
invalid_bssid_no_colons = st.text(
    alphabet=string.hexdigits, min_size=12, max_size=12
)
invalid_bssid_wrong_separators = st.lists(hex_octet, min_size=6, max_size=6).map(
    lambda octets: "-".join(octets)
)
invalid_bssid_too_short = st.lists(hex_octet, min_size=1, max_size=5).map(
    lambda octets: ":".join(octets)
)
invalid_bssid_empty = st.just("")

# Office network list strategy: list of (ssid, bssid) tuples
office_network_entry = st.tuples(valid_ssid, valid_bssid)
office_network_list = st.lists(office_network_entry, min_size=1, max_size=10)

# WiFi states
wifi_connected = st.builds(WifiInfo, ssid=valid_ssid, bssid=valid_bssid)
wifi_disconnected = st.just(None)


@pytest.mark.property
class TestLocationDetectionCorrectness:
    """Property 4: Location detection correctness."""

    @given(
        office_networks=office_network_list,
    )
    @settings(max_examples=300)
    def test_matching_network_returns_office(
        self, office_networks: list[tuple[str, str]]
    ) -> None:
        """When current WiFi SSID+BSSID exactly match an entry, location SHALL be "office"."""
        # Pick the first entry from the office list as the connected network
        target_ssid, target_bssid = office_networks[0]

        detector = FakeWifiDetector(WifiInfo(ssid=target_ssid, bssid=target_bssid))
        service = LocationDetectorService(
            wifi_detector=detector, office_networks=office_networks
        )

        location, error = service.detect_location()
        assert location == LocationType.OFFICE
        assert error is None

    @given(
        office_networks=office_network_list,
        current_ssid=valid_ssid,
        current_bssid=valid_bssid,
    )
    @settings(max_examples=300)
    def test_non_matching_network_returns_home(
        self,
        office_networks: list[tuple[str, str]],
        current_ssid: str,
        current_bssid: str,
    ) -> None:
        """When SSID+BSSID don't match any entry, location SHALL be "home"."""
        # Ensure the current network does NOT match any office entry
        assume(
            all(
                not (current_ssid == ssid and current_bssid.lower() == bssid.lower())
                for ssid, bssid in office_networks
            )
        )

        detector = FakeWifiDetector(WifiInfo(ssid=current_ssid, bssid=current_bssid))
        service = LocationDetectorService(
            wifi_detector=detector, office_networks=office_networks
        )

        location, error = service.detect_location()
        assert location == LocationType.HOME

    @given(office_networks=office_network_list)
    @settings(max_examples=200)
    def test_no_wifi_returns_home(
        self, office_networks: list[tuple[str, str]]
    ) -> None:
        """When no WiFi connection is detected, location SHALL be "home"."""
        detector = FakeWifiDetector(wifi_info=None)
        service = LocationDetectorService(
            wifi_detector=detector, office_networks=office_networks
        )

        location, error = service.detect_location()
        assert location == LocationType.HOME
        assert error is None

    @given(current_wifi=wifi_connected)
    @settings(max_examples=200)
    def test_empty_office_list_returns_home(self, current_wifi: WifiInfo) -> None:
        """When office network list is empty, location SHALL be "home"."""
        detector = FakeWifiDetector(wifi_info=current_wifi)
        service = LocationDetectorService(
            wifi_detector=detector, office_networks=[]
        )

        location, error = service.detect_location()
        assert location == LocationType.HOME
        assert error is not None  # Should report config error

    @given(office_networks=office_network_list)
    @settings(max_examples=200)
    def test_detection_timeout_returns_home(
        self, office_networks: list[tuple[str, str]]
    ) -> None:
        """When WiFi detection raises an exception (timeout), location SHALL be "home"."""
        detector = FakeWifiDetector(wifi_info=None, should_raise=True)
        service = LocationDetectorService(
            wifi_detector=detector, office_networks=office_networks
        )

        location, error = service.detect_location()
        assert location == LocationType.HOME
        assert error is not None  # Should report detection failure

    @given(
        office_networks=office_network_list,
    )
    @settings(max_examples=200)
    def test_ssid_match_bssid_mismatch_returns_home(
        self, office_networks: list[tuple[str, str]]
    ) -> None:
        """When only SSID matches but BSSID differs, location SHALL be "home"."""
        target_ssid, _ = office_networks[0]
        # Use a different BSSID that won't match
        fake_bssid = "ff:ff:ff:ff:ff:ff"
        assume(
            all(
                not (target_ssid == ssid and fake_bssid == bssid.lower())
                for ssid, bssid in office_networks
            )
        )

        detector = FakeWifiDetector(WifiInfo(ssid=target_ssid, bssid=fake_bssid))
        service = LocationDetectorService(
            wifi_detector=detector, office_networks=office_networks
        )

        location, error = service.detect_location()
        assert location == LocationType.HOME

    @given(
        office_networks=office_network_list,
    )
    @settings(max_examples=200)
    def test_bssid_match_ssid_mismatch_returns_home(
        self, office_networks: list[tuple[str, str]]
    ) -> None:
        """When only BSSID matches but SSID differs, location SHALL be "home"."""
        _, target_bssid = office_networks[0]
        # Use a different SSID that won't match
        fake_ssid = "DEFINITELY_NOT_OFFICE_NET_12345"
        assume(
            all(
                not (fake_ssid == ssid and target_bssid.lower() == bssid.lower())
                for ssid, bssid in office_networks
            )
        )

        detector = FakeWifiDetector(WifiInfo(ssid=fake_ssid, bssid=target_bssid))
        service = LocationDetectorService(
            wifi_detector=detector, office_networks=office_networks
        )

        location, error = service.detect_location()
        assert location == LocationType.HOME


@pytest.mark.property
class TestSSIDBSSIDFormatValidation:
    """Property 31: SSID/BSSID output format validation."""

    @given(ssid=valid_ssid)
    @settings(max_examples=300)
    def test_valid_ssid_accepted(self, ssid: str) -> None:
        """Printable ASCII 1-32 chars SHALL be accepted as valid SSID."""
        service = LocationDetectorService(
            wifi_detector=FakeWifiDetector(None), office_networks=[]
        )
        assert service._validate_ssid(ssid) is True

    @given(ssid=invalid_ssid_empty)
    @settings(max_examples=10)
    def test_empty_ssid_rejected(self, ssid: str) -> None:
        """Empty string SHALL be rejected as invalid SSID."""
        service = LocationDetectorService(
            wifi_detector=FakeWifiDetector(None), office_networks=[]
        )
        assert service._validate_ssid(ssid) is False

    @given(ssid=invalid_ssid_too_long)
    @settings(max_examples=200)
    def test_too_long_ssid_rejected(self, ssid: str) -> None:
        """SSID longer than 32 chars SHALL be rejected."""
        service = LocationDetectorService(
            wifi_detector=FakeWifiDetector(None), office_networks=[]
        )
        assert service._validate_ssid(ssid) is False

    @given(ssid=invalid_ssid_non_printable)
    @settings(max_examples=200)
    def test_non_printable_ssid_rejected(self, ssid: str) -> None:
        """SSID with non-printable characters (below 0x20) SHALL be rejected."""
        service = LocationDetectorService(
            wifi_detector=FakeWifiDetector(None), office_networks=[]
        )
        assert service._validate_ssid(ssid) is False

    @given(bssid=valid_bssid)
    @settings(max_examples=300)
    def test_valid_bssid_accepted(self, bssid: str) -> None:
        """XX:XX:XX:XX:XX:XX hex format SHALL be accepted as valid BSSID."""
        service = LocationDetectorService(
            wifi_detector=FakeWifiDetector(None), office_networks=[]
        )
        assert service._validate_bssid(bssid) is True

    @given(bssid=invalid_bssid_empty)
    @settings(max_examples=10)
    def test_empty_bssid_rejected(self, bssid: str) -> None:
        """Empty string SHALL be rejected as invalid BSSID."""
        service = LocationDetectorService(
            wifi_detector=FakeWifiDetector(None), office_networks=[]
        )
        assert service._validate_bssid(bssid) is False

    @given(bssid=invalid_bssid_no_colons)
    @settings(max_examples=200)
    def test_bssid_without_colons_rejected(self, bssid: str) -> None:
        """BSSID without colon separators SHALL be rejected."""
        service = LocationDetectorService(
            wifi_detector=FakeWifiDetector(None), office_networks=[]
        )
        assert service._validate_bssid(bssid) is False

    @given(bssid=invalid_bssid_wrong_separators)
    @settings(max_examples=200)
    def test_bssid_with_wrong_separator_rejected(self, bssid: str) -> None:
        """BSSID with dash separators instead of colons SHALL be rejected."""
        service = LocationDetectorService(
            wifi_detector=FakeWifiDetector(None), office_networks=[]
        )
        assert service._validate_bssid(bssid) is False

    @given(bssid=invalid_bssid_too_short)
    @settings(max_examples=200)
    def test_bssid_too_short_rejected(self, bssid: str) -> None:
        """BSSID with fewer than 6 octets SHALL be rejected."""
        service = LocationDetectorService(
            wifi_detector=FakeWifiDetector(None), office_networks=[]
        )
        assert service._validate_bssid(bssid) is False

    @given(
        office_networks=office_network_list,
    )
    @settings(max_examples=200)
    def test_malformed_ssid_causes_home_detection(
        self, office_networks: list[tuple[str, str]]
    ) -> None:
        """When WiFi reports a malformed SSID, detect_location SHALL return "home"."""
        # Use a non-printable character SSID
        malformed_wifi = WifiInfo(ssid="\x01\x02\x03", bssid="aa:bb:cc:dd:ee:ff")
        detector = FakeWifiDetector(wifi_info=malformed_wifi)
        service = LocationDetectorService(
            wifi_detector=detector, office_networks=office_networks
        )

        location, error = service.detect_location()
        assert location == LocationType.HOME
        assert error is not None

    @given(
        office_networks=office_network_list,
    )
    @settings(max_examples=200)
    def test_malformed_bssid_causes_home_detection(
        self, office_networks: list[tuple[str, str]]
    ) -> None:
        """When WiFi reports a malformed BSSID, detect_location SHALL return "home"."""
        # Use an invalid BSSID format
        malformed_wifi = WifiInfo(ssid="ValidSSID", bssid="not-a-mac-address")
        detector = FakeWifiDetector(wifi_info=malformed_wifi)
        service = LocationDetectorService(
            wifi_detector=detector, office_networks=office_networks
        )

        location, error = service.detect_location()
        assert location == LocationType.HOME
        assert error is not None
