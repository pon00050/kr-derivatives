"""Tests for composite_score() in forensic/signals.py."""

from __future__ import annotations

from datetime import date

import pytest

from kr_derivatives.contracts.convertible_bond import CBSpec
from kr_derivatives.contracts.base import ContractType
from kr_derivatives.forensic.signals import composite_score


@pytest.fixture
def otm_cb() -> CBSpec:
    """OTM CB: stock price will be below exercise price."""
    return CBSpec(
        contract_type=ContractType.CB,
        corp_code="00100001",
        exercise_price=10_000.0,
        issue_date=date(2022, 1, 15),
        maturity_date=date(2025, 1, 15),
        refixing_floor=0.70,
        bond_type="CB",
    )


@pytest.fixture
def itm_cb() -> CBSpec:
    """ITM CB: stock price will exceed exercise price."""
    return CBSpec(
        contract_type=ContractType.CB,
        corp_code="00200002",
        exercise_price=10_000.0,
        issue_date=date(2022, 6, 1),
        maturity_date=date(2024, 6, 1),
        refixing_floor=0.70,
        bond_type="CB",
    )


class TestCompositeScore:
    def test_otm_returns_low_severity(self, otm_cb):
        result = composite_score(otm_cb, stock_price=8_000.0, sigma=0.35, r=0.035)
        assert result["composite_severity"] == "low"
        assert result["composite_flag"] is False

    def test_itm_returns_medium_severity(self, itm_cb):
        # S=10_500 / K=10_000 = 1.05 → medium (>1.00 but <=1.10)
        result = composite_score(itm_cb, stock_price=10_500.0, sigma=0.35, r=0.035)
        assert result["composite_severity"] == "medium"
        assert result["composite_flag"] is True

    def test_deep_itm_returns_high_severity(self, itm_cb):
        # S=12_000 / K=10_000 = 1.20 → high (>1.10)
        result = composite_score(itm_cb, stock_price=12_000.0, sigma=0.35, r=0.035)
        assert result["composite_severity"] == "high"
        assert result["composite_flag"] is True

    def test_has_repricing_score_false(self, otm_cb):
        """Phase 2 not implemented yet."""
        result = composite_score(otm_cb, stock_price=8_000.0, sigma=0.35, r=0.035)
        assert result["has_repricing_score"] is False

    def test_includes_issuance_score(self, otm_cb):
        result = composite_score(otm_cb, stock_price=8_000.0, sigma=0.35, r=0.035)
        assert "issuance_score" in result
        assert isinstance(result["issuance_score"], dict)
        assert "moneyness" in result["issuance_score"]

    def test_corp_code_propagated(self, otm_cb):
        result = composite_score(otm_cb, stock_price=8_000.0, sigma=0.35, r=0.035)
        assert result["corp_code"] == "00100001"

    def test_requires_sigma_or_price_series(self, otm_cb):
        with pytest.raises(ValueError, match="price_series or sigma"):
            composite_score(otm_cb, stock_price=8_000.0)

    def test_severity_boundary_at_1_00(self, itm_cb):
        # Exactly at moneyness=1.0 → should NOT flag (> not >=)
        result = composite_score(itm_cb, stock_price=10_000.0, sigma=0.35, r=0.035)
        assert result["composite_severity"] == "low"
        assert result["composite_flag"] is False

    def test_severity_boundary_at_1_10(self, itm_cb):
        # Moneyness just above 1.10 → high
        result = composite_score(itm_cb, stock_price=11_100.0, sigma=0.35, r=0.035)
        assert result["composite_severity"] == "high"
