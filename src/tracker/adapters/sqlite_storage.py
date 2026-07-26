"""SQLite Local Storage adapter implementing LocalStoragePort.

Provides persistent local storage for the Tracker using SQLite in WAL mode
to prevent corruption on power loss/crash. Uses context managers for all
database connections and handles write retries with bounded attempts.

Requirements:
    R1.8: Write retry — retain in memory, retry next cycle, max 3 attempts before discard.
    R4.1: Run as system service (adapter handles DB file path in system-protected dir).
    R51.12: WAL mode for SQLite to prevent corruption on power loss/crash.
    R46.4: Use context managers for all DB connections.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime

from shared.enums import ActivityStatus, ExceptionCategory, LocationType
from tracker.domain.models import LogEntry, QuickException

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS log_entries (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Online', 'Idle')),
    location TEXT NOT NULL CHECK(location IN ('office', 'home')),
    hash TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    synced INTEGER DEFAULT 0,
    integrity_flag TEXT,
    time_drift_flag TEXT,
    detection_error TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quick_exceptions (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    synced INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_queue (
    id TEXT PRIMARY KEY,
    batch_date TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_attempt TEXT
);

CREATE TABLE IF NOT EXISTS heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    success INTEGER NOT NULL,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_log_entries_synced ON log_entries(synced);
CREATE INDEX IF NOT EXISTS idx_log_entries_timestamp ON log_entries(timestamp);
CREATE INDEX IF NOT EXISTS idx_sync_queue_created ON sync_queue(created_at);
"""

# Maximum retry attempts before discarding a failed write
MAX_RETRY_ATTEMPTS = 3


class SQLiteLocalStorage:
    """SQLite-based local storage adapter for the Tracker.

    Stores activity log entries, quick exceptions, sync queue batches,
    heartbeats, and configuration key-value pairs in a local SQLite database.

    The database uses WAL (Write-Ahead Logging) mode to prevent corruption
    on power loss or crash, and a busy_timeout of 5000ms for lock contention.

    A single persistent connection is maintained for the lifetime of the
    adapter (single-process Tracker design). Context managers are used for
    transactional access to ensure proper commit/rollback semantics.

    Args:
        db_path: Path to the SQLite database file. Use ':memory:' for testing.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._pending_retries: list[tuple[LogEntry, int]] = []
        self._pending_exception_retries: list[tuple[QuickException, int]] = []
        self._initialize_schema()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for transactional database access.

        Yields the persistent connection. Commits on success, rolls back
        on failure. The connection itself remains open for reuse.
        """
        try:
            yield self._conn
            self._conn.commit()
        except sqlite3.Error:
            self._conn.rollback()
            raise

    def _initialize_schema(self) -> None:
        """Create the database schema if tables don't exist.

        Enables WAL mode and sets busy_timeout, then creates all tables
        and indexes.
        """
        with self._get_connection() as conn:
            conn.executescript(_SCHEMA_SQL)

    def close(self) -> None:
        """Close the database connection.

        Should be called when the Tracker service is shutting down.
        """
        self._conn.close()

    def insert_log_entry(self, entry: LogEntry) -> bool:
        """Persist a single activity log entry to local storage.

        On failure, retains the entry in memory for retry on the next cycle.
        After MAX_RETRY_ATTEMPTS failures, the entry is discarded.

        Args:
            entry: The LogEntry to store.

        Returns:
            True if the entry was successfully written, False if the write failed.
        """
        # First, process any pending retries
        self._process_pending_retries()

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO log_entries
                    (id, timestamp, employee_id, status, location, hash,
                     previous_hash, synced, integrity_flag, time_drift_flag,
                     detection_error, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry.id,
                        entry.timestamp.isoformat(),
                        entry.employee_id,
                        entry.status.value,
                        entry.location.value,
                        entry.hash,
                        entry.previous_hash,
                        1 if entry.synced else 0,
                        entry.integrity_flag,
                        entry.time_drift_flag,
                        entry.detection_error,
                        0,
                    ),
                )
            return True
        except sqlite3.Error:
            # Retain in memory for retry next cycle
            self._pending_retries.append((entry, 1))
            return False

    def insert_quick_exception(self, exception: QuickException) -> bool:
        """Persist a quick exception from the idle-return toast notification.

        On failure, retains the exception in memory for retry on the next cycle.
        After MAX_RETRY_ATTEMPTS failures, the exception is discarded.

        Args:
            exception: The QuickException record to store.

        Returns:
            True if the exception was successfully written, False otherwise.
        """
        # Process any pending exception retries
        self._process_pending_exception_retries()

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO quick_exceptions
                    (id, employee_id, timestamp, category, duration_minutes, synced)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        exception.id,
                        exception.employee_id,
                        exception.timestamp.isoformat(),
                        exception.category.value,
                        exception.duration_minutes,
                        1 if exception.synced else 0,
                    ),
                )
            return True
        except sqlite3.Error:
            self._pending_exception_retries.append((exception, 1))
            return False

    def get_entries_for_date(self, target_date: date) -> list[LogEntry]:
        """Retrieve all log entries for a specific calendar date.

        Args:
            target_date: The date to query entries for.

        Returns:
            A list of LogEntry records for the given date, ordered
            chronologically by timestamp. Empty list if no entries or on error.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM log_entries
                    WHERE date(timestamp) = ?
                    ORDER BY timestamp""",
                    (target_date.isoformat(),),
                )
                rows = cursor.fetchall()
                return [self._row_to_log_entry(row) for row in rows]
        except sqlite3.Error:
            return []

    def get_sync_queue(self) -> list[LogEntry]:
        """Retrieve all log entries pending synchronization.

        Returns:
            A list of LogEntry records where synced = 0, ordered
            chronologically (oldest first) for FIFO push.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM log_entries
                    WHERE synced = 0
                    ORDER BY timestamp ASC""",
                )
                rows = cursor.fetchall()
                return [self._row_to_log_entry(row) for row in rows]
        except sqlite3.Error:
            return []

    def get_exception_sync_queue(self) -> list[QuickException]:
        """Retrieve all quick exceptions pending synchronization.

        Returns:
            A list of QuickException records where synced = 0, ordered
            chronologically.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM quick_exceptions
                    WHERE synced = 0
                    ORDER BY timestamp ASC""",
                )
                rows = cursor.fetchall()
                return [self._row_to_quick_exception(row) for row in rows]
        except sqlite3.Error:
            return []

    def mark_synced(self, entry_ids: list[str]) -> None:
        """Mark entries as successfully synced to the remote store.

        Updates both log_entries and quick_exceptions tables.

        Args:
            entry_ids: List of entry identifiers that were successfully pushed.
        """
        if not entry_ids:
            return

        try:
            with self._get_connection() as conn:
                placeholders = ",".join("?" for _ in entry_ids)
                conn.execute(
                    f"UPDATE log_entries SET synced = 1 WHERE id IN ({placeholders})",
                    entry_ids,
                )
                conn.execute(
                    f"UPDATE quick_exceptions SET synced = 1 WHERE id IN ({placeholders})",
                    entry_ids,
                )
        except sqlite3.Error:
            pass

    def get_queue_oldest_date(self) -> date | None:
        """Get the date of the oldest entry in the sync queue.

        Returns:
            The date of the oldest unsynced entry, or None if the
            sync queue is empty.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT MIN(date(timestamp)) as oldest FROM log_entries WHERE synced = 0",
                )
                row = cursor.fetchone()
                if row and row["oldest"]:
                    return date.fromisoformat(row["oldest"])
                return None
        except sqlite3.Error:
            return None

    def get_last_valid_hash(self) -> str | None:
        """Retrieve the hash of the most recent log entry.

        Used at startup and before sync to resume hash chain computation.

        Returns:
            The SHA-256 hex digest of the last entry, or None if no entries exist.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT hash FROM log_entries ORDER BY timestamp DESC LIMIT 1",
                )
                row = cursor.fetchone()
                if row:
                    return row["hash"]
                return None
        except sqlite3.Error:
            return None

    def insert_heartbeat(
        self, timestamp: datetime, success: bool, error_message: str | None = None
    ) -> bool:
        """Record a heartbeat check result.

        Args:
            timestamp: When the heartbeat was sent.
            success: Whether the heartbeat reached the remote store.
            error_message: Error details if the heartbeat failed.

        Returns:
            True if the heartbeat was recorded, False on failure.
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO heartbeats (timestamp, success, error_message)
                    VALUES (?, ?, ?)""",
                    (timestamp.isoformat(), 1 if success else 0, error_message),
                )
            return True
        except sqlite3.Error:
            return False

    def insert_sync_batch(
        self, batch_id: str, batch_date: date, payload: dict, created_at: datetime
    ) -> bool:
        """Insert a sync batch into the sync queue.

        Args:
            batch_id: Unique identifier for the batch.
            batch_date: The calendar date this batch covers.
            payload: Serialized batch data.
            created_at: When the batch was assembled.

        Returns:
            True if the batch was inserted, False on failure.
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO sync_queue (id, batch_date, payload, created_at)
                    VALUES (?, ?, ?, ?)""",
                    (
                        batch_id,
                        batch_date.isoformat(),
                        json.dumps(payload),
                        created_at.isoformat(),
                    ),
                )
            return True
        except sqlite3.Error:
            return False

    def get_config(self, key: str) -> str | None:
        """Get a configuration value by key.

        Args:
            key: The configuration key.

        Returns:
            The configuration value, or None if not found.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT value FROM config WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                if row:
                    return row["value"]
                return None
        except sqlite3.Error:
            return None

    def set_config(self, key: str, value: str) -> bool:
        """Set a configuration value.

        Args:
            key: The configuration key.
            value: The configuration value.

        Returns:
            True if the value was set, False on failure.
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)""",
                    (key, value),
                )
            return True
        except sqlite3.Error:
            return False

    def get_pending_retry_count(self) -> int:
        """Return the number of entries pending retry in memory.

        Returns:
            Count of entries awaiting retry.
        """
        return len(self._pending_retries) + len(self._pending_exception_retries)

    def _process_pending_retries(self) -> None:
        """Attempt to write pending log entry retries.

        Entries that exceed MAX_RETRY_ATTEMPTS are discarded.
        """
        if not self._pending_retries:
            return

        remaining: list[tuple[LogEntry, int]] = []
        for entry, attempt_count in self._pending_retries:
            if attempt_count >= MAX_RETRY_ATTEMPTS:
                # Discard after max attempts
                continue
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        """INSERT INTO log_entries
                        (id, timestamp, employee_id, status, location, hash,
                         previous_hash, synced, integrity_flag, time_drift_flag,
                         detection_error, retry_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            entry.id,
                            entry.timestamp.isoformat(),
                            entry.employee_id,
                            entry.status.value,
                            entry.location.value,
                            entry.hash,
                            entry.previous_hash,
                            1 if entry.synced else 0,
                            entry.integrity_flag,
                            entry.time_drift_flag,
                            entry.detection_error,
                            attempt_count,
                        ),
                    )
            except sqlite3.Error:
                remaining.append((entry, attempt_count + 1))

        self._pending_retries = remaining

    def _process_pending_exception_retries(self) -> None:
        """Attempt to write pending quick exception retries.

        Exceptions that exceed MAX_RETRY_ATTEMPTS are discarded.
        """
        if not self._pending_exception_retries:
            return

        remaining: list[tuple[QuickException, int]] = []
        for exception, attempt_count in self._pending_exception_retries:
            if attempt_count >= MAX_RETRY_ATTEMPTS:
                # Discard after max attempts
                continue
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        """INSERT INTO quick_exceptions
                        (id, employee_id, timestamp, category, duration_minutes, synced)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            exception.id,
                            exception.employee_id,
                            exception.timestamp.isoformat(),
                            exception.category.value,
                            exception.duration_minutes,
                            1 if exception.synced else 0,
                        ),
                    )
            except sqlite3.Error:
                remaining.append((exception, attempt_count + 1))

        self._pending_exception_retries = remaining

    @staticmethod
    def _row_to_log_entry(row: sqlite3.Row) -> LogEntry:
        """Convert a database row to a LogEntry dataclass.

        Args:
            row: A sqlite3.Row from the log_entries table.

        Returns:
            A LogEntry instance populated from the row data.
        """
        return LogEntry(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            employee_id=row["employee_id"],
            status=ActivityStatus(row["status"]),
            location=LocationType(row["location"]),
            hash=row["hash"],
            previous_hash=row["previous_hash"],
            synced=bool(row["synced"]),
            integrity_flag=row["integrity_flag"],
            time_drift_flag=row["time_drift_flag"],
            detection_error=row["detection_error"],
        )

    @staticmethod
    def _row_to_quick_exception(row: sqlite3.Row) -> QuickException:
        """Convert a database row to a QuickException dataclass.

        Args:
            row: A sqlite3.Row from the quick_exceptions table.

        Returns:
            A QuickException instance populated from the row data.
        """
        return QuickException(
            id=row["id"],
            employee_id=row["employee_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            category=ExceptionCategory(row["category"]),
            duration_minutes=row["duration_minutes"],
            synced=bool(row["synced"]),
        )
