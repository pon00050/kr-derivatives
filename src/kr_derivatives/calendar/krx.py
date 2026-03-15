"""KRX trading calendar utilities using exchange_calendars XKRX."""

from __future__ import annotations

from datetime import date, timedelta


def _get_calendar():
    """Lazy-load XKRX calendar."""
    try:
        import exchange_calendars as xcals  # type: ignore
        return xcals.get_calendar("XKRX")
    except ImportError as exc:
        raise ImportError(
            "exchange_calendars is required for KRX calendar functions. "
            "Install it with: pip install exchange-calendars"
        ) from exc


def is_trading_day(d: date) -> bool:
    """Return True if the given date is a KRX trading day."""
    cal = _get_calendar()
    return cal.is_session(d.isoformat())


def next_trading_day(d: date) -> date:
    """Return the next KRX trading day on or after the given date."""
    cal = _get_calendar()
    candidate = d
    for _ in range(30):  # max 30 days forward (covers holidays + weekends)
        if cal.is_session(candidate.isoformat()):
            return candidate
        candidate = candidate + timedelta(days=1)
    raise RuntimeError(f"Could not find next trading day within 30 days of {d}")


def previous_trading_day(d: date) -> date:
    """Return the most recent KRX trading day on or before the given date.

    If the date is itself a trading day, it is returned unchanged.
    Use this to snap a board-meeting date (which may fall on a weekend or
    public holiday) to the last available closing price before the meeting.

    Args:
        d: Calendar date to snap backward from.

    Returns:
        The date itself if it is a KRX session, otherwise the nearest
        prior session.

    Raises:
        RuntimeError: If no trading day is found within 30 days prior.
    """
    cal = _get_calendar()
    candidate = d
    for _ in range(30):  # max 30 days back (covers long holiday blocks)
        if cal.is_session(candidate.isoformat()):
            return candidate
        candidate = candidate - timedelta(days=1)
    raise RuntimeError(f"Could not find previous trading day within 30 days of {d}")


def second_thursday_of_month(year: int, month: int) -> date:
    """Return the second Thursday of the given month.

    KOSPI200 futures and options expire on the second Thursday of the
    expiry month (quarterly: March, June, September, December).

    Args:
        year: Calendar year.
        month: Calendar month (1-12).

    Returns:
        Date of the second Thursday. If that date is a KRX holiday,
        returns the preceding trading day.
    """
    # Find first Thursday of the month
    first_day = date(year, month, 1)
    # Thursday is weekday 3 (Monday=0)
    days_to_thursday = (3 - first_day.weekday()) % 7
    first_thursday = first_day + timedelta(days=days_to_thursday)
    second_thursday = first_thursday + timedelta(weeks=1)

    # Adjust if it falls on a KRX holiday
    cal = _get_calendar()
    adjusted = second_thursday
    while not cal.is_session(adjusted.isoformat()):
        adjusted = adjusted - timedelta(days=1)

    return adjusted


def trading_days_between(start: date, end: date) -> int:
    """Return the number of KRX trading days between start (exclusive) and end (inclusive)."""
    cal = _get_calendar()
    sessions = cal.sessions_in_range(start.isoformat(), end.isoformat())
    # sessions_in_range is inclusive on both ends; subtract 1 if start is a session
    count = len(sessions)
    if cal.is_session(start.isoformat()):
        count -= 1
    return count
