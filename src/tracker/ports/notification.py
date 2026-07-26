"""Port interfaces for toast notifications and focus mode control.

These ports abstract the OS-native notification system and the focus mode
toggle mechanism, allowing domain logic to trigger idle-return toasts and
manage notification suppression without platform coupling.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol


class ToastNotificationPort(Protocol):
    """Protocol defining the contract for desktop toast notifications.

    Implementations display OS-native toast notifications when an employee
    returns from an idle period exceeding the auto-exempt threshold. The
    toast presents category buttons for quick exception reporting and
    auto-dismisses after 5 minutes if no selection is made.
    """

    def show_idle_return_toast(
        self, idle_duration: timedelta, categories: list[str]
    ) -> str | None:
        """Display an idle-return toast notification with category options.

        Shows a desktop toast informing the employee of the idle duration
        and presenting quick-select category buttons. Auto-dismisses after
        5 minutes if no interaction occurs.

        Args:
            idle_duration: How long the employee was idle (used in the
                          notification message).
            categories: List of exception category labels to display as
                       action buttons (e.g., ["Medical Break",
                       "Client Meeting", "Hardware Issue", "Personal Leave"]).

        Returns:
            The selected category string if the employee taps a button,
            or None if the toast was dismissed or auto-expired (resulting
            in "Unmarked Idle" classification).
        """
        ...

    def is_suppressed(self) -> bool:
        """Check whether notifications are currently suppressed.

        Notifications are suppressed when Focus Mode is active.

        Returns:
            True if notifications should not be shown (Focus Mode active),
            False if notifications can be displayed normally.
        """
        ...


class FocusModePort(Protocol):
    """Protocol defining the contract for focus mode management.

    Focus mode suppresses idle-return toast notifications for a configurable
    duration (1-4 hours) while tracking continues unchanged. Focus mode
    status is private and never reported to HR.
    """

    def activate(self, duration_hours: int) -> None:
        """Activate focus mode for the specified duration.

        While active, all toast notifications are suppressed and idle
        periods are automatically classified as "Unmarked Idle".

        Args:
            duration_hours: Duration in hours (1-4) for focus mode.
        """
        ...

    def deactivate(self) -> None:
        """Manually deactivate focus mode before its timer expires.

        Resumes normal notification behavior immediately.
        """
        ...

    def is_active(self) -> bool:
        """Check whether focus mode is currently active.

        Returns:
            True if focus mode is active (timer has not expired and
            deactivate() has not been called), False otherwise.
        """
        ...

    def remaining_minutes(self) -> int:
        """Get the number of minutes remaining in the current focus session.

        Returns:
            The number of whole minutes remaining before focus mode
            auto-deactivates. Returns 0 if focus mode is not active.
        """
        ...
