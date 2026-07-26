"""Port interface for structured logging.

This port abstracts the structured JSON logger, allowing all tracker
components to emit consistent log entries without coupling to the
specific file-based logging implementation.
"""

from __future__ import annotations

from typing import Any, Protocol


class StructuredLoggerPort(Protocol):
    """Protocol defining the contract for structured event logging.

    Implementations write structured JSON log entries with consistent
    fields (timestamp, level, component, event_type, message, details)
    to rotating log files (5 MB rotation, max 5 files).
    """

    def log(
        self,
        level: str,
        component: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Write a structured log entry.

        Args:
            level: Log severity level (e.g., "DEBUG", "INFO", "WARNING",
                   "ERROR", "CRITICAL").
            component: The tracker component emitting the log (e.g.,
                      "ActivityMonitor", "SyncEngine", "HashChain",
                      "NTPValidator", "FocusMode").
            event_type: A machine-readable event identifier (e.g.,
                       "activity_detected", "sync_failed",
                       "hash_chain_broken", "ntp_drift_detected").
            message: Human-readable description of the event.
            details: Optional dictionary of additional structured data
                    relevant to the event (e.g., {"drift_seconds": 145,
                    "ntp_server": "time.google.com"}). Pass None if no
                    extra details are needed.
        """
        ...
