"""Port interface for WiFi network detection.

This port abstracts the platform-specific mechanism for reading the currently
connected WiFi network. Implementations use OS-native tools (netsh on Windows,
system_profiler/CoreWLAN on macOS) behind a common Protocol interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WifiInfo:
    """Immutable value object representing a detected WiFi network.

    Attributes:
        ssid: The network name (Service Set Identifier).
        bssid: The access point MAC address (Basic Service Set Identifier),
               formatted as colon-separated hex pairs (e.g., "AA:BB:CC:DD:EE:FF").
    """

    ssid: str
    bssid: str


class WifiDetectionPort(Protocol):
    """Protocol defining the contract for WiFi network detection.

    Implementations must query the OS networking stack to determine which
    WiFi network (if any) the device is currently connected to. The detection
    should complete within a 5-second timeout.
    """

    def get_current_network(self) -> WifiInfo | None:
        """Detect the currently connected WiFi network.

        Returns:
            A WifiInfo instance containing the SSID and BSSID of the
            connected network, or None if no WiFi connection is active,
            detection fails, or the operation times out.
        """
        ...
