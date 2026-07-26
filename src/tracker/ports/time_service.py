"""Port interface for authoritative time retrieval.

This port abstracts the NTP time query mechanism, allowing the domain to
obtain a trusted external time source for drift detection and timestamp
correction without coupling to the specific NTP implementation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class TimeServicePort(Protocol):
    """Protocol defining the contract for authoritative time retrieval.

    Implementations query an external NTP server (e.g., time.google.com)
    via UDP with a 5-second timeout to obtain a trusted UTC timestamp.
    This is used to detect local clock drift (>2 minutes triggers a flag)
    and apply offset corrections to logged timestamps.
    """

    def get_authoritative_time(self) -> datetime | None:
        """Query the external time service for the current authoritative UTC time.

        Returns:
            A timezone-aware UTC datetime from the NTP server if the query
            succeeds within the 5-second timeout, or None if the server is
            unreachable or the query times out. When None is returned, the
            system should proceed with local time and mark entries as
            "NTP Unavailable".
        """
        ...
