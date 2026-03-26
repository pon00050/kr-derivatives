"""Analytical Black-Scholes Greeks."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from .black_scholes import d1, d2


def delta(S: float, K: float, T: float, r: float, sigma: float, flag: str = "c") -> float:
    """Option delta (dV/dS).

    Args:
        flag: 'c' for call, 'p' for put.

    Returns:
        Delta. Call delta in (0, 1), put delta in (-1, 0).
    """
    if T <= 0 or sigma <= 0:
        return float("nan")
    _d1 = d1(S, K, T, r, sigma)
    if flag == "c":
        return float(norm.cdf(_d1))
    return float(norm.cdf(_d1) - 1)


def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Option gamma (d²V/dS²). Same for calls and puts."""
    if T <= 0 or sigma <= 0:
        return float("nan")
    _d1 = d1(S, K, T, r, sigma)
    return float(norm.pdf(_d1) / (S * sigma * np.sqrt(T)))


def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Option vega (dV/dσ). Same for calls and puts.

    Returns vega per 1% move in vol (i.e. raw dV/dσ divided by 100).

    Convention note: the raw Black-Scholes vega is dV/dσ (per unit of sigma).
    Practitioners quote vega as "KRW change per 1 vol-point (= 1% = 0.01 in
    sigma units)", so we divide by 100 here.  The IV solver (implied_vol.py)
    multiplies by 100 to recover dV/dσ for Newton-Raphson; the net round-trip
    is correct: vega()*100 == raw dV/dσ.
    """
    if T <= 0 or sigma <= 0:
        return float("nan")
    _d1 = d1(S, K, T, r, sigma)
    return float(S * norm.pdf(_d1) * np.sqrt(T) / 100)


def theta(S: float, K: float, T: float, r: float, sigma: float, flag: str = "c") -> float:
    """Option theta (dV/dt), expressed per calendar day.

    Args:
        flag: 'c' for call, 'p' for put.

    Returns:
        Theta per day (negative for long options = time decay).
    """
    if T <= 0 or sigma <= 0:
        return float("nan")
    _d1 = d1(S, K, T, r, sigma)
    _d2 = d2(S, K, T, r, sigma)
    term1 = -(S * norm.pdf(_d1) * sigma) / (2 * np.sqrt(T))
    if flag == "c":
        term2 = -r * K * np.exp(-r * T) * norm.cdf(_d2)
    else:
        term2 = r * K * np.exp(-r * T) * norm.cdf(-_d2)
    return float((term1 + term2) / 365)


def rho(S: float, K: float, T: float, r: float, sigma: float, flag: str = "c") -> float:
    """Option rho (dV/dr), expressed per 1% move in rates.

    Args:
        flag: 'c' for call, 'p' for put.
    """
    if T <= 0 or sigma <= 0:
        return float("nan")
    _d2 = d2(S, K, T, r, sigma)
    if flag == "c":
        return float(K * T * np.exp(-r * T) * norm.cdf(_d2) / 100)
    return float(-K * T * np.exp(-r * T) * norm.cdf(-_d2) / 100)


def greeks(
    S: float, K: float, T: float, r: float, sigma: float, flag: str = "c"
) -> dict[str, float]:
    """Return all Greeks as a dict.

    Args:
        flag: 'c' for call, 'p' for put.
    """
    return {
        "delta": delta(S, K, T, r, sigma, flag),
        "gamma": gamma(S, K, T, r, sigma),
        "vega": vega(S, K, T, r, sigma),
        "theta": theta(S, K, T, r, sigma, flag),
        "rho": rho(S, K, T, r, sigma, flag),
    }
