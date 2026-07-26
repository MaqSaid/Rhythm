"""Windows WiFi detection adapter using netsh.

Implements the WifiDetectionPort protocol by invoking `netsh wlan show interfaces`
via subprocess with an argument array (no shell=True) to prevent command injection.
Parses the output to extract SSID and BSSID of the currently connected network.

Requirements: R2.5, R25.1, R25.2
"""

from __future__ import annotations

import re
import subprocess

from tracker.ports.wifi_detector import WifiInfo


class WindowsWifiDetector:
    """Detects the currently connected WiFi network on Windows.

    Uses ``netsh wlan show interfaces`` to query the wireless interface state.
    The command is executed with a fixed argument array — no user-controllable
    values are ever passed as arguments (R25.1, R25.2).

    The detector enforces a 5-second timeout. On timeout, parsing failure,
    or absence of a WiFi connection, ``get_current_network`` returns None.
    """

    _SSID_PATTERN = re.compile(r"^\s*SSID\s*:\s*(.+)$", re.MULTILINE)
    _BSSID_PATTERN = re.compile(r"^\s*BSSID\s*:\s*([0-9a-fA-F:]+)\s*$", re.MULTILINE)

    def get_current_network(self) -> WifiInfo | None:
        """Detect the currently connected WiFi network on Windows.

        Returns:
            A WifiInfo with the connected SSID and BSSID, or None if:
            - No WiFi connection is active
            - The subprocess times out (5 seconds)
            - The output cannot be parsed or is malformed
        """
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
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
        """Parse netsh output to extract SSID and BSSID.

        The SSID line looks like:
            SSID                   : MyNetwork
        The BSSID line looks like:
            BSSID                  : aa:bb:cc:dd:ee:ff
        """
        ssid_match = self._SSID_PATTERN.search(output)
        bssid_match = self._BSSID_PATTERN.search(output)

        if not ssid_match or not bssid_match:
            return None

        ssid = ssid_match.group(1).strip()
        bssid = bssid_match.group(1).strip().upper()

        if not ssid or not bssid:
            return None

        return WifiInfo(ssid=ssid, bssid=bssid)
