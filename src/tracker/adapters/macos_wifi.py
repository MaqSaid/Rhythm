"""macOS WiFi detection adapter using system_profiler.

Implements the WifiDetectionPort protocol by invoking
``/usr/sbin/system_profiler SPAirPortDataType`` via subprocess with an argument
array (no shell=True) to prevent command injection.
Parses the output to extract the SSID and BSSID of the current WiFi network.

Requirements: R2.5, R25.1, R25.2
"""

from __future__ import annotations

import re
import subprocess

from tracker.ports.wifi_detector import WifiInfo


class MacOSWifiDetector:
    """Detects the currently connected WiFi network on macOS.

    Uses ``system_profiler SPAirPortDataType`` to query airport interface data.
    The command is executed with a fixed argument array — no user-controllable
    values are ever passed as arguments (R25.1, R25.2).

    The detector enforces a 5-second timeout. On timeout, parsing failure,
    or absence of a WiFi connection, ``get_current_network`` returns None.
    """

    # In system_profiler output the current network section is indented under
    # "Current Network Information:" with the SSID as the key, and BSSID listed
    # as a sub-field.
    _CURRENT_NETWORK_MARKER = "Current Network Information:"
    _BSSID_PATTERN = re.compile(r"BSSID\s*:\s*([0-9a-fA-F:]+)", re.IGNORECASE)

    def get_current_network(self) -> WifiInfo | None:
        """Detect the currently connected WiFi network on macOS.

        Returns:
            A WifiInfo with the connected SSID and BSSID, or None if:
            - No WiFi connection is active
            - The subprocess times out (5 seconds)
            - The output cannot be parsed or is malformed
        """
        try:
            result = subprocess.run(
                ["/usr/sbin/system_profiler", "SPAirPortDataType"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            return None
        except OSError:
            return None

        if result.returncode != 0:
            return None

        return self._parse_output(result.stdout)

    def _parse_output(self, output: str) -> WifiInfo | None:
        """Parse system_profiler output to extract current network SSID and BSSID.

        The relevant section typically looks like:

            Current Network Information:
              MyNetworkSSID:
                PHY Mode: 802.11ac
                BSSID: aa:bb:cc:dd:ee:ff
                ...

        The SSID is the key under "Current Network Information:" and the BSSID
        is a sub-field of that entry.
        """
        marker_idx = output.find(self._CURRENT_NETWORK_MARKER)
        if marker_idx == -1:
            return None

        # Work with the section after the marker
        section = output[marker_idx + len(self._CURRENT_NETWORK_MARKER) :]

        # Extract SSID: the first non-empty indented line ending with ':'
        ssid = self._extract_ssid(section)
        if not ssid:
            return None

        # Extract BSSID from within the current network section
        bssid_match = self._BSSID_PATTERN.search(section)
        if not bssid_match:
            return None

        bssid = bssid_match.group(1).strip().upper()
        if not bssid:
            return None

        return WifiInfo(ssid=ssid, bssid=bssid)

    @staticmethod
    def _extract_ssid(section: str) -> str | None:
        """Extract the SSID from the first indented key line in the section.

        The SSID appears as an indented line like:
            '          MyNetwork:'
        We strip whitespace and the trailing colon.
        """
        for line in section.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # The SSID line ends with a colon and is the network name
            if stripped.endswith(":"):
                ssid = stripped[:-1].strip()
                if ssid:
                    return ssid
            # If we hit a line that doesn't match the expected pattern, stop
            break
        return None
