"""Date utility functions for kr-derivatives."""

from __future__ import annotations

from datetime import date, datetime


def days_to_expiry(issue_date: date | datetime | str, maturity_date: date | datetime | str) -> float:
    """Return time to expiry in years (actual/365 convention).

    Args:
        issue_date: CB issuance date (start of time window).
        maturity_date: CB maturity / option expiry date.

    Returns:
        Float years. Returns 0.0 if maturity <= issue.
    """
    def _to_date(d: date | datetime | str) -> date:
        if isinstance(d, str):
            return date.fromisoformat(d)
        if isinstance(d, datetime):
            return d.date()
        return d

    t = (_to_date(maturity_date) - _to_date(issue_date)).days / 365.0
    return max(t, 0.0)


def ensure_date(d: date | datetime | str) -> date:
    """Coerce str/datetime to date."""
    if isinstance(d, str):
        return date.fromisoformat(d)
    if isinstance(d, datetime):
        return d.date()
    return d
