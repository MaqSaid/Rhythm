"""Unit tests for platform-specific WiFi detection adapters.

Tests mock subprocess.run to verify output parsing logic for both
Windows (netsh) and macOS (system_profiler) adapters.

Requirements tested: R2.5, R25.1, R25.2, R44.6
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from tracker.adapters.macos_wifi import MacOSWifiDetector
from tracker.adapters.windows_wifi import WindowsWifiDetector
from tracker.ports.wifi_detector import WifiInfo

# ---------------------------------------------------------------------------
# Windows adapter tests
# ---------------------------------------------------------------------------


class TestWindowsWifiDetector:
    """Tests for WindowsWifiDetector parsing and error handling."""

    def setup_method(self) -> None:
        self.detector = WindowsWifiDetector()

    @patch("tracker.adapters.windows_wifi.subprocess.run")
    def test_valid_output_returns_wifi_info(self, mock_run: MagicMock) -> None:
        """Valid netsh output with SSID and BSSID returns correct WifiInfo."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "    Name                   : Wi-Fi\n"
                "    Description            : Intel Wi-Fi 6 AX201\n"
                "    GUID                   : abc-123\n"
                "    Physical address       : aa:bb:cc:dd:ee:ff\n"
                "    State                  : connected\n"
                "    SSID                   : OfficeNetwork\n"
                "    BSSID                  : 11:22:33:44:55:66\n"
                "    Network type           : Infrastructure\n"
                "    Radio type             : 802.11ax\n"
                "    Authentication         : WPA2-Personal\n"
                "    Channel                : 36\n"
            ),
        )

        result = self.detector.get_current_network()

        assert result is not None
        assert result == WifiInfo(ssid="OfficeNetwork", bssid="11:22:33:44:55:66")

    @patch("tracker.adapters.windows_wifi.subprocess.run")
    def test_timeout_returns_none(self, mock_run: MagicMock) -> None:
        """Subprocess timeout (5 seconds) returns None."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="netsh", timeout=5)

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.windows_wifi.subprocess.run")
    def test_empty_output_returns_none(self, mock_run: MagicMock) -> None:
        """Empty stdout returns None."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.windows_wifi.subprocess.run")
    def test_no_wifi_connected_returns_none(self, mock_run: MagicMock) -> None:
        """Output with no SSID/BSSID (disconnected) returns None."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "    Name                   : Wi-Fi\n"
                "    Description            : Intel Wi-Fi 6 AX201\n"
                "    State                  : disconnected\n"
            ),
        )

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.windows_wifi.subprocess.run")
    def test_malformed_bssid_returns_none(self, mock_run: MagicMock) -> None:
        """Output with SSID but malformed BSSID returns None."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "    SSID                   : OfficeNetwork\n"
                "    BSSID                  : not-a-mac-address\n"
            ),
        )

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.windows_wifi.subprocess.run")
    def test_nonzero_return_code_returns_none(self, mock_run: MagicMock) -> None:
        """Non-zero return code from netsh returns None."""
        mock_run.return_value = MagicMock(returncode=1, stdout="Error")

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.windows_wifi.subprocess.run")
    def test_os_error_returns_none(self, mock_run: MagicMock) -> None:
        """OSError (e.g., netsh not found) returns None."""
        mock_run.side_effect = OSError("No such file")

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.windows_wifi.subprocess.run")
    def test_bssid_normalized_to_uppercase(self, mock_run: MagicMock) -> None:
        """BSSID is normalized to uppercase."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "    SSID                   : Home\n"
                "    BSSID                  : aa:bb:cc:dd:ee:ff\n"
            ),
        )

        result = self.detector.get_current_network()

        assert result is not None
        assert result.bssid == "AA:BB:CC:DD:EE:FF"

    @patch("tracker.adapters.windows_wifi.subprocess.run")
    def test_uses_argument_array_not_shell(self, mock_run: MagicMock) -> None:
        """Verify subprocess is called with arg array and no shell=True (R25.1)."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        self.detector.get_current_network()

        mock_run.assert_called_once_with(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=5,
        )


# ---------------------------------------------------------------------------
# macOS adapter tests
# ---------------------------------------------------------------------------


class TestMacOSWifiDetector:
    """Tests for MacOSWifiDetector parsing and error handling."""

    def setup_method(self) -> None:
        self.detector = MacOSWifiDetector()

    @patch("tracker.adapters.macos_wifi.subprocess.run")
    def test_valid_output_returns_wifi_info(self, mock_run: MagicMock) -> None:
        """Valid system_profiler output returns correct WifiInfo."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "Wi-Fi:\n"
                "\n"
                "  Software Versions:\n"
                "    CoreWLAN: 16.0\n"
                "\n"
                "  Interfaces:\n"
                "    en0:\n"
                "      Card Type: Wi-Fi\n"
                "      Status: Connected\n"
                "      Current Network Information:\n"
                "        CorpWiFi:\n"
                "          PHY Mode: 802.11ac\n"
                "          BSSID: aa:bb:cc:dd:ee:ff\n"
                "          Channel: 36\n"
                "          Security: WPA2 Personal\n"
            ),
        )

        result = self.detector.get_current_network()

        assert result is not None
        assert result == WifiInfo(ssid="CorpWiFi", bssid="AA:BB:CC:DD:EE:FF")

    @patch("tracker.adapters.macos_wifi.subprocess.run")
    def test_timeout_returns_none(self, mock_run: MagicMock) -> None:
        """Subprocess timeout (5 seconds) returns None."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="system_profiler", timeout=5
        )

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.macos_wifi.subprocess.run")
    def test_empty_output_returns_none(self, mock_run: MagicMock) -> None:
        """Empty stdout returns None."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.macos_wifi.subprocess.run")
    def test_no_current_network_section_returns_none(
        self, mock_run: MagicMock
    ) -> None:
        """Output without 'Current Network Information:' returns None."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "Wi-Fi:\n"
                "  Interfaces:\n"
                "    en0:\n"
                "      Card Type: Wi-Fi\n"
                "      Status: Off\n"
            ),
        )

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.macos_wifi.subprocess.run")
    def test_no_bssid_in_section_returns_none(self, mock_run: MagicMock) -> None:
        """Current network section without BSSID returns None."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "  Current Network Information:\n"
                "    MyNetwork:\n"
                "      PHY Mode: 802.11ac\n"
                "      Channel: 6\n"
            ),
        )

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.macos_wifi.subprocess.run")
    def test_nonzero_return_code_returns_none(self, mock_run: MagicMock) -> None:
        """Non-zero return code returns None."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.macos_wifi.subprocess.run")
    def test_os_error_returns_none(self, mock_run: MagicMock) -> None:
        """OSError (e.g., binary not found) returns None."""
        mock_run.side_effect = OSError("No such file")

        result = self.detector.get_current_network()

        assert result is None

    @patch("tracker.adapters.macos_wifi.subprocess.run")
    def test_bssid_normalized_to_uppercase(self, mock_run: MagicMock) -> None:
        """BSSID is normalized to uppercase."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "  Current Network Information:\n"
                "    HomeNet:\n"
                "      BSSID: ab:cd:ef:12:34:56\n"
            ),
        )

        result = self.detector.get_current_network()

        assert result is not None
        assert result.bssid == "AB:CD:EF:12:34:56"

    @patch("tracker.adapters.macos_wifi.subprocess.run")
    def test_uses_argument_array_not_shell(self, mock_run: MagicMock) -> None:
        """Verify subprocess is called with arg array and no shell=True (R25.1)."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        self.detector.get_current_network()

        mock_run.assert_called_once_with(
            ["/usr/sbin/system_profiler", "SPAirPortDataType"],
            capture_output=True,
            text=True,
            timeout=5,
        )


# ---------------------------------------------------------------------------
# Factory function tests
# ---------------------------------------------------------------------------


class TestWifiFactory:
    """Tests for create_wifi_detector factory function."""

    @patch("tracker.adapters.wifi_factory.platform.system", return_value="Windows")
    def test_windows_returns_windows_detector(self, _mock_sys: MagicMock) -> None:
        """Factory returns WindowsWifiDetector on Windows."""
        from tracker.adapters.wifi_factory import create_wifi_detector

        detector = create_wifi_detector()
        assert isinstance(detector, WindowsWifiDetector)

    @patch("tracker.adapters.wifi_factory.platform.system", return_value="Darwin")
    def test_darwin_returns_macos_detector(self, _mock_sys: MagicMock) -> None:
        """Factory returns MacOSWifiDetector on macOS."""
        from tracker.adapters.wifi_factory import create_wifi_detector

        detector = create_wifi_detector()
        assert isinstance(detector, MacOSWifiDetector)

    @patch("tracker.adapters.wifi_factory.platform.system", return_value="Linux")
    def test_unsupported_platform_raises(self, _mock_sys: MagicMock) -> None:
        """Factory raises RuntimeError on unsupported platforms."""
        from tracker.adapters.wifi_factory import create_wifi_detector

        with pytest.raises(RuntimeError, match="Unsupported platform: Linux"):
            create_wifi_detector()
