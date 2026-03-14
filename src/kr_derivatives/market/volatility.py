"""Historical volatility computation from price series."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils.constants import DEFAULT_VOL_WINDOW, ANNUALIZATION_FACTOR


def compute_hist_vol(
    prices: pd.Series,
    window: int = DEFAULT_VOL_WINDOW,
    annualize: bool = True,
) -> float:
    """Compute realized (historical) volatility from a price series.

    Uses log-return standard deviation, optionally annualized.

    Args:
        prices: Pandas Series of closing prices (chronological order).
            Index can be dates or integers. Must have at least 2 entries.
        window: Number of most-recent observations to use. If len(prices) < window,
            uses all available data.
        annualize: If True, multiply by sqrt(ANNUALIZATION_FACTOR=252).

    Returns:
        Annualized volatility as a decimal (e.g. 0.35 = 35%).

    Raises:
        ValueError: If prices has fewer than 2 non-null entries.
    """
    clean = prices.dropna()
    if len(clean) < 2:
        raise ValueError(f"Need at least 2 non-null prices, got {len(clean)}")

    # Use the most recent `window` prices
    series = clean.iloc[-window:] if len(clean) > window else clean

    log_returns = np.log(series.values[1:] / series.values[:-1])
    vol = float(np.std(log_returns, ddof=1))

    if annualize:
        vol *= np.sqrt(ANNUALIZATION_FACTOR)

    return vol


def rolling_hist_vol(
    prices: pd.Series,
    window: int = DEFAULT_VOL_WINDOW,
) -> pd.Series:
    """Return rolling annualized volatility series.

    Args:
        prices: Chronological closing price series.
        window: Rolling window in trading days.

    Returns:
        Series of annualized volatilities (same index as prices, NaN where
        insufficient data).
    """
    log_returns = np.log(prices / prices.shift(1))
    return log_returns.rolling(window).std(ddof=1) * np.sqrt(ANNUALIZATION_FACTOR)
