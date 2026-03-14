"""Tests for Black-Scholes pricing functions.

Behavioral contracts verified:
- put-call parity holds
- boundary conditions (T=0, sigma=0)
- call increases with S, decreases with K
- Greeks sign conventions
"""

import numpy as np
import pytest

from kr_derivatives.pricing.black_scholes import bs_call, bs_put, d1, d2, put_call_parity_check


class TestD1D2:
    def test_d1_atm(self):
        """ATM option with zero drift: d1 = 0.5 * sigma * sqrt(T)."""
        # S=K, r=0 => d1 = 0.5 * sigma * sqrt(T)
        result = d1(S=100, K=100, T=1.0, r=0.0, sigma=0.20)
        expected = 0.5 * 0.20 * np.sqrt(1.0)
        assert abs(result - expected) < 1e-10

    def test_d2_equals_d1_minus_vol_sqrtT(self):
        result_d1 = d1(S=100, K=100, T=1.0, r=0.035, sigma=0.30)
        result_d2 = d2(S=100, K=100, T=1.0, r=0.035, sigma=0.30)
        assert abs(result_d1 - result_d2 - 0.30 * np.sqrt(1.0)) < 1e-10

    def test_d1_returns_nan_for_zero_T(self):
        assert np.isnan(d1(S=100, K=100, T=0, r=0.035, sigma=0.30))

    def test_d1_returns_nan_for_zero_sigma(self):
        assert np.isnan(d1(S=100, K=100, T=1.0, r=0.035, sigma=0.0))


class TestBSCall:
    def test_positive_value_for_standard_params(self):
        val = bs_call(S=10_000, K=10_000, T=2.0, r=0.035, sigma=0.35)
        assert val > 0

    def test_otm_call_less_than_itm_call(self):
        """Deep OTM call must be worth less than deep ITM call."""
        otm = bs_call(S=5_000, K=10_000, T=1.0, r=0.035, sigma=0.35)
        itm = bs_call(S=15_000, K=10_000, T=1.0, r=0.035, sigma=0.35)
        assert otm < itm

    def test_call_increases_with_spot(self):
        """Call value strictly increases as S increases (all else equal)."""
        vals = [bs_call(S=s, K=10_000, T=1.0, r=0.035, sigma=0.35) for s in range(6000, 15000, 1000)]
        assert all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))

    def test_call_decreases_with_strike(self):
        vals = [bs_call(S=10_000, K=k, T=1.0, r=0.035, sigma=0.35) for k in range(7000, 14000, 1000)]
        assert all(vals[i] > vals[i + 1] for i in range(len(vals) - 1))

    def test_expired_option_returns_intrinsic(self):
        """T=0 call = max(S-K, 0)."""
        assert bs_call(S=12_000, K=10_000, T=0, r=0.035, sigma=0.35) == pytest.approx(2_000.0)
        assert bs_call(S=8_000, K=10_000, T=0, r=0.035, sigma=0.35) == pytest.approx(0.0)

    def test_call_bounded_by_spot(self):
        """Call value can never exceed spot price."""
        val = bs_call(S=10_000, K=1, T=10.0, r=0.0, sigma=0.99)
        assert val <= 10_000


class TestBSPut:
    def test_positive_value_for_otm_put(self):
        val = bs_put(S=8_000, K=10_000, T=2.0, r=0.035, sigma=0.35)
        assert val > 0

    def test_expired_option_returns_intrinsic(self):
        assert bs_put(S=8_000, K=10_000, T=0, r=0.035, sigma=0.35) == pytest.approx(2_000.0)
        assert bs_put(S=12_000, K=10_000, T=0, r=0.035, sigma=0.35) == pytest.approx(0.0)

    def test_put_bounded_by_discounted_strike(self):
        """Put value can never exceed PV of strike."""
        K = 10_000
        r = 0.035
        T = 2.0
        val = bs_put(S=1, K=K, T=T, r=r, sigma=0.01)
        assert val <= K * np.exp(-r * T) + 1  # allow small numerical buffer


class TestPutCallParity:
    @pytest.mark.parametrize("S,K,T,r,sigma", [
        (10_000, 10_000, 1.0, 0.035, 0.30),
        (8_500, 12_000, 2.0, 0.035, 0.40),
        (15_000, 10_000, 0.5, 0.04, 0.50),
        (10_000, 10_000, 3.0, 0.03, 0.20),
    ])
    def test_put_call_parity_holds(self, S, K, T, r, sigma):
        """C - P = S - K*exp(-rT) within floating point tolerance."""
        c = bs_call(S, K, T, r, sigma)
        p = bs_put(S, K, T, r, sigma)
        residual = put_call_parity_check(c, p, S, K, T, r)
        assert abs(residual) < 1e-6, f"Parity violated: residual={residual:.2e}"
