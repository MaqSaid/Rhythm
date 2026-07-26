"""Unit tests for ActivityMonitorService domain logic.

Tests verify correct status determination, idle duration delegation,
resume detection, and logging decisions.
"""

from datetime import timedelta

import pytest

from shared.config import TenantConfig
from shared.enums import ActivityStatus
from tracker.domain.activity import ActivityMonitorService


class FakeActivityMonitor:
    """Test double implementing the ActivityMonitorPort protocol."""

    def __init__(self, idle_duration: timedelta = timedelta(0)) -> None:
        self._idle_duration = idle_duration

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def has_activity_since(self, since) -> bool:
        return self._idle_duration == timedelta(0)

    def get_idle_duration(self) -> timedelta:
        return self._idle_duration

    def set_idle_duration(self, duration: timedelta) -> None:
        self._idle_duration = duration


@pytest.fixture
def default_config() -> TenantConfig:
    """TenantConfig with default idle_threshold_minutes=10."""
    return TenantConfig()


@pytest.fixture
def custom_config() -> TenantConfig:
    """TenantConfig with custom idle_threshold_minutes=15."""
    return TenantConfig(idle_threshold_minutes=15)


class TestDetermineStatus:
    """Tests for ActivityMonitorService.determine_status()."""

    def test_online_when_no_idle(self, default_config: TenantConfig) -> None:
        monitor = FakeActivityMonitor(idle_duration=timedelta(0))
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.determine_status() == ActivityStatus.ONLINE

    def test_online_when_idle_below_threshold(self, default_config: TenantConfig) -> None:
        monitor = FakeActivityMonitor(idle_duration=timedelta(minutes=9, seconds=59))
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.determine_status() == ActivityStatus.ONLINE

    def test_idle_when_exactly_at_threshold(self, default_config: TenantConfig) -> None:
        monitor = FakeActivityMonitor(idle_duration=timedelta(minutes=10))
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.determine_status() == ActivityStatus.IDLE

    def test_idle_when_above_threshold(self, default_config: TenantConfig) -> None:
        monitor = FakeActivityMonitor(idle_duration=timedelta(minutes=15))
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.determine_status() == ActivityStatus.IDLE

    def test_respects_custom_threshold(self, custom_config: TenantConfig) -> None:
        # 12 minutes idle with 15-minute threshold → still Online
        monitor = FakeActivityMonitor(idle_duration=timedelta(minutes=12))
        service = ActivityMonitorService(activity_monitor=monitor, config=custom_config)

        assert service.determine_status() == ActivityStatus.ONLINE

    def test_idle_at_custom_threshold(self, custom_config: TenantConfig) -> None:
        # Exactly 15 minutes idle with 15-minute threshold → Idle
        monitor = FakeActivityMonitor(idle_duration=timedelta(minutes=15))
        service = ActivityMonitorService(activity_monitor=monitor, config=custom_config)

        assert service.determine_status() == ActivityStatus.IDLE


class TestGetIdleDuration:
    """Tests for ActivityMonitorService.get_idle_duration()."""

    def test_delegates_to_port(self, default_config: TenantConfig) -> None:
        expected = timedelta(minutes=7, seconds=30)
        monitor = FakeActivityMonitor(idle_duration=expected)
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.get_idle_duration() == expected

    def test_zero_when_active(self, default_config: TenantConfig) -> None:
        monitor = FakeActivityMonitor(idle_duration=timedelta(0))
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.get_idle_duration() == timedelta(0)


class TestIsResumingFromIdle:
    """Tests for ActivityMonitorService.is_resuming_from_idle()."""

    def test_true_when_previous_idle_and_now_online(self, default_config: TenantConfig) -> None:
        # Currently active (idle < threshold) but previous was Idle
        monitor = FakeActivityMonitor(idle_duration=timedelta(minutes=2))
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.is_resuming_from_idle(ActivityStatus.IDLE) is True

    def test_false_when_previous_online(self, default_config: TenantConfig) -> None:
        # Previous was Online — not a resume
        monitor = FakeActivityMonitor(idle_duration=timedelta(minutes=2))
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.is_resuming_from_idle(ActivityStatus.ONLINE) is False

    def test_false_when_still_idle(self, default_config: TenantConfig) -> None:
        # Previous was Idle and still Idle — not resumed yet
        monitor = FakeActivityMonitor(idle_duration=timedelta(minutes=15))
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.is_resuming_from_idle(ActivityStatus.IDLE) is False


class TestShouldLogEntry:
    """Tests for ActivityMonitorService.should_log_entry()."""

    def test_always_returns_true(self, default_config: TenantConfig) -> None:
        monitor = FakeActivityMonitor(idle_duration=timedelta(0))
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.should_log_entry() is True

    def test_returns_true_even_when_idle(self, default_config: TenantConfig) -> None:
        monitor = FakeActivityMonitor(idle_duration=timedelta(minutes=30))
        service = ActivityMonitorService(activity_monitor=monitor, config=default_config)

        assert service.should_log_entry() is True
