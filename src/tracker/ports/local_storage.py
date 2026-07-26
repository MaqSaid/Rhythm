"""Port interface for local persistent storage on the employee's device.

This port abstracts the SQLite local database, allowing the domain logic
to persist log entries, quick exceptions, and manage the sync queue without
coupling to the specific storage implementation.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from tracker.domain.models import LogEntry, QuickException


class LocalStoragePort(Protocol):
    """Protocol defining the contract for local data persistence.

    Implementations store activity log entries and quick exception records
    in a local database (SQLite WAL mode), manage the sync queue for
    nightly push, and support hash chain verification via last valid hash.
    """

    def insert_log_entry(self, entry: LogEntry) -> bool:
        """Persist a single activity log entry to local storage.

        Args:
            entry: The LogEntry to store, including timestamp, employee ID,
                   status, location, and hash chain fields.

        Returns:
            True if the entry was successfully written, False if the write
            failed (e.g., database locked, disk full).
        """
        ...

    def insert_quick_exception(self, exception: QuickException) -> bool:
        """Persist a quick exception from the idle-return toast notification.

        Args:
            exception: The QuickException record containing category,
                       timestamp, and duration information.

        Returns:
            True if the exception was successfully written, False otherwise.
        """
        ...

    def get_entries_for_date(self, target_date: date) -> list[LogEntry]:
        """Retrieve all log entries for a specific calendar date.

        Args:
            target_date: The date to query entries for.

        Returns:
            A list of LogEntry records for the given date, ordered
            chronologically by timestamp. Empty list if no entries exist.
        """
        ...

    def get_sync_queue(self) -> list[LogEntry]:
        """Retrieve all log entries pending synchronization to remote store.

        Returns:
            A list of LogEntry records that have not yet been successfully
            synced, ordered chronologically (oldest first) for FIFO push.
        """
        ...

    def get_exception_sync_queue(self) -> list[QuickException]:
        """Retrieve all quick exceptions pending synchronization.

        Returns:
            A list of QuickException records not yet pushed to the
            remote store, ordered chronologically.
        """
        ...

    def mark_synced(self, entry_ids: list[str]) -> None:
        """Mark entries as successfully synced to the remote store.

        Args:
            entry_ids: List of entry identifiers that were successfully
                       pushed to the central store.
        """
        ...

    def get_queue_oldest_date(self) -> date | None:
        """Get the date of the oldest entry in the sync queue.

        Used to determine how far back the offline queue extends
        (maximum 90 days retention policy).

        Returns:
            The date of the oldest unsynced entry, or None if the
            sync queue is empty.
        """
        ...

    def get_last_valid_hash(self) -> str | None:
        """Retrieve the hash of the last successfully verified chain entry.

        Used at startup and before sync to resume hash chain computation
        from the correct point.

        Returns:
            The SHA-256 hex digest of the last valid entry in the hash
            chain, or None if no entries exist yet (first run).
        """
        ...
