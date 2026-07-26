"""Port interface for activity monitoring on the employee's device.

This port abstracts the underlying input detection mechanism (keyboard, mouse,
scroll, active window changes) so that the domain logic remains decoupled from
the specific platform implementation (e.g., pynput on Windows/macOS).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol


class ActivityMonitorPort(Protocol):
    """Protocol defining the contract for hardware-level activity detection.

    Implementations are responsible for listening to input events and
    determining whether user activity has occurred within a given timeframe.
    """

    def start(self) -> None:
        """Begin listening for input activity events.

        After calling start(), the monitor should detect keyboard, mouse,
        scroll, and active window change events until stop() is called.
        """
        ...

    def stop(self) -> None:
        """Stop listening for input activity events.

        Release any resources (listeners, threads) held by the monitor.
        """
        ...

    def has_activity_since(self, since: datetime) -> bool:
        """Check whether any activity signal was detected since the given time.

        Args:
            since: A timezone-aware UTC datetime marking the start of the
                   window to check for activity.

        Returns:
            True if at least one activity event (keyboard, mouse, scroll,
            or active window change) was detected since the given time,
            False otherwise.
        """
        ...

    def get_idle_duration(self) -> timedelta:
        """Get the duration of continuous inactivity from the last event.

        Returns:
            A timedelta representing how long it has been since the last
            detected activity event. Returns timedelta(0) if activity
            is currently ongoing.
        """
        ...
