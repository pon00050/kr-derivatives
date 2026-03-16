"""Tests for Black-Scholes Greeks (delta, gamma, vega, theta, rho)."""

from __future__ import annotations

import math

import pytest

from kr_derivatives.pricing.greeks import delta, gamma, vega, theta, rho, greeks


# Standard test parameters: ATM call, 1 year, 35% vol, 3.5% rate
S, K, T, r, sigma = 10_000.0, 10_000.0, 1.0, 0.035, 0.35


class TestDelta:
    def test_atm_call_delta_near_half(self):
        """ATM call delta should be slightly above 0.5 (due to positive drift)."""
        d = delta(S, K, T, r, sigma, "c")
        assert 0.5 < d < 0.7

    def test_atm_put_delta_near_minus_half(self):
        d = delta(S, K, T, r, sigma, "p")
        assert -0.3 > d > -0.7

    def test_deep_itm_call_delta_near_one(self):
        d = delta(20_000.0, K, T, r, sigma, "c")
        assert d > 0.95

    def test_deep_otm_call_delta_near_zero(self):
        d = delta(1_000.0, K, T, r, sigma, "c")
        assert d < 0.05

    def test_put_call_delta_relationship(self):
        """Put delta = call delta - 1."""
        dc = delta(S, K, T, r, sigma, "c")
        dp = delta(S, K, T, r, sigma, "p")
        assert abs((dc - 1) - dp) < 1e-10

    def test_degenerate_T_zero(self):
        assert math.isnan(delta(S, K, 0, r, sigma))

    def test_degenerate_sigma_zero(self):
        assert math.isnan(delta(S, K, T, r, 0))


class TestGamma:
    def test_atm_gamma_positive(self):
        g = gamma(S, K, T, r, sigma)
        assert g > 0

    def test_atm_gamma_highest(self):
        """Gamma is highest ATM."""
        g_atm = gamma(S, K, T, r, sigma)
        g_itm = gamma(20_000.0, K, T, r, sigma)
        g_otm = gamma(1_000.0, K, T, r, sigma)
        assert g_atm > g_itm
        assert g_atm > g_otm

    def test_degenerate_returns_nan(self):
        assert math.isnan(gamma(S, K, 0, r, sigma))


class TestVega:
    def test_atm_vega_positive(self):
        v = vega(S, K, T, r, sigma)
        assert v > 0

    def test_longer_maturity_higher_vega(self):
        v1 = vega(S, K, 0.5, r, sigma)
        v2 = vega(S, K, 2.0, r, sigma)
        assert v2 > v1

    def test_degenerate_returns_nan(self):
        assert math.isnan(vega(S, K, 0, r, sigma))


class TestTheta:
    def test_call_theta_negative(self):
        """Long call theta should be negative (time decay)."""
        t = theta(S, K, T, r, sigma, "c")
        assert t < 0

    def test_put_theta_negative(self):
        t = theta(S, K, T, r, sigma, "p")
        assert t < 0

    def test_degenerate_returns_nan(self):
        assert math.isnan(theta(S, K, 0, r, sigma))


class TestRho:
    def test_call_rho_positive(self):
        """Call rho is positive: higher rates increase call value."""
        r_val = rho(S, K, T, r, sigma, "c")
        assert r_val > 0

    def test_put_rho_negative(self):
        r_val = rho(S, K, T, r, sigma, "p")
        assert r_val < 0

    def test_degenerate_returns_nan(self):
        assert math.isnan(rho(S, K, 0, r, sigma))


class TestGreeksDict:
    def test_returns_all_keys(self):
        g = greeks(S, K, T, r, sigma)
        assert set(g.keys()) == {"delta", "gamma", "vega", "theta", "rho"}

    def test_call_vs_put_flag(self):
        gc = greeks(S, K, T, r, sigma, "c")
        gp = greeks(S, K, T, r, sigma, "p")
        # Gamma and vega should be identical
        assert gc["gamma"] == gp["gamma"]
        assert gc["vega"] == gp["vega"]
        # Delta should differ
        assert gc["delta"] != gp["delta"]

    def test_all_values_are_float(self):
        g = greeks(S, K, T, r, sigma)
        for v in g.values():
            assert isinstance(v, float)
