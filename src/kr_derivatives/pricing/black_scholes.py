"""Black-Scholes pricing functions — pure numpy, no external dependencies."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm


def d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Compute d1 of the Black-Scholes formula.

    Args:
        S: Spot price (current stock price).
        K: Strike price (conversion / exercise price).
        T: Time to expiry in years.
        r: Risk-free rate (annualized, continuously compounded).
        sigma: Annualized volatility (e.g. 0.35 = 35%).

    Returns:
        d1 scalar.
    """
    if T <= 0 or sigma <= 0:
        return float("nan")
    return (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))


def d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Compute d2 = d1 - sigma * sqrt(T)."""
    if T <= 0 or sigma <= 0:
        return float("nan")
    return d1(S, K, T, r, sigma) - sigma * np.sqrt(T)


def bs_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes European call price.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate (annualized).
        sigma: Annualized volatility.

    Returns:
        Call option fair value. Returns intrinsic value if T <= 0.
    """
    if T <= 0:
        return max(S - K, 0.0)
    if sigma <= 0:
        return max(S - K * np.exp(-r * T), 0.0)
    _d1 = d1(S, K, T, r, sigma)
    _d2 = d2(S, K, T, r, sigma)
    return float(S * norm.cdf(_d1) - K * np.exp(-r * T) * norm.cdf(_d2))


def bs_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes European put price.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate (annualized).
        sigma: Annualized volatility.

    Returns:
        Put option fair value. Returns intrinsic value if T <= 0.
    """
    if T <= 0:
        return max(K - S, 0.0)
    if sigma <= 0:
        return max(K * np.exp(-r * T) - S, 0.0)
    _d1 = d1(S, K, T, r, sigma)
    _d2 = d2(S, K, T, r, sigma)
    return float(K * np.exp(-r * T) * norm.cdf(-_d2) - S * norm.cdf(-_d1))


def put_call_parity_check(
    call: float, put: float, S: float, K: float, T: float, r: float
) -> float:
    """Return put-call parity residual (should be ~0 for European options).

    C - P - S + K*exp(-rT) ≈ 0
    """
    return call - put - S + K * np.exp(-r * T)
