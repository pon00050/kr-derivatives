"""Composite forensic scoring: combines multiple signal levels into a single score."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from ..contracts.convertible_bond import CBSpec
from ..market.volatility import compute_hist_vol
from ..market.rates import fetch_ktb_rate
from .repricing import cb_issuance_score


def composite_score(
    cb: CBSpec,
    stock_price: float,
    price_series: pd.Series | None = None,
    sigma: float | None = None,
    r: float | None = None,
    valuation_date: date | None = None,
) -> dict[str, Any]:
    """Compute composite forensic score for a single CB.

    Combines available signal levels. Currently only Level 1 (issuance score)
    is implemented; Level 2 (per-repricing) awaits SEIBRO data.

    Args:
        cb: CBSpec with exercise_price, issue_date, maturity_date.
        stock_price: Stock price on the valuation date.
        price_series: Historical price series for vol computation.
            If None, sigma must be provided explicitly.
        sigma: Override annualized volatility. If None, computed from price_series.
        r: Override risk-free rate. If None, fetched from FRED (with fallback).
        valuation_date: Override valuation date. Defaults to cb.issue_date.

    Returns:
        Dict with issuance_score (Level 1 result) and metadata.

    Raises:
        ValueError: If neither price_series nor sigma is provided.
    """
    if sigma is None:
        if price_series is None:
            raise ValueError("Provide either price_series or sigma explicitly.")
        sigma = compute_hist_vol(price_series)

    if r is None:
        r = fetch_ktb_rate()

    level1 = cb_issuance_score(cb, stock_price, sigma, r, valuation_date)

    return {
        "corp_code": cb.corp_code,
        "issuance_score": level1,
        "has_repricing_score": False,  # Phase 2 not yet implemented
        "composite_flag": level1["dilution_flag"],
        "composite_severity": "high" if level1["moneyness"] > 1.10 else
                              "medium" if level1["moneyness"] > 1.00 else "low",
    }
