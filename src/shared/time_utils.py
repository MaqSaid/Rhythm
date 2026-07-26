"""UTC time utilities for clock-aligned boundaries and review period calculations."""

from datetime import UTC, date, datetime, time, timedelta

from shared.enums import ReviewPeriodType
from shared.work_schedule import WorkSchedulePattern


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime.

    Returns:
        Current UTC datetime with tzinfo set.
    """
    return datetime.now(tz=UTC)


def get_next_5min_boundary(now: datetime) -> datetime:
    """Return the next clock-aligned 5-minute boundary >= now.

    If `now` is already exactly on a 5-minute boundary, returns `now` unchanged.

    Args:
        now: The reference datetime (should be timezone-aware).

    Returns:
        The smallest datetime >= now where minutes are divisible by 5
        and seconds/microseconds are zero.
    """
    # Truncate to the current minute boundary
    truncated = now.replace(second=0, microsecond=0)

    # If now is already exactly on a 5-min boundary (no seconds/microseconds)
    if truncated == now and truncated.minute % 5 == 0:
        return now

    # Find the next 5-minute mark
    minutes_past = truncated.minute % 5
    if minutes_past == 0 and truncated == now:
        return truncated
    elif minutes_past == 0:
        # Current minute is divisible by 5 but now has seconds/microseconds
        next_boundary = truncated + timedelta(minutes=5)
    else:
        minutes_to_add = 5 - minutes_past
        next_boundary = truncated + timedelta(minutes=minutes_to_add)

    return next_boundary


def get_review_period_bounds(
    period_type: ReviewPeriodType, reference_date: date
) -> tuple[date, date]:
    """Return the (start, end) dates for the review period containing reference_date.

    Args:
        period_type: The type of review period (weekly/fortnightly/monthly).
        reference_date: A date within the desired review period.

    Returns:
        A tuple of (start_date, end_date) inclusive for the period.
    """
    if period_type == ReviewPeriodType.WEEKLY:
        # Week starts on Monday (weekday() == 0)
        start = reference_date - timedelta(days=reference_date.weekday())
        end = start + timedelta(days=6)
        return (start, end)

    elif period_type == ReviewPeriodType.FORTNIGHTLY:
        # Two-week periods anchored to ISO week number (odd weeks start a period)
        iso_year, iso_week, _ = reference_date.isocalendar()
        # Determine if this is the first or second week of the fortnight
        # Odd ISO weeks start a new fortnight
        if iso_week % 2 == 1:
            period_start_week = iso_week
        else:
            period_start_week = iso_week - 1

        # Calculate the Monday of the period start week
        jan4 = date(iso_year, 1, 4)  # Jan 4 is always in ISO week 1
        start_of_week1 = jan4 - timedelta(days=jan4.weekday())
        start = start_of_week1 + timedelta(weeks=period_start_week - 1)
        end = start + timedelta(days=13)
        return (start, end)

    elif period_type == ReviewPeriodType.MONTHLY:
        # Calendar month
        start = reference_date.replace(day=1)
        # Last day of month
        if start.month == 12:
            end = date(start.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(start.year, start.month + 1, 1) - timedelta(days=1)
        return (start, end)

    else:
        raise ValueError(f"Unknown review period type: {period_type}")


def is_within_work_schedule(
    timestamp: datetime, pattern: WorkSchedulePattern
) -> bool:
    """Check if a timestamp falls within any of the pattern's time blocks.

    Args:
        timestamp: The datetime to check.
        pattern: The work schedule pattern with time blocks.

    Returns:
        True if the timestamp's time falls within any time block.
    """
    check_time: time = timestamp.time()

    for block in pattern.blocks:
        if block.start <= check_time < block.end:
            return True

    return False
