"""Tests for historical volatility computation.

Contracts:
- compute_hist_vol returns annualized vol from log-returns
- Known constant price series => vol = 0
- Geometric random walk with known sigma => recovered vol ~ sigma (within sampling error)
- Raises ValueError for < 2 prices
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from kr_derivatives.market.volatility import compute_hist_vol, rolling_hist_vol


class TestComputeHistVol:
    def test_constant_price_series_has_zero_vol(self):
        """No movement = zero volatility."""
        prices = pd.Series([10_000.0] * 100)
        vol = compute_hist_vol(prices)
        assert vol == pytest.approx(0.0, abs=1e-10)

    def test_known_sigma_recovered_within_tolerance(self):
        """GBM series with sigma=0.30 daily => annualized vol ~ 0.30 * sqrt(252).

        Use large N for law-of-large-numbers accuracy.
        """
        rng = np.random.default_rng(0)
        daily_sigma = 0.02  # daily
        n = 2000
        log_returns = rng.normal(0, daily_sigma, n)
        prices = 10_000.0 * np.exp(np.cumsum(log_returns))
        vol = compute_hist_vol(pd.Series(prices), window=n)
        expected = daily_sigma * np.sqrt(252)
        # Allow 15% relative error (sampling variation)
        assert abs(vol - expected) / expected < 0.15, f"vol={vol:.4f}, expected~{expected:.4f}"

    def test_annualized_larger_than_daily(self):
        rng = np.random.default_rng(1)
        prices = pd.Series(10_000.0 * np.exp(np.cumsum(rng.normal(0, 0.02, 252))))
        annualized = compute_hist_vol(prices, annualize=True)
        daily = compute_hist_vol(prices, annualize=False)
        assert annualized > daily

    def test_fewer_than_two_prices_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            compute_hist_vol(pd.Series([10_000.0]))

    def test_empty_series_raises(self):
        with pytest.raises(ValueError):
            compute_hist_vol(pd.Series([], dtype=float))

    def test_window_limits_lookback(self):
        """Window=10 uses only last 10 prices, not all 100."""
        rng = np.random.default_rng(42)
        # First 90 prices: high vol; last 10: constant
        high_vol_prices = 10_000 * np.exp(np.cumsum(rng.normal(0, 0.05, 90)))
        low_vol_prices = np.ones(10) * high_vol_prices[-1]
        prices = pd.Series(np.concatenate([high_vol_prices, low_vol_prices]))

        vol_full = compute_hist_vol(prices, window=100)
        vol_recent = compute_hist_vol(prices, window=10)
        assert vol_recent < vol_full

    def test_nan_prices_ignored(self):
        """NaN values in price series are dropped before computation."""
        prices = pd.Series([10_000.0, np.nan, 10_100.0, 10_050.0, np.nan, 10_150.0])
        # Should not raise — NaN rows dropped
        vol = compute_hist_vol(prices)
        assert vol >= 0


class TestRollingHistVol:
    def test_returns_series_same_length(self):
        prices = pd.Series(np.linspace(10_000, 12_000, 300))
        result = rolling_hist_vol(prices, window=60)
        assert len(result) == len(prices)

    def test_first_window_values_are_nan(self):
        prices = pd.Series(np.linspace(10_000, 12_000, 100))
        result = rolling_hist_vol(prices, window=30)
        # First 30 values should be NaN (insufficient data for rolling std)
        assert result.iloc[:30].isna().all()

    def test_values_after_window_are_positive(self):
        rng = np.random.default_rng(7)
        prices = pd.Series(10_000 * np.exp(np.cumsum(rng.normal(0, 0.02, 200))))
        result = rolling_hist_vol(prices, window=30)
        valid = result.dropna()
        assert (valid > 0).all()
