"""Tests for forensic repricing signals.

Behavioral contracts:
- cb_issuance_score: ITM issuance => dilution_flag=True; OTM => False
- cb_issuance_score: moneyness = S/K exactly
- repricing_coercion_score: raises NotImplementedError (Phase 2)
"""

from __future__ import annotations

from datetime import date

import pytest

from kr_derivatives.contracts.convertible_bond import CBSpec
from kr_derivatives.contracts.base import ContractType
from kr_derivatives.forensic.repricing import cb_issuance_score, repricing_coercion_score


@pytest.fixture
def otm_cb():
    return CBSpec(
        contract_type=ContractType.CB,
        corp_code="99000001",
        exercise_price=10_000.0,
        issue_date=date(2022, 1, 1),
        maturity_date=date(2025, 1, 1),
    )


@pytest.fixture
def itm_cb():
    return CBSpec(
        contract_type=ContractType.CB,
        corp_code="99000002",
        exercise_price=10_000.0,
        issue_date=date(2022, 1, 1),
        maturity_date=date(2025, 1, 1),
    )


class TestCBIssuanceScore:
    def test_otm_not_flagged(self, otm_cb):
        """Stock below conversion price → no dilution flag."""
        score = cb_issuance_score(otm_cb, stock_price=8_500, sigma=0.35, r=0.035)
        assert score["dilution_flag"] is False

    def test_itm_flagged(self, itm_cb):
        """Stock above conversion price → dilution flag fires."""
        score = cb_issuance_score(itm_cb, stock_price=12_000, sigma=0.35, r=0.035)
        assert score["dilution_flag"] is True

    def test_atm_not_flagged(self, otm_cb):
        """Exactly ATM (S == K) → moneyness=1.0, flag does NOT fire (> not >=)."""
        score = cb_issuance_score(otm_cb, stock_price=10_000, sigma=0.35, r=0.035)
        assert score["dilution_flag"] is False
        assert score["moneyness"] == pytest.approx(1.0)

    def test_moneyness_equals_S_over_K(self, otm_cb):
        stock_price = 8_500.0
        score = cb_issuance_score(otm_cb, stock_price=stock_price, sigma=0.35, r=0.035)
        assert score["moneyness"] == pytest.approx(stock_price / otm_cb.exercise_price)

    def test_bs_call_value_positive(self, otm_cb):
        score = cb_issuance_score(otm_cb, stock_price=8_500, sigma=0.35, r=0.035)
        assert score["bs_call_value"] > 0

    def test_itm_has_higher_bs_value_than_otm(self):
        cb = CBSpec(
            contract_type=ContractType.CB,
            corp_code="test",
            exercise_price=10_000.0,
            issue_date=date(2022, 1, 1),
            maturity_date=date(2025, 1, 1),
        )
        otm_score = cb_issuance_score(cb, stock_price=8_000, sigma=0.35, r=0.035)
        itm_score = cb_issuance_score(cb, stock_price=13_000, sigma=0.35, r=0.035)
        assert itm_score["bs_call_value"] > otm_score["bs_call_value"]

    def test_corp_code_in_result(self, otm_cb):
        score = cb_issuance_score(otm_cb, stock_price=8_500, sigma=0.35, r=0.035)
        assert score["corp_code"] == otm_cb.corp_code

    def test_result_contains_expected_keys(self, otm_cb):
        score = cb_issuance_score(otm_cb, stock_price=8_500, sigma=0.35, r=0.035)
        expected_keys = {"corp_code", "valuation_date", "S", "K", "T", "sigma", "r",
                         "bs_call_value", "moneyness", "discount_to_theory",
                         "dilution_flag", "flag_reason"}
        assert set(score.keys()) == expected_keys

    def test_zero_stock_price_raises(self, otm_cb):
        with pytest.raises(ValueError):
            cb_issuance_score(otm_cb, stock_price=0, sigma=0.35, r=0.035)

    def test_zero_exercise_price_raises(self):
        bad_cb = CBSpec(
            contract_type=ContractType.CB,
            corp_code="bad",
            exercise_price=0.0,
            issue_date=date(2022, 1, 1),
            maturity_date=date(2025, 1, 1),
        )
        with pytest.raises(ValueError):
            cb_issuance_score(bad_cb, stock_price=10_000, sigma=0.35, r=0.035)

    def test_valuation_date_override(self, otm_cb):
        """Passing a valuation_date later than issue_date reduces T."""
        score_at_issue = cb_issuance_score(otm_cb, stock_price=8_500, sigma=0.35, r=0.035)
        score_later = cb_issuance_score(
            otm_cb, stock_price=8_500, sigma=0.35, r=0.035,
            valuation_date=date(2023, 1, 1)  # 1 year after issue
        )
        assert score_later["T"] < score_at_issue["T"]


class TestRepricingCoercionScore:
    def test_raises_not_implemented(self, otm_cb):
        """Phase 2: must raise NotImplementedError until SEIBRO data available."""
        with pytest.raises(NotImplementedError):
            repricing_coercion_score(otm_cb, [], None, sigma=0.35, r=0.035)
