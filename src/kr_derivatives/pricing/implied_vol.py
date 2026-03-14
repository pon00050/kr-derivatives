"""Implied volatility solver: Newton-Raphson with bisection fallback.

No dependency on py_vollib — pure scipy implementation.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from .black_scholes import bs_call, bs_put
from .greeks import vega
from ..utils.constants import MIN_VOL, MAX_VOL, IV_TOLERANCE, IV_MAX_ITERATIONS


def _model_price(S: float, K: float, T: float, r: float, sigma: float, flag: str) -> float:
    return bs_call(S, K, T, r, sigma) if flag == "c" else bs_put(S, K, T, r, sigma)


def newton_iv(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    flag: str = "c",
    initial_guess: float = 0.30,
    tol: float = IV_TOLERANCE,
    max_iter: int = IV_MAX_ITERATIONS,
) -> float:
    """Compute implied volatility via Newton-Raphson iteration.

    Falls back to Brent's method (bisection) if Newton-Raphson diverges.

    Args:
        market_price: Observed market price of the option.
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate.
        flag: 'c' for call, 'p' for put.
        initial_guess: Starting vol estimate (default 30%).
        tol: Convergence tolerance on price difference.
        max_iter: Maximum Newton-Raphson iterations.

    Returns:
        Implied volatility as a decimal (e.g. 0.35 = 35%).

    Raises:
        ValueError: If IV cannot be solved (e.g. price below intrinsic).
    """
    if T <= 0:
        raise ValueError("Cannot compute IV for expired option (T <= 0)")

    # Check for arbitrage-free bounds
    if flag == "c":
        intrinsic = max(S - K * np.exp(-r * T), 0.0)
    else:
        intrinsic = max(K * np.exp(-r * T) - S, 0.0)

    if market_price < intrinsic - tol:
        raise ValueError(
            f"market_price={market_price:.4f} is below intrinsic value={intrinsic:.4f}"
        )

    # Newton-Raphson
    sigma = initial_guess
    for _ in range(max_iter):
        price = _model_price(S, K, T, r, sigma, flag)
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        v = vega(S, K, T, r, sigma) * 100  # vega returns per 1%, multiply back
        if abs(v) < 1e-12:
            break  # near-zero vega — fall through to bisection
        sigma = sigma - diff / v
        if sigma < MIN_VOL:
            sigma = MIN_VOL
        elif sigma > MAX_VOL:
            sigma = MAX_VOL

    # Bisection fallback via scipy Brent's method
    try:
        def objective(s: float) -> float:
            return _model_price(S, K, T, r, s, flag) - market_price

        iv = brentq(objective, MIN_VOL, MAX_VOL, xtol=tol, maxiter=500)
        return float(iv)
    except ValueError as exc:
        raise ValueError(
            f"IV solver failed for market_price={market_price:.4f}, S={S}, K={K}, T={T:.4f}"
        ) from exc


# Convenience alias
implied_vol = newton_iv
