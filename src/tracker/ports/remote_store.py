"""Port interface for remote data store communication.

This port abstracts the connection to the central store (Google Sheets)
for pushing synced activity data, exception records, and heartbeat signals.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from tracker.domain.models import LogEntry, QuickException


class RemoteStorePort(Protocol):
    """Protocol defining the contract for remote central store communication.

    Implementations push batched activity data and exceptions to the central
    store (Google Sheets via gspread) and send periodic heartbeat signals.
    All operations should respect timeout (30s) and circuit breaker policies.
    """

    def push_sync_batch(self, entries: list[LogEntry]) -> bool:
        """Push a batch of log entries to the central store.

        Entries are pushed chronologically during nightly sync. On failure,
        entries should be returned to the front of the sync queue.

        Args:
            entries: Ordered list of LogEntry records to push.

        Returns:
            True if the batch was successfully written to the central
            store, False if the push failed (timeout, auth error, etc.).
        """
        ...

    def push_exceptions(self, exceptions: list[QuickException]) -> bool:
        """Push quick exception records to the central store.

        Args:
            exceptions: List of QuickException records to sync.

        Returns:
            True if all exceptions were successfully written, False otherwise.
        """
        ...

    def send_heartbeat(self, employee_id: str, timestamp: datetime) -> bool:
        """Send a heartbeat signal indicating the tracker is active.

        Heartbeats are sent every 30 minutes and used by the Portal to
        compute the ephemeral presence indicator.

        Args:
            employee_id: The unique identifier of the employee.
            timestamp: The UTC timestamp of the heartbeat.

        Returns:
            True if the heartbeat was acknowledged, False on failure.
            Failures are silently retried on the next cycle.
        """
        ...
