"""Unit tests for SQLite Local Storage adapter.

Uses in-memory SQLite databases (':memory:') for fast, isolated tests.
Tests verify all LocalStoragePort interface methods and the retry mechanism.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest

from shared.enums import ActivityStatus, ExceptionCategory, LocationType
from tracker.adapters.sqlite_storage import MAX_RETRY_ATTEMPTS, SQLiteLocalStorage
from tracker.domain.models import LogEntry, QuickException

# --- Fixtures ---


@pytest.fixture
def storage() -> SQLiteLocalStorage:
    """Create a fresh in-memory SQLite storage for each test."""
    return SQLiteLocalStorage(":memory:")


def _make_log_entry(
    entry_id: str | None = None,
    timestamp: datetime | None = None,
    employee_id: str = "EMP001",
    status: ActivityStatus = ActivityStatus.ONLINE,
    location: LocationType = LocationType.OFFICE,
    hash_val: str = "abc123",
    previous_hash: str = "000000",
    synced: bool = False,
    integrity_flag: str | None = None,
    time_drift_flag: str | None = None,
    detection_error: str | None = None,
) -> LogEntry:
    """Factory helper to create LogEntry instances for testing."""
    return LogEntry(
        id=entry_id or uuid4().hex,
        timestamp=timestamp or datetime(2024, 6, 15, 10, 0, 0),
        employee_id=employee_id,
        status=status,
        location=location,
        hash=hash_val,
        previous_hash=previous_hash,
        synced=synced,
        integrity_flag=integrity_flag,
        time_drift_flag=time_drift_flag,
        detection_error=detection_error,
    )


def _make_quick_exception(
    exception_id: str | None = None,
    employee_id: str = "EMP001",
    timestamp: datetime | None = None,
    category: ExceptionCategory = ExceptionCategory.MEDICAL_BREAK,
    duration_minutes: int = 15,
    synced: bool = False,
) -> QuickException:
    """Factory helper to create QuickException instances for testing."""
    return QuickException(
        id=exception_id or uuid4().hex,
        employee_id=employee_id,
        timestamp=timestamp or datetime(2024, 6, 15, 10, 30, 0),
        category=category,
        duration_minutes=duration_minutes,
        synced=synced,
    )


# --- Schema initialization tests ---


class TestSchemaInitialization:
    """Tests for database schema creation on first use."""

    def test_creates_tables_on_init(self, storage: SQLiteLocalStorage) -> None:
        """All required tables are created during initialization."""
        with storage._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row["name"] for row in cursor.fetchall()]

        assert "log_entries" in tables
        assert "quick_exceptions" in tables
        assert "sync_queue" in tables
        assert "heartbeats" in tables
        assert "config" in tables

    def test_creates_indexes_on_init(self, storage: SQLiteLocalStorage) -> None:
        """All required indexes are created during initialization."""
        with storage._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
            )
            indexes = [row["name"] for row in cursor.fetchall()]

        assert "idx_log_entries_synced" in indexes
        assert "idx_log_entries_timestamp" in indexes
        assert "idx_sync_queue_created" in indexes

    def test_wal_mode_enabled(self) -> None:
        """WAL journal mode is configured for crash safety."""
        storage = SQLiteLocalStorage(":memory:")
        with storage._get_connection() as conn:
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
        # In-memory databases may report 'memory' instead of 'wal'
        # but the PRAGMA is executed; test with file-based DB in integration
        assert mode in ("wal", "memory")

    def test_idempotent_schema_creation(self) -> None:
        """Creating storage twice on same DB doesn't fail."""
        storage1 = SQLiteLocalStorage(":memory:")
        # Re-initialize schema should not raise
        storage1._initialize_schema()


# --- insert_log_entry tests ---


class TestInsertLogEntry:
    """Tests for inserting log entries."""

    def test_insert_returns_true_on_success(self, storage: SQLiteLocalStorage) -> None:
        """Successful insert returns True."""
        entry = _make_log_entry()
        result = storage.insert_log_entry(entry)
        assert result is True

    def test_inserted_entry_is_retrievable(self, storage: SQLiteLocalStorage) -> None:
        """Inserted entry can be retrieved by date."""
        entry = _make_log_entry(timestamp=datetime(2024, 6, 15, 10, 0, 0))
        storage.insert_log_entry(entry)

        entries = storage.get_entries_for_date(date(2024, 6, 15))
        assert len(entries) == 1
        assert entries[0].id == entry.id
        assert entries[0].employee_id == entry.employee_id
        assert entries[0].status == ActivityStatus.ONLINE
        assert entries[0].location == LocationType.OFFICE

    def test_duplicate_id_returns_false(self, storage: SQLiteLocalStorage) -> None:
        """Inserting a duplicate ID returns False (not raises)."""
        entry = _make_log_entry(entry_id="dup-id")
        storage.insert_log_entry(entry)

        result = storage.insert_log_entry(entry)
        assert result is False

    def test_preserves_optional_fields(self, storage: SQLiteLocalStorage) -> None:
        """Optional fields (flags, detection_error) are preserved."""
        entry = _make_log_entry(
            integrity_flag="Integrity Violation",
            time_drift_flag="Clock Drift Detected",
            detection_error="WiFi timeout",
        )
        storage.insert_log_entry(entry)

        entries = storage.get_entries_for_date(entry.timestamp.date())
        assert entries[0].integrity_flag == "Integrity Violation"
        assert entries[0].time_drift_flag == "Clock Drift Detected"
        assert entries[0].detection_error == "WiFi timeout"

    def test_preserves_none_optional_fields(self, storage: SQLiteLocalStorage) -> None:
        """None optional fields are stored and retrieved as None."""
        entry = _make_log_entry()
        storage.insert_log_entry(entry)

        entries = storage.get_entries_for_date(entry.timestamp.date())
        assert entries[0].integrity_flag is None
        assert entries[0].time_drift_flag is None
        assert entries[0].detection_error is None


# --- insert_quick_exception tests ---


class TestInsertQuickException:
    """Tests for inserting quick exceptions."""

    def test_insert_returns_true_on_success(self, storage: SQLiteLocalStorage) -> None:
        """Successful exception insert returns True."""
        exc = _make_quick_exception()
        result = storage.insert_quick_exception(exc)
        assert result is True

    def test_inserted_exception_is_retrievable(self, storage: SQLiteLocalStorage) -> None:
        """Inserted exception appears in sync queue."""
        exc = _make_quick_exception()
        storage.insert_quick_exception(exc)

        queue = storage.get_exception_sync_queue()
        assert len(queue) == 1
        assert queue[0].id == exc.id
        assert queue[0].category == ExceptionCategory.MEDICAL_BREAK
        assert queue[0].duration_minutes == 15

    def test_duplicate_exception_id_returns_false(self, storage: SQLiteLocalStorage) -> None:
        """Inserting a duplicate exception ID returns False."""
        exc = _make_quick_exception(exception_id="dup-exc")
        storage.insert_quick_exception(exc)

        result = storage.insert_quick_exception(exc)
        assert result is False


# --- get_entries_for_date tests ---


class TestGetEntriesForDate:
    """Tests for date-based entry retrieval."""

    def test_returns_empty_for_no_entries(self, storage: SQLiteLocalStorage) -> None:
        """Returns empty list when no entries exist for the date."""
        entries = storage.get_entries_for_date(date(2024, 1, 1))
        assert entries == []

    def test_filters_by_date(self, storage: SQLiteLocalStorage) -> None:
        """Only returns entries matching the target date."""
        entry_june15 = _make_log_entry(
            entry_id="e1", timestamp=datetime(2024, 6, 15, 10, 0, 0)
        )
        entry_june16 = _make_log_entry(
            entry_id="e2", timestamp=datetime(2024, 6, 16, 10, 0, 0)
        )
        storage.insert_log_entry(entry_june15)
        storage.insert_log_entry(entry_june16)

        entries = storage.get_entries_for_date(date(2024, 6, 15))
        assert len(entries) == 1
        assert entries[0].id == "e1"

    def test_orders_by_timestamp(self, storage: SQLiteLocalStorage) -> None:
        """Entries are returned in chronological order."""
        entry_late = _make_log_entry(
            entry_id="late", timestamp=datetime(2024, 6, 15, 14, 0, 0)
        )
        entry_early = _make_log_entry(
            entry_id="early", timestamp=datetime(2024, 6, 15, 8, 0, 0)
        )
        storage.insert_log_entry(entry_late)
        storage.insert_log_entry(entry_early)

        entries = storage.get_entries_for_date(date(2024, 6, 15))
        assert entries[0].id == "early"
        assert entries[1].id == "late"


# --- get_sync_queue tests ---


class TestGetSyncQueue:
    """Tests for the sync queue retrieval."""

    def test_returns_only_unsynced_entries(self, storage: SQLiteLocalStorage) -> None:
        """Only entries with synced=0 are returned."""
        unsynced = _make_log_entry(entry_id="unsynced")
        synced = _make_log_entry(entry_id="synced", synced=True)
        storage.insert_log_entry(unsynced)
        storage.insert_log_entry(synced)

        queue = storage.get_sync_queue()
        assert len(queue) == 1
        assert queue[0].id == "unsynced"

    def test_ordered_by_timestamp_asc(self, storage: SQLiteLocalStorage) -> None:
        """Queue is FIFO — oldest entries first."""
        old = _make_log_entry(
            entry_id="old", timestamp=datetime(2024, 6, 14, 10, 0, 0)
        )
        new = _make_log_entry(
            entry_id="new", timestamp=datetime(2024, 6, 15, 10, 0, 0)
        )
        storage.insert_log_entry(new)
        storage.insert_log_entry(old)

        queue = storage.get_sync_queue()
        assert queue[0].id == "old"
        assert queue[1].id == "new"

    def test_returns_empty_when_all_synced(self, storage: SQLiteLocalStorage) -> None:
        """Empty list when no unsynced entries exist."""
        entry = _make_log_entry(synced=True)
        storage.insert_log_entry(entry)

        queue = storage.get_sync_queue()
        assert queue == []


# --- get_exception_sync_queue tests ---


class TestGetExceptionSyncQueue:
    """Tests for exception sync queue."""

    def test_returns_unsynced_exceptions(self, storage: SQLiteLocalStorage) -> None:
        """Only unsynced exceptions are returned."""
        exc = _make_quick_exception()
        storage.insert_quick_exception(exc)

        queue = storage.get_exception_sync_queue()
        assert len(queue) == 1
        assert queue[0].id == exc.id

    def test_excludes_synced_exceptions(self, storage: SQLiteLocalStorage) -> None:
        """Synced exceptions are not in the queue."""
        exc = _make_quick_exception(synced=True)
        storage.insert_quick_exception(exc)

        queue = storage.get_exception_sync_queue()
        assert queue == []


# --- mark_synced tests ---


class TestMarkSynced:
    """Tests for marking entries as synced."""

    def test_marks_log_entries_as_synced(self, storage: SQLiteLocalStorage) -> None:
        """Entries marked as synced no longer appear in sync queue."""
        entry = _make_log_entry(entry_id="to-sync")
        storage.insert_log_entry(entry)

        storage.mark_synced(["to-sync"])

        queue = storage.get_sync_queue()
        assert queue == []

    def test_marks_exceptions_as_synced(self, storage: SQLiteLocalStorage) -> None:
        """Exceptions marked as synced no longer appear in exception queue."""
        exc = _make_quick_exception(exception_id="exc-sync")
        storage.insert_quick_exception(exc)

        storage.mark_synced(["exc-sync"])

        queue = storage.get_exception_sync_queue()
        assert queue == []

    def test_handles_empty_list(self, storage: SQLiteLocalStorage) -> None:
        """Calling mark_synced with empty list doesn't raise."""
        storage.mark_synced([])

    def test_handles_nonexistent_ids(self, storage: SQLiteLocalStorage) -> None:
        """Non-existent IDs are silently ignored."""
        storage.mark_synced(["nonexistent-id"])


# --- get_queue_oldest_date tests ---


class TestGetQueueOldestDate:
    """Tests for getting the oldest unsynced entry date."""

    def test_returns_none_when_empty(self, storage: SQLiteLocalStorage) -> None:
        """Returns None when no unsynced entries exist."""
        result = storage.get_queue_oldest_date()
        assert result is None

    def test_returns_oldest_date(self, storage: SQLiteLocalStorage) -> None:
        """Returns the date of the earliest unsynced entry."""
        old = _make_log_entry(
            entry_id="old", timestamp=datetime(2024, 6, 10, 10, 0, 0)
        )
        new = _make_log_entry(
            entry_id="new", timestamp=datetime(2024, 6, 15, 10, 0, 0)
        )
        storage.insert_log_entry(old)
        storage.insert_log_entry(new)

        result = storage.get_queue_oldest_date()
        assert result == date(2024, 6, 10)

    def test_ignores_synced_entries(self, storage: SQLiteLocalStorage) -> None:
        """Synced entries are not considered for oldest date."""
        old_synced = _make_log_entry(
            entry_id="old", timestamp=datetime(2024, 6, 10, 10, 0, 0), synced=True
        )
        new_unsynced = _make_log_entry(
            entry_id="new", timestamp=datetime(2024, 6, 15, 10, 0, 0)
        )
        storage.insert_log_entry(old_synced)
        storage.insert_log_entry(new_unsynced)

        result = storage.get_queue_oldest_date()
        assert result == date(2024, 6, 15)


# --- get_last_valid_hash tests ---


class TestGetLastValidHash:
    """Tests for retrieving the last valid hash."""

    def test_returns_none_when_empty(self, storage: SQLiteLocalStorage) -> None:
        """Returns None when no entries exist."""
        result = storage.get_last_valid_hash()
        assert result is None

    def test_returns_latest_hash(self, storage: SQLiteLocalStorage) -> None:
        """Returns the hash of the most recent entry by timestamp."""
        old = _make_log_entry(
            entry_id="old",
            timestamp=datetime(2024, 6, 15, 10, 0, 0),
            hash_val="hash_old",
        )
        new = _make_log_entry(
            entry_id="new",
            timestamp=datetime(2024, 6, 15, 10, 5, 0),
            hash_val="hash_new",
        )
        storage.insert_log_entry(old)
        storage.insert_log_entry(new)

        result = storage.get_last_valid_hash()
        assert result == "hash_new"


# --- Write retry mechanism tests ---


class TestWriteRetry:
    """Tests for the write retry mechanism (R1.8)."""

    def test_failed_write_adds_to_pending(self, storage: SQLiteLocalStorage) -> None:
        """A failed write retains the entry in memory for retry."""
        entry = _make_log_entry(entry_id="retry-me")

        # Insert it once to cause a UNIQUE constraint violation on next try
        storage.insert_log_entry(entry)
        # Create a new entry with the same ID to force failure
        duplicate = _make_log_entry(entry_id="retry-me", hash_val="different")
        result = storage.insert_log_entry(duplicate)

        assert result is False
        assert storage.get_pending_retry_count() > 0

    def test_pending_retries_processed_on_next_insert(
        self, storage: SQLiteLocalStorage
    ) -> None:
        """Pending retries are attempted on the next insert call."""
        # Manually add a pending retry with a fresh entry
        entry = _make_log_entry(entry_id="pending-entry")
        storage._pending_retries.append((entry, 1))

        # Trigger retry processing by inserting another entry
        another = _make_log_entry(entry_id="trigger-entry")
        storage.insert_log_entry(another)

        # The pending entry should have been written
        assert storage.get_pending_retry_count() == 0
        entries = storage.get_entries_for_date(entry.timestamp.date())
        ids = [e.id for e in entries]
        assert "pending-entry" in ids

    def test_discard_after_max_retries(self, storage: SQLiteLocalStorage) -> None:
        """Entries are discarded after MAX_RETRY_ATTEMPTS failures."""
        entry = _make_log_entry(entry_id="doomed")
        # Set retry count at max to trigger discard
        storage._pending_retries.append((entry, MAX_RETRY_ATTEMPTS))

        # Trigger processing
        another = _make_log_entry(entry_id="trigger")
        storage.insert_log_entry(another)

        # The "doomed" entry should be discarded, not in pending or DB
        assert storage.get_pending_retry_count() == 0
        entries = storage.get_entries_for_date(entry.timestamp.date())
        ids = [e.id for e in entries]
        assert "doomed" not in ids

    def test_retry_count_increments_on_failure(
        self, storage: SQLiteLocalStorage
    ) -> None:
        """Each failed retry attempt increments the count."""
        entry = _make_log_entry(entry_id="will-fail")
        # First, insert the entry normally so a re-insert fails
        storage.insert_log_entry(entry)

        # Now add the same entry to pending retries (it will fail due to dup)
        storage._pending_retries.append((entry, 1))
        storage._process_pending_retries()

        # Should still be pending with incremented count
        assert len(storage._pending_retries) == 1
        assert storage._pending_retries[0][1] == 2

    def test_exception_retry_discard_after_max(
        self, storage: SQLiteLocalStorage
    ) -> None:
        """Quick exceptions are discarded after MAX_RETRY_ATTEMPTS."""
        exc = _make_quick_exception(exception_id="doomed-exc")
        storage._pending_exception_retries.append((exc, MAX_RETRY_ATTEMPTS))

        # Trigger processing
        another = _make_quick_exception(exception_id="trigger-exc")
        storage.insert_quick_exception(another)

        assert len(storage._pending_exception_retries) == 0


# --- Heartbeat tests ---


class TestHeartbeat:
    """Tests for heartbeat recording."""

    def test_insert_successful_heartbeat(self, storage: SQLiteLocalStorage) -> None:
        """Successful heartbeat is recorded."""
        result = storage.insert_heartbeat(datetime(2024, 6, 15, 12, 0, 0), True)
        assert result is True

    def test_insert_failed_heartbeat_with_error(
        self, storage: SQLiteLocalStorage
    ) -> None:
        """Failed heartbeat with error message is recorded."""
        result = storage.insert_heartbeat(
            datetime(2024, 6, 15, 12, 0, 0), False, "Connection timeout"
        )
        assert result is True


# --- Config tests ---


class TestConfig:
    """Tests for config key-value storage."""

    def test_set_and_get_config(self, storage: SQLiteLocalStorage) -> None:
        """Config values can be set and retrieved."""
        storage.set_config("employee_id", "EMP001")
        result = storage.get_config("employee_id")
        assert result == "EMP001"

    def test_get_missing_config_returns_none(
        self, storage: SQLiteLocalStorage
    ) -> None:
        """Getting a non-existent key returns None."""
        result = storage.get_config("nonexistent")
        assert result is None

    def test_update_existing_config(self, storage: SQLiteLocalStorage) -> None:
        """Setting an existing key overwrites the value."""
        storage.set_config("key", "value1")
        storage.set_config("key", "value2")
        result = storage.get_config("key")
        assert result == "value2"


# --- Sync batch tests ---


class TestSyncBatch:
    """Tests for sync batch insertion."""

    def test_insert_sync_batch(self, storage: SQLiteLocalStorage) -> None:
        """Sync batch is stored successfully."""
        result = storage.insert_sync_batch(
            batch_id="batch-1",
            batch_date=date(2024, 6, 15),
            payload={"entries": [], "exceptions": []},
            created_at=datetime(2024, 6, 16, 0, 0, 30),
        )
        assert result is True


# --- Error handling tests ---


class TestErrorHandling:
    """Tests for graceful error handling (no crashes)."""

    def test_get_entries_returns_empty_on_error(self) -> None:
        """get_entries_for_date returns empty list on DB errors."""
        storage = SQLiteLocalStorage(":memory:")
        # Drop the table to simulate an error
        with storage._get_connection() as conn:
            conn.execute("DROP TABLE log_entries")

        result = storage.get_entries_for_date(date(2024, 6, 15))
        assert result == []

    def test_get_sync_queue_returns_empty_on_error(self) -> None:
        """get_sync_queue returns empty list on DB errors."""
        storage = SQLiteLocalStorage(":memory:")
        with storage._get_connection() as conn:
            conn.execute("DROP TABLE log_entries")

        result = storage.get_sync_queue()
        assert result == []

    def test_get_last_valid_hash_returns_none_on_error(self) -> None:
        """get_last_valid_hash returns None on DB errors."""
        storage = SQLiteLocalStorage(":memory:")
        with storage._get_connection() as conn:
            conn.execute("DROP TABLE log_entries")

        result = storage.get_last_valid_hash()
        assert result is None

    def test_mark_synced_handles_error_gracefully(self) -> None:
        """mark_synced doesn't crash on DB errors."""
        storage = SQLiteLocalStorage(":memory:")
        with storage._get_connection() as conn:
            conn.execute("DROP TABLE log_entries")

        # Should not raise
        storage.mark_synced(["some-id"])
