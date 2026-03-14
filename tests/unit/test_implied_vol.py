"""Tests for implied volatility solver.

Key contract: round-trip price → IV → price must match within tolerance.
"""

import numpy as np
import pytest

from kr_derivatives.pricing.black_scholes import bs_call, bs_put
from kr_derivatives.pricing.implied_vol import implied_vol


ROUND_TRIP_TOL = 1e-4  # price tolerance after round-trip


class TestImpliedVolRoundTrip:
    @pytest.mark.parametrize("S,K,T,r,sigma,flag", [
        (10_000, 10_000, 1.0, 0.035, 0.30, "c"),   # ATM call
        (10_000, 10_000, 1.0, 0.035, 0.30, "p"),   # ATM put
        (8_500, 10_000, 2.0, 0.035, 0.35, "c"),    # OTM call
        (12_000, 10_000, 2.0, 0.035, 0.35, "c"),   # ITM call
        (10_000, 10_000, 0.25, 0.035, 0.60, "c"),  # short-dated high-vol
        (10_000, 10_000, 3.0, 0.035, 0.15, "p"),   # long-dated low-vol put
    ])
    def test_round_trip(self, S, K, T, r, sigma, flag):
        """price → IV → price must reproduce original price within tolerance."""
        if flag == "c":
            price = bs_call(S, K, T, r, sigma)
        else:
            price = bs_put(S, K, T, r, sigma)

        iv = implied_vol(price, S, K, T, r, flag)
        
        if flag == "c":
            recovered = bs_call(S, K, T, r, iv)
        else:
            recovered = bs_put(S, K, T, r, iv)

        assert abs(recovered - price) < ROUND_TRIP_TOL, (
            f"Round-trip failed: sigma={sigma}, iv={iv:.6f}, "
            f"price={price:.4f}, recovered={recovered:.4f}"
        )

    def test_iv_value_close_to_input_sigma(self):
        """The recovered IV should be close to the true sigma used to price."""
        true_sigma = 0.35
        price = bs_call(S=10_000, K=10_000, T=1.0, r=0.035, sigma=true_sigma)
        iv = implied_vol(price, S=10_000, K=10_000, T=1.0, r=0.035, flag="c")
        assert abs(iv - true_sigma) < 1e-5

    def test_expired_option_raises(self):
        with pytest.raises(ValueError, match="T <= 0"):
            implied_vol(100.0, S=10_000, K=10_000, T=0, r=0.035, flag="c")

    def test_below_intrinsic_raises(self):
        """Price below intrinsic value is arbitrage — must raise ValueError."""
        # ITM call: intrinsic = 2000. Pass price=500 (below intrinsic).
        with pytest.raises(ValueError):
            implied_vol(500.0, S=12_000, K=10_000, T=1.0, r=0.035, flag="c")
