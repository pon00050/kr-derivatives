"""Shared pytest fixtures for kr-derivatives tests."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from kr_derivatives.contracts.convertible_bond import CBSpec
from kr_derivatives.contracts.base import ContractType


@pytest.fixture
def sample_cb() -> CBSpec:
    """Representative OTM convertible bond at issuance."""
    return CBSpec(
        contract_type=ContractType.CB,
        corp_code="01051092",
        exercise_price=10_000.0,
        issue_date=date(2022, 1, 15),
        maturity_date=date(2025, 1, 15),
        refixing_floor=0.70,
        bond_type="CB",
        issue_amount=5_000_000_000.0,
    )


@pytest.fixture
def itm_cb() -> CBSpec:
    """ITM convertible bond — stock above conversion price at issue."""
    return CBSpec(
        contract_type=ContractType.CB,
        corp_code="01207761",
        exercise_price=10_000.0,
        issue_date=date(2022, 6, 1),
        maturity_date=date(2024, 6, 1),
        refixing_floor=0.70,
        bond_type="CB",
    )


@pytest.fixture
def price_series() -> pd.Series:
    """250-day synthetic price series with known drift and vol.

    Log-returns ~ N(0, 0.02) daily => annualized vol ~ 0.02 * sqrt(252) ~ 0.317.
    """
    rng = np.random.default_rng(42)
    n = 250
    log_returns = rng.normal(0, 0.02, n)
    prices = 10_000 * np.exp(np.cumsum(log_returns))
    return pd.Series(prices)


@pytest.fixture
def market_data() -> dict:
    """Standard market parameters used across tests."""
    return {
        "sigma": 0.35,
        "r": 0.035,
        "stock_price": 8_500.0,
    }
