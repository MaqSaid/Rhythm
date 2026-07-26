"""Tracker domain models — immutable dataclasses for activity logging and sync.

All models use frozen dataclasses to enforce immutability, ensuring that
domain objects cannot be accidentally mutated after creation. This supports
the integrity guarantees required by the hash-chain mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from shared.enums import ActivityStatus, ExceptionCategory, LocationType


@dataclass(frozen=True)
class LogEntry:
    """A single 5-minute activity log entry recorded by the Tracker.

    Each entry captures the employee's activity status and detected location
    at a clock-aligned 5-minute boundary. Entries are chained via SHA-256
    hashes to provide cryptographic tamper resistance.

    Attributes:
        id: Unique identifier (UUID4 hex string).
        timestamp: UTC timestamp aligned to a 5-minute clock boundary.
        employee_id: Identifier of the employee this entry belongs to.
        status: Binary activity status (Online or Idle).
        location: Detected work location (office or home).
        hash: SHA-256 hex digest of this entry's content chained with previous_hash.
        previous_hash: SHA-256 hex digest of the preceding entry in the chain.
        synced: Whether this entry has been successfully pushed to the Central Store.
        integrity_flag: Set to "Integrity Violation" if hash chain verification
            detected tampering; None otherwise.
        time_drift_flag: Set to "Clock Drift Detected" if NTP drift > 2 min,
            "NTP Unavailable" if NTP server unreachable, or None if time verified OK.
        detection_error: Reason string if location detection failed (e.g., timeout,
            config error); None if detection succeeded.
    """

    id: str
    timestamp: datetime
    employee_id: str
    status: ActivityStatus
    location: LocationType
    hash: str
    previous_hash: str
    synced: bool = False
    integrity_flag: str | None = None
    time_drift_flag: str | None = None
    detection_error: str | None = None


@dataclass(frozen=True)
class QuickException:
    """A quick exception recorded via the desktop toast notification.

    When an employee returns from an idle period exceeding the auto-exempt
    threshold, they can tap a category button on the toast to explain the
    absence. This dataclass captures that one-click exception report.

    Attributes:
        id: Unique identifier (UUID4 hex string).
        employee_id: Identifier of the employee who reported the exception.
        timestamp: UTC timestamp of when the idle period ended (activity resumed).
        category: The exception category selected by the employee.
        duration_minutes: Duration of the idle period in minutes, auto-calculated
            from the idle start to the resume point.
        synced: Whether this exception has been successfully pushed to the Central Store.
    """

    id: str
    employee_id: str
    timestamp: datetime
    category: ExceptionCategory
    duration_minutes: int
    synced: bool = False


@dataclass(frozen=True)
class SyncBatch:
    """A batch of log entries and exceptions prepared for nightly sync.

    The Sync Engine aggregates the previous 24 hours of data into a SyncBatch
    at midnight, then pushes it to the Central Store. NTP validation metadata
    is attached to the batch to indicate time verification status.

    Attributes:
        id: Unique identifier (UUID4 hex string).
        batch_date: The calendar date this batch covers.
        entries: List of LogEntry objects included in this sync batch.
        exceptions: List of QuickException objects included in this sync batch.
        created_at: UTC timestamp of when this batch was assembled.
        time_drift_applied: Whether NTP offset correction was applied to timestamps.
        ntp_offset_seconds: The NTP offset in seconds applied to entries, or None
            if NTP was unavailable or no drift was detected.
    """

    id: str
    batch_date: date
    entries: list[LogEntry]
    exceptions: list[QuickException]
    created_at: datetime
    time_drift_applied: bool = False
    ntp_offset_seconds: float | None = None
