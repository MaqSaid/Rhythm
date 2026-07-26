"""Activity Monitor domain logic — pure status determination based on idle duration.

This module implements the core activity monitoring logic for the Tracker.
It determines whether an employee is Online or Idle based on the duration
since their last detected activity signal (keyboard, mouse, scroll, or
active window change).

All I/O is delegated to the injected ActivityMonitorPort — this class
contains only pure domain logic with no file access, network calls, or
platform-specific code.

Requirements implemented:
    R1.1: Detect keyboard, mouse, scroll, active window changes as activity signals
          (via the ActivityMonitorPort — domain just uses it)
    R1.2: Log a record every 5 minutes aligned to clock boundaries
    R1.4: When no activity for idle_threshold continuous minutes, set status to Idle
    R1.5: When activity resumes after Idle, set status back to Online
    R1.6: When laptop is off/sleep, log no entries (handled by orchestrator — no
          cycle runs while sleeping)
    R1.7: Resume at next clock-aligned boundary after wake (handled by orchestrator)
"""

from __future__ import annotations

from datetime import timedelta

from shared.config import TenantConfig
from shared.enums import ActivityStatus
from tracker.ports.input_monitor import ActivityMonitorPort


class ActivityMonitorService:
    """Pure domain service for activity status determination.

    This service encapsulates the logic for deciding whether an employee
    is currently Online or Idle based on how long they have been inactive.
    The idle threshold is configurable per tenant.

    The service does NOT control the 5-minute cycle timing or handle
    sleep/wake events — that responsibility belongs to the orchestrator
    (TrackerLoop). This class is called once per cycle to determine the
    current status.

    Args:
        activity_monitor: Port providing hardware-level activity detection.
        config: Tenant configuration containing idle_threshold_minutes.
    """

    def __init__(
        self,
        activity_monitor: ActivityMonitorPort,
        config: TenantConfig,
    ) -> None:
        self._activity_monitor = activity_monitor
        self._config = config

    def determine_status(self) -> ActivityStatus:
        """Determine the current activity status based on idle duration.

        Checks how long since the last detected activity signal. If the
        idle duration meets or exceeds the configured idle threshold,
        the status is Idle; otherwise, Online.

        Returns:
            ActivityStatus.IDLE if no activity for >= idle_threshold_minutes.
            ActivityStatus.ONLINE otherwise.
        """
        idle_duration = self.get_idle_duration()
        threshold = timedelta(minutes=self._config.idle_threshold_minutes)

        if idle_duration >= threshold:
            return ActivityStatus.IDLE
        return ActivityStatus.ONLINE

    def get_idle_duration(self) -> timedelta:
        """Get how long since the last detected activity signal.

        Delegates to the activity monitor port to retrieve the continuous
        inactivity duration from the last event.

        Returns:
            A timedelta representing time since the last activity event.
        """
        return self._activity_monitor.get_idle_duration()

    def is_resuming_from_idle(self, previous_status: ActivityStatus) -> bool:
        """Check if the employee is resuming activity after an Idle period.

        This is True when the previous status was Idle and the current
        status is Online — meaning the employee has just become active
        again. The orchestrator uses this to trigger idle-return
        notifications (if the idle duration exceeded the auto-exempt
        threshold).

        Args:
            previous_status: The status recorded in the previous 5-min cycle.

        Returns:
            True if transitioning from Idle to Online, False otherwise.
        """
        if previous_status != ActivityStatus.IDLE:
            return False
        current_status = self.determine_status()
        return current_status == ActivityStatus.ONLINE

    def should_log_entry(self) -> bool:
        """Determine whether a log entry should be recorded this cycle.

        While the Tracker is running (laptop is on and not sleeping),
        a log entry is always recorded at each 5-minute clock-aligned
        boundary. The orchestrator is responsible for not calling this
        during sleep — if this method is called, logging should happen.

        Returns:
            True — always logs on each 5-minute cycle while running.
        """
        return True
