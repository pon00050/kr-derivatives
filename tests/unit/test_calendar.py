"""Tests for KRX calendar utilities."""

from __future__ import annotations

from datetime import date

import pytest

from kr_derivatives.calendar.krx import (
    is_trading_day,
    next_trading_day,
    previous_trading_day,
    second_thursday_of_month,
    trading_days_between,
)


class TestIsTradingDay:
    def test_known_weekday_is_trading(self):
        """2024-01-02 (Tuesday) was a KRX trading day."""
        assert is_trading_day(date(2024, 1, 2)) is True

    def test_saturday_not_trading(self):
        assert is_trading_day(date(2024, 1, 6)) is False  # Saturday

    def test_sunday_not_trading(self):
        assert is_trading_day(date(2024, 1, 7)) is False  # Sunday

    def test_korean_holiday_not_trading(self):
        """Lunar New Year 2024: Feb 9-12 were KRX holidays."""
        assert is_trading_day(date(2024, 2, 9)) is False   # Friday — holiday
        assert is_trading_day(date(2024, 2, 12)) is False  # Monday — holiday


class TestNextTradingDay:
    def test_trading_day_returns_itself(self):
        d = date(2024, 1, 2)  # Known trading day
        assert next_trading_day(d) == d

    def test_weekend_advances_to_monday(self):
        saturday = date(2024, 1, 6)
        result = next_trading_day(saturday)
        assert result == date(2024, 1, 8)  # Monday


class TestPreviousTradingDay:
    def test_trading_day_returns_itself(self):
        d = date(2024, 1, 2)  # Known trading day
        assert previous_trading_day(d) == d

    def test_saturday_snaps_to_friday(self):
        saturday = date(2024, 1, 6)
        result = previous_trading_day(saturday)
        assert result == date(2024, 1, 5)  # Friday

    def test_sunday_snaps_to_friday(self):
        sunday = date(2024, 1, 7)
        result = previous_trading_day(sunday)
        assert result == date(2024, 1, 5)  # Friday

    def test_holiday_snaps_to_prior_session(self):
        """Lunar New Year 2024: Feb 9 (Fri) was a KRX holiday.
        Previous trading day should be Feb 8 (Thu)."""
        holiday = date(2024, 2, 9)
        result = previous_trading_day(holiday)
        assert result == date(2024, 2, 8)  # Thursday before 설날

    def test_result_is_always_before_or_equal_to_input(self):
        d = date(2024, 3, 15)
        result = previous_trading_day(d)
        assert result <= d


class TestSecondThursdayOfMonth:
    @pytest.mark.parametrize("year,month,expected", [
        (2024, 3, date(2024, 3, 14)),   # March 2024: 1st Thu=7th, 2nd=14th
        (2024, 6, date(2024, 6, 13)),   # June 2024: 1st Thu=6th, 2nd=13th
        (2024, 9, date(2024, 9, 12)),   # Sep 2024: 1st Thu=5th, 2nd=12th
        (2024, 12, date(2024, 12, 12)), # Dec 2024: 1st Thu=5th, 2nd=12th
    ])
    def test_quarterly_expiry_dates(self, year, month, expected):
        result = second_thursday_of_month(year, month)
        assert result == expected


class TestTradingDaysBetween:
    def test_consecutive_trading_days(self):
        """Mon to Fri of a normal week = 4 trading days (Mon exclusive, Fri inclusive)."""
        # 2024-01-08 (Mon) to 2024-01-12 (Fri) — no holidays
        count = trading_days_between(date(2024, 1, 8), date(2024, 1, 12))
        assert count == 4

    def test_same_day_is_zero(self):
        d = date(2024, 1, 2)
        count = trading_days_between(d, d)
        assert count == 0

    def test_includes_end_excludes_start(self):
        """By convention: start exclusive, end inclusive."""
        start = date(2024, 1, 8)  # Monday
        end = date(2024, 1, 9)    # Tuesday
        assert trading_days_between(start, end) == 1
