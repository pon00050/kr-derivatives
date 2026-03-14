"""Example 3: Compute implied volatility from a known option price.

Shows round-trip: price → IV → verify recovered price matches.

Usage:
    uv run python examples/03_iv_from_option_price.py
"""

from __future__ import annotations

from kr_derivatives import bs_call, bs_put, implied_vol


def main() -> float:
    """Compute IV from market price. Returns the implied vol."""
    # Hypothetical KOSPI200 call option
    S = 380.0      # index points
    K = 380.0      # ATM
    T = 0.25       # 3 months
    r = 0.035
    flag = "c"

    # Suppose we observe this market price (from KRX)
    true_sigma = 0.18  # 18% — typical KOSPI200 realized vol
    market_price = bs_call(S, K, T, r, true_sigma)

    # Recover implied vol from the market price
    iv = implied_vol(market_price, S=S, K=K, T=T, r=r, flag=flag)

    # Verify round-trip
    recovered_price = bs_call(S, K, T, r, iv)
    error = abs(recovered_price - market_price)

    print(f"\n{'='*50}")
    print(f"  Implied Volatility from Option Price")
    print(f"{'='*50}")
    print(f"  Underlying (KOSPI200):  {S:.1f}")
    print(f"  Strike:                 {K:.1f}")
    print(f"  Time to expiry:         {T:.2f} years")
    print(f"  Risk-free rate:         {r:.1%}")
    print(f"  Market price (call):    {market_price:.4f}")
    print(f"{'='*50}")
    print(f"  Implied volatility:     {iv:.4f} ({iv:.1%})")
    print(f"  Price round-trip error: {error:.2e}")
    print(f"{'='*50}\n")

    assert error < 1e-4, f"Round-trip error too large: {error}"
    return iv


if __name__ == "__main__":
    main()
