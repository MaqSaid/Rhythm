"""Work schedule pattern definitions used by Tracker and Portal."""

from dataclasses import dataclass, field
from datetime import date, time

from shared.enums import WorkPatternType


@dataclass(frozen=True)
class TimeBlock:
    """A contiguous work time block within a day.

    Attributes:
        start: Start time of the block (inclusive).
        end: End time of the block (exclusive).
    """

    start: time
    end: time

    def __post_init__(self) -> None:
        """Validate that start is before end."""
        if self.start >= self.end:
            raise ValueError(
                f"TimeBlock start ({self.start}) must be before end ({self.end})"
            )


@dataclass
class WorkSchedulePattern:
    """A work schedule pattern defining when an employee is expected to work.

    Attributes:
        pattern_type: The type of schedule pattern.
        blocks: List of time blocks that define working hours.
        effective_from: Date from which this pattern takes effect.
    """

    pattern_type: WorkPatternType
    blocks: list[TimeBlock] = field(default_factory=list)
    effective_from: date = field(default_factory=date.today)
