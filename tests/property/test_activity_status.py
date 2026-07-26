# Feature: fraud-proof-hybrid-timesheet, Property 2: Activity-based status determination
"""Property tests for activity-based status determination.

**Validates: Requirements 1.4, 1.5**

Tests that for any sequence of activity events and any current time, the computed status
SHALL be "Idle" if and only if the continuous idle duration is >= the configured idle
threshold (default 10 minutes), and SHALL be "Online" otherwise.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from shared.config import TenantConfig
from shared.enums import ActivityStatus
from tracker.domain.activity import ActivityMonitorService


class FakeActivityMonitor:
    """A fake ActivityMonitorPort that returns a preconfigured idle duration."""

    def __init__(self, idle_duration: timedelta) -> None:
        self._idle_duration = idle_duration

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def has_activity_since(self, since: object) -> bool:
        return self._idle_duration == timedelta(0)

    def get_idle_duration(self) -> timedelta:
        return self._idle_duration


# --- Strategies ---

# Idle durations from 0 to 120 minutes (in seconds for precision)
idle_duration_seconds = st.integers(min_value=0, max_value=120 * 60).map(
    lambda s: timedelta(seconds=s)
)

# Configurable threshold values from 5 to 60 minutes (matching TenantConfig range)
threshold_minutes = st.integers(min_value=5, max_value=60)


@pytest.mark.property
class TestActivityStatusDetermination:
    """Property 2: Activity-based status determination."""

    @given(
        idle_seconds=st.integers(min_value=0, max_value=120 * 60),
        threshold=threshold_minutes,
    )
    @settings(max_examples=500)
    def test_idle_iff_duration_gte_threshold(
        self, idle_seconds: int, threshold: int
    ) -> None:
        """Status SHALL be Idle iff continuous idle duration >= threshold.

        For any idle duration and any valid threshold, the ActivityMonitorService
        must return IDLE when idle_duration >= threshold, and ONLINE otherwise.
        """
        idle_duration = timedelta(seconds=idle_seconds)
        threshold_td = timedelta(minutes=threshold)

        monitor = FakeActivityMonitor(idle_duration=idle_duration)
        config = TenantConfig(idle_threshold_minutes=threshold)
        service = ActivityMonitorService(activity_monitor=monitor, config=config)

        status = service.determine_status()

        if idle_duration >= threshold_td:
            assert status == ActivityStatus.IDLE, (
                f"Expected IDLE for idle_duration={idle_duration}, threshold={threshold_td}"
            )
        else:
            assert status == ActivityStatus.ONLINE, (
                f"Expected ONLINE for idle_duration={idle_duration}, threshold={threshold_td}"
            )

    @given(threshold=threshold_minutes)
    @settings(max_examples=200)
    def test_zero_idle_always_online(self, threshold: int) -> None:
        """When idle duration is zero, status SHALL always be Online."""
        monitor = FakeActivityMonitor(idle_duration=timedelta(0))
        config = TenantConfig(idle_threshold_minutes=threshold)
        service = ActivityMonitorService(activity_monitor=monitor, config=config)

        assert service.determine_status() == ActivityStatus.ONLINE

    @given(threshold=threshold_minutes)
    @settings(max_examples=200)
    def test_exact_threshold_is_idle(self, threshold: int) -> None:
        """When idle duration exactly equals threshold, status SHALL be Idle."""
        idle_duration = timedelta(minutes=threshold)
        monitor = FakeActivityMonitor(idle_duration=idle_duration)
        config = TenantConfig(idle_threshold_minutes=threshold)
        service = ActivityMonitorService(activity_monitor=monitor, config=config)

        assert service.determine_status() == ActivityStatus.IDLE

    @given(threshold=threshold_minutes)
    @settings(max_examples=200)
    def test_one_second_below_threshold_is_online(self, threshold: int) -> None:
        """When idle duration is 1 second below threshold, status SHALL be Online."""
        idle_duration = timedelta(minutes=threshold) - timedelta(seconds=1)
        monitor = FakeActivityMonitor(idle_duration=idle_duration)
        config = TenantConfig(idle_threshold_minutes=threshold)
        service = ActivityMonitorService(activity_monitor=monitor, config=config)

        assert service.determine_status() == ActivityStatus.ONLINE

    @given(
        threshold=threshold_minutes,
        extra_seconds=st.integers(min_value=1, max_value=3600),
    )
    @settings(max_examples=200)
    def test_above_threshold_always_idle(self, threshold: int, extra_seconds: int) -> None:
        """When idle duration exceeds threshold, status SHALL always be Idle."""
        idle_duration = timedelta(minutes=threshold) + timedelta(seconds=extra_seconds)
        monitor = FakeActivityMonitor(idle_duration=idle_duration)
        config = TenantConfig(idle_threshold_minutes=threshold)
        service = ActivityMonitorService(activity_monitor=monitor, config=config)

        assert service.determine_status() == ActivityStatus.IDLE

    @given(
        idle_seconds=st.integers(min_value=0, max_value=120 * 60),
        threshold=threshold_minutes,
    )
    @settings(max_examples=300)
    def test_resume_detection_after_idle(
        self, idle_seconds: int, threshold: int
    ) -> None:
        """When previous status was IDLE and current is ONLINE, is_resuming_from_idle is True.

        Validates R1.5: When activity resumes after Idle, set status back to Online.
        """
        idle_duration = timedelta(seconds=idle_seconds)
        threshold_td = timedelta(minutes=threshold)

        monitor = FakeActivityMonitor(idle_duration=idle_duration)
        config = TenantConfig(idle_threshold_minutes=threshold)
        service = ActivityMonitorService(activity_monitor=monitor, config=config)

        is_resuming = service.is_resuming_from_idle(ActivityStatus.IDLE)

        # Resuming is True only when currently ONLINE (idle < threshold)
        if idle_duration < threshold_td:
            assert is_resuming is True
        else:
            assert is_resuming is False
