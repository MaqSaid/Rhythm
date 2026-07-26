# Feature: fraud-proof-hybrid-timesheet, Property 1: Clock-aligned boundary computation
"""Property tests for clock-aligned 5-minute boundary computation.

**Validates: Requirements 1.3**

Tests that for any arbitrary datetime, the computed next logging boundary is one of the
12 fixed 5-minute points within its hour (HH:00, HH:05, ..., HH:55), and is the smallest
such boundary that is >= the input datetime.
"""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from shared.time_utils import get_next_5min_boundary

# Strategy: generate arbitrary timezone-aware UTC datetimes
aware_datetimes = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2099, 12, 31),
    timezones=st.just(UTC),
)

# The 12 valid 5-minute marks within any hour
VALID_MINUTE_MARKS: list[int] = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]


@pytest.mark.property
class TestClockAlignedBoundary:
    """Property 1: Clock-aligned boundary computation."""

    @given(dt=aware_datetimes)
    @settings(max_examples=500)
    def test_boundary_is_5min_aligned(self, dt: datetime) -> None:
        """The computed boundary minute MUST be one of the 12 fixed 5-minute points."""
        boundary = get_next_5min_boundary(dt)
        assert boundary.minute in VALID_MINUTE_MARKS
        assert boundary.second == 0
        assert boundary.microsecond == 0

    @given(dt=aware_datetimes)
    @settings(max_examples=500)
    def test_boundary_is_gte_input(self, dt: datetime) -> None:
        """The computed boundary MUST be >= the input datetime."""
        boundary = get_next_5min_boundary(dt)
        assert boundary >= dt

    @given(dt=aware_datetimes)
    @settings(max_examples=500)
    def test_boundary_is_smallest_valid(self, dt: datetime) -> None:
        """The computed boundary MUST be the smallest 5-min point >= input.

        No valid 5-minute boundary exists between the input and the result.
        """
        boundary = get_next_5min_boundary(dt)

        # The previous 5-minute boundary must be strictly less than dt
        # (unless dt is exactly on a boundary, in which case boundary == dt)
        if boundary > dt:
            prev_boundary = boundary - timedelta(minutes=5)
            assert prev_boundary < dt

    @given(dt=aware_datetimes)
    @settings(max_examples=500)
    def test_boundary_within_same_hour_or_next(self, dt: datetime) -> None:
        """The boundary is at most 5 minutes ahead of the input (within next boundary)."""
        boundary = get_next_5min_boundary(dt)
        # Maximum distance is just under 5 minutes (4 min 59.999999 sec)
        assert boundary - dt < timedelta(minutes=5)

    @given(minute=st.sampled_from(VALID_MINUTE_MARKS))
    @settings(max_examples=50)
    def test_exact_boundary_returns_itself(self, minute: int) -> None:
        """When input is exactly on a 5-minute boundary, return the input unchanged."""
        dt = datetime(2024, 6, 15, 14, minute, 0, 0, tzinfo=UTC)
        boundary = get_next_5min_boundary(dt)
        assert boundary == dt

    @given(
        minute=st.sampled_from(VALID_MINUTE_MARKS),
        second=st.integers(min_value=1, max_value=59),
    )
    @settings(max_examples=100)
    def test_boundary_minute_with_seconds_advances(self, minute: int, second: int) -> None:
        """When input is on a 5-min minute but has seconds, boundary advances to next mark."""
        dt = datetime(2024, 6, 15, 14, minute, second, 0, tzinfo=UTC)
        boundary = get_next_5min_boundary(dt)
        assert boundary > dt
        assert boundary.minute in VALID_MINUTE_MARKS
        expected_next_minute = (minute + 5) % 60
        assert boundary.minute == expected_next_minute

    @given(
        minute=st.sampled_from(VALID_MINUTE_MARKS),
        microsecond=st.integers(min_value=1, max_value=999999),
    )
    @settings(max_examples=100)
    def test_boundary_minute_with_microseconds_advances(
        self, minute: int, microsecond: int
    ) -> None:
        """When input is on a 5-min minute but has microseconds, boundary advances."""
        dt = datetime(2024, 6, 15, 14, minute, 0, microsecond, tzinfo=UTC)
        boundary = get_next_5min_boundary(dt)
        assert boundary > dt
        assert boundary.minute in VALID_MINUTE_MARKS
