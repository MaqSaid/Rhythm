"""Factory function for creating the platform-appropriate WiFi detector.

Selects the correct WifiDetectionPort implementation based on the current
operating system at runtime (Strategy Pattern).

Requirements: R2.5, R44.6
"""

from __future__ import annotations

import platform

from tracker.ports.wifi_detector import WifiDetectionPort


def create_wifi_detector() -> WifiDetectionPort:
    """Create a WiFi detector appropriate for the current platform.

    Returns:
        A WifiDetectionPort implementation:
        - WindowsWifiDetector on Windows
        - MacOSWifiDetector on macOS (Darwin)

    Raises:
        RuntimeError: If the current platform is not supported.
    """
    system = platform.system()

    if system == "Windows":
        from tracker.adapters.windows_wifi import WindowsWifiDetector

        return WindowsWifiDetector()
    elif system == "Darwin":
        from tracker.adapters.macos_wifi import MacOSWifiDetector

        return MacOSWifiDetector()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")
