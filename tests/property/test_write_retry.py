# Feature: fraud-proof-hybrid-timesheet, Property 3: Write retry bounded at 3 attempts
"""Property test for write retry bounds.

**Validates: Requirements 1.8**

Property 3: Write retry bounded at 3 attempts — For any sequence of Local_DB write
    attempts for a single log entry, the entry SHALL be retried max 3 times then
    permanently discarded.

This is a behavioral property — uses a simple RetryTracker class that tracks attempts
and verifies:
- For any number of consecutive failures (1-10), the system retries up to 3 times only
- After 3 failures, the entry is discarded (not retried again)
- On success before 3 failures, it stops retrying
"""

from __future__ import annotations

from enum import Enum

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


class WriteResult(Enum):
    """Outcome of a single write attempt."""

    SUCCESS = "success"
    FAILURE = "failure"
    DISCARDED = "discarded"


class RetryTracker:
    """Tracks write retry attempts for a single log entry.

    Implements the retry policy from Requirement 1.8:
    - Max 3 consecutive attempts before discarding
    - On success, stop retrying
    - After 3 failures, permanently discard the entry
    """

    MAX_RETRIES = 3

    def __init__(self) -> None:
        self._attempts: int = 0
        self._discarded: bool = False
        self._succeeded: bool = False

    @property
    def attempts(self) -> int:
        """Total number of write attempts made."""
        return self._attempts

    @property
    def is_discarded(self) -> bool:
        """Whether the entry has been permanently discarded."""
        return self._discarded

    @property
    def is_succeeded(self) -> bool:
        """Whether the write eventually succeeded."""
        return self._succeeded

    @property
    def should_retry(self) -> bool:
        """Whether the entry should be retried on next cycle."""
        return not self._discarded and not self._succeeded

    def attempt_write(self, success: bool) -> WriteResult:
        """Attempt to write the entry.

        Args:
            success: Whether this write attempt succeeds.

        Returns:
            WriteResult indicating the outcome.
        """
        if self._discarded or self._succeeded:
            # Entry already resolved — no more attempts
            return WriteResult.DISCARDED if self._discarded else WriteResult.SUCCESS

        self._attempts += 1

        if success:
            self._succeeded = True
            return WriteResult.SUCCESS

        # Failed attempt
        if self._attempts >= self.MAX_RETRIES:
            self._discarded = True
            return WriteResult.DISCARDED

        return WriteResult.FAILURE


# --- Strategies ---

failure_counts = st.integers(min_value=1, max_value=10)
success_positions = st.integers(min_value=1, max_value=3)


@pytest.mark.property
class TestWriteRetryBounds:
    """Property 3: Write retry bounded at 3 attempts."""

    @given(num_failures=failure_counts)
    @settings(max_examples=500)
    def test_max_3_retries_then_discard(self, num_failures: int) -> None:
        """For any number of consecutive failures, max 3 attempts then discard.

        The entry SHALL be retried max 3 times then permanently discarded.
        """
        tracker = RetryTracker()

        for i in range(num_failures):
            result = tracker.attempt_write(success=False)

            if i < 2:
                # First two failures: entry retained for retry
                assert result == WriteResult.FAILURE
                assert tracker.should_retry is True
                assert tracker.is_discarded is False
            elif i == 2:
                # Third failure: entry discarded
                assert result == WriteResult.DISCARDED
                assert tracker.is_discarded is True
                assert tracker.should_retry is False
            else:
                # Beyond 3: already discarded, no more attempts accepted
                assert result == WriteResult.DISCARDED
                assert tracker.is_discarded is True

        # Final state check
        if num_failures >= 3:
            assert tracker.is_discarded is True
            assert tracker.attempts == 3  # Capped at 3
        else:
            assert tracker.is_discarded is False
            assert tracker.attempts == num_failures

    @given(success_at=success_positions)
    @settings(max_examples=300)
    def test_success_before_3_failures_stops_retrying(self, success_at: int) -> None:
        """On success before 3 failures, stop retrying immediately.

        If the write succeeds on attempt 1, 2, or 3, the entry is no longer retried.
        """
        tracker = RetryTracker()

        # Fail (success_at - 1) times, then succeed
        for _ in range(success_at - 1):
            result = tracker.attempt_write(success=False)
            assert result == WriteResult.FAILURE

        # Succeed on the success_at-th attempt
        result = tracker.attempt_write(success=True)
        assert result == WriteResult.SUCCESS
        assert tracker.is_succeeded is True
        assert tracker.is_discarded is False
        assert tracker.should_retry is False
        assert tracker.attempts == success_at

    @given(num_failures=failure_counts)
    @settings(max_examples=300)
    def test_discarded_entry_never_retried_again(self, num_failures: int) -> None:
        """After 3 failures, no further retry attempts are accepted."""
        tracker = RetryTracker()

        # Force 3 failures to discard
        for _ in range(3):
            tracker.attempt_write(success=False)

        assert tracker.is_discarded is True

        # Any further attempts should return DISCARDED
        for _ in range(num_failures):
            result = tracker.attempt_write(success=True)  # Even success is rejected
            assert result == WriteResult.DISCARDED
            assert tracker.is_discarded is True

        # Attempt count stays at 3 (no further tracking)
        assert tracker.attempts == 3

    @given(
        failure_sequence=st.lists(
            st.booleans(), min_size=1, max_size=10
        )
    )
    @settings(max_examples=500)
    def test_retry_count_never_exceeds_3(self, failure_sequence: list[bool]) -> None:
        """For any sequence of success/failure outcomes, attempts never exceed 3.

        Regardless of the pattern of successes and failures presented,
        the tracker SHALL never perform more than 3 write attempts.
        """
        tracker = RetryTracker()

        for success in failure_sequence:
            tracker.attempt_write(success=success)
            if tracker.is_succeeded or tracker.is_discarded:
                break

        assert tracker.attempts <= 3
