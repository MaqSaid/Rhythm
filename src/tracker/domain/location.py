"""Location Detector domain logic — WiFi-based office/home determination.

This module implements the core location detection logic for the Tracker.
It determines whether an employee is working from the office or from home
by comparing the currently connected WiFi network's SSID and BSSID against
a pre-configured list of known office networks.

All I/O is delegated to the injected WifiDetectionPort — this class
contains only pure domain logic with no file access, network calls, or
platform-specific code.

Requirements implemented:
    R2.1: Compare current WiFi SSID + BSSID against pre-configured office network list
    R2.2: Both SSID AND BSSID must match for location to be "office"
    R2.3: If no match → "home"
    R2.4: No WiFi connection → "home"
    R2.6: Detection timeout/failure → "home" + record error reason
    R2.7: Empty/unreadable office list → "home" + record config error
    R25.3: Validate SSID format (alphanumeric and standard characters)
    R25.4: Validate BSSID format (XX:XX:XX:XX:XX:XX hex)
"""

from __future__ import annotations

import re

from shared.enums import LocationType
from tracker.ports.wifi_detector import WifiDetectionPort


class LocationDetectorService:
    """Pure domain service for WiFi-based location determination.

    This service encapsulates the logic for deciding whether an employee
    is at the office or at home based on WiFi network matching. The office
    network list is injected at construction time and must contain at least
    one (SSID, BSSID) pair for office detection to be possible.

    The service does NOT perform the actual WiFi scanning — that responsibility
    belongs to the platform-specific adapter behind WifiDetectionPort.

    Args:
        wifi_detector: Port providing WiFi network detection.
        office_networks: List of (ssid, bssid) tuples representing known office networks.
    """

    # SSID: printable ASCII characters, 1-32 chars. Allow alphanumeric, spaces,
    # hyphens, underscores, dots, and other standard characters.
    _SSID_PATTERN = re.compile(r"^[\x20-\x7E]{1,32}$")

    # BSSID: six pairs of hex digits separated by colons (case-insensitive).
    _BSSID_PATTERN = re.compile(
        r"^[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:"
        r"[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}$"
    )

    def __init__(
        self,
        wifi_detector: WifiDetectionPort,
        office_networks: list[tuple[str, str]],
    ) -> None:
        self._wifi_detector = wifi_detector
        self._office_networks = office_networks

    def detect_location(self) -> tuple[LocationType, str | None]:
        """Detect the current work location based on WiFi network matching.

        Follows this decision logic:
        1. If office_networks is empty → ("home", config error message)
        2. Query the WiFi detector for the current network
        3. If no WiFi connection → ("home", None)
        4. Validate SSID/BSSID format → if malformed, ("home", error message)
        5. Compare against office network list (case-insensitive BSSID)
        6. Match → ("office", None)
        7. No match → ("home", None)

        Returns:
            A tuple of (LocationType, error_reason_or_None).
            LocationType.OFFICE if the current network matches the office list.
            LocationType.HOME in all other cases (no WiFi, no match, errors).
        """
        # R2.7: Empty or unreadable office network list
        if not self._office_networks:
            return (LocationType.HOME, "Office network list is empty or unreadable")

        # R2.6: Detection timeout/failure handled by port returning None,
        # but we also wrap with try/except for unexpected errors.
        try:
            wifi_info = self._wifi_detector.get_current_network()
        except Exception:
            return (LocationType.HOME, "WiFi detection failed unexpectedly")

        # R2.4: No WiFi connection
        if wifi_info is None:
            return (LocationType.HOME, None)

        # R25.3, R25.4: Validate output format
        if not self._validate_ssid(wifi_info.ssid) or not self._validate_bssid(wifi_info.bssid):
            return (LocationType.HOME, "Malformed WiFi output detected")

        # R2.1, R2.2: Both SSID and BSSID must match (BSSID case-insensitive)
        current_bssid_lower = wifi_info.bssid.lower()
        for office_ssid, office_bssid in self._office_networks:
            if wifi_info.ssid == office_ssid and current_bssid_lower == office_bssid.lower():
                return (LocationType.OFFICE, None)

        # R2.3: No match
        return (LocationType.HOME, None)

    def _validate_ssid(self, ssid: str) -> bool:
        """Validate SSID format against expected pattern.

        SSIDs should contain printable ASCII characters (space through tilde)
        and be between 1 and 32 characters long.

        Args:
            ssid: The SSID string to validate.

        Returns:
            True if the SSID matches the expected pattern, False otherwise.
        """
        if not ssid:
            return False
        return self._SSID_PATTERN.match(ssid) is not None

    def _validate_bssid(self, bssid: str) -> bool:
        """Validate BSSID format (XX:XX:XX:XX:XX:XX hex, case-insensitive).

        BSSIDs must be exactly six pairs of hexadecimal digits separated
        by colons, e.g., "AA:BB:CC:DD:EE:FF".

        Args:
            bssid: The BSSID string to validate.

        Returns:
            True if the BSSID matches the MAC address format, False otherwise.
        """
        if not bssid:
            return False
        return self._BSSID_PATTERN.match(bssid) is not None
