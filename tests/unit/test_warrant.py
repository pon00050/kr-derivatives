"""Tests for WarrantSpec (신주인수권부사채) contract."""

from __future__ import annotations

from datetime import date

import pytest

from kr_derivatives.contracts.warrant import WarrantSpec
from kr_derivatives.contracts.base import ContractType


class TestWarrantSpec:
    def test_contract_type_is_bw(self):
        ws = WarrantSpec(
            contract_type=ContractType.BW,
            exercise_price=5_000.0,
            issue_date=date(2023, 1, 1),
            maturity_date=date(2026, 1, 1),
        )
        assert ws.contract_type == ContractType.BW

    def test_post_init_sets_bw(self):
        """Even if constructed with wrong type, __post_init__ forces BW."""
        ws = WarrantSpec(
            contract_type=ContractType.CB,  # wrong
            exercise_price=5_000.0,
            issue_date=date(2023, 1, 1),
            maturity_date=date(2026, 1, 1),
        )
        assert ws.contract_type == ContractType.BW

    def test_defaults(self):
        ws = WarrantSpec(
            contract_type=ContractType.BW,
            exercise_price=5_000.0,
            issue_date=date(2023, 1, 1),
            maturity_date=date(2026, 1, 1),
        )
        assert ws.corp_code == ""
        assert ws.exercise_ratio == 1.0
        assert ws.separable is True

    def test_custom_fields(self):
        ws = WarrantSpec(
            contract_type=ContractType.BW,
            exercise_price=8_000.0,
            issue_date=date(2023, 6, 1),
            maturity_date=date(2025, 6, 1),
            corp_code="01234567",
            exercise_ratio=2.5,
            separable=False,
        )
        assert ws.corp_code == "01234567"
        assert ws.exercise_ratio == 2.5
        assert ws.separable is False

    def test_time_to_expiry(self):
        ws = WarrantSpec(
            contract_type=ContractType.BW,
            exercise_price=5_000.0,
            issue_date=date(2023, 1, 1),
            maturity_date=date(2026, 1, 1),
        )
        t = ws.time_to_expiry()  # from issue_date
        assert abs(t - 3.0) < 0.01  # ~3 years

    def test_time_to_expiry_custom_date(self):
        ws = WarrantSpec(
            contract_type=ContractType.BW,
            exercise_price=5_000.0,
            issue_date=date(2023, 1, 1),
            maturity_date=date(2026, 1, 1),
        )
        t = ws.time_to_expiry(date(2025, 1, 1))
        assert abs(t - 1.0) < 0.01

    def test_time_to_expiry_at_maturity(self):
        ws = WarrantSpec(
            contract_type=ContractType.BW,
            exercise_price=5_000.0,
            issue_date=date(2023, 1, 1),
            maturity_date=date(2026, 1, 1),
        )
        t = ws.time_to_expiry(date(2026, 1, 1))
        assert t == 0.0

    def test_time_to_expiry_past_maturity(self):
        ws = WarrantSpec(
            contract_type=ContractType.BW,
            exercise_price=5_000.0,
            issue_date=date(2023, 1, 1),
            maturity_date=date(2026, 1, 1),
        )
        t = ws.time_to_expiry(date(2027, 1, 1))
        assert t == 0.0  # clamped to 0
