"""Example 1: Price a Korean convertible bond embedded option.

Standalone — no external pipeline data required.
All parameters passed explicitly.

Usage:
    uv run python examples/01_cb_fair_value.py
"""

from __future__ import annotations

from datetime import date

from kr_derivatives import bs_call, CBSpec, cb_issuance_score
from kr_derivatives.contracts.base import ContractType
from kr_derivatives.utils.dates import days_to_expiry


def main() -> float:
    """Price a sample CB and print forensic score. Returns call value."""
    # --- CB parameters (would come from cb_bw_events.parquet in practice) ---
    corp_code = "01051092"          # PCL (피씨엘) — Tier 1 lead
    issue_date = date(2022, 3, 15)
    maturity_date = date(2025, 3, 15)
    exercise_price = 10_000.0       # KRW — conversion price at issuance
    stock_price_at_issue = 8_750.0  # KRW — close price on board_date

    # --- Market parameters ---
    sigma = 0.40    # 40% annualized vol (KOSDAQ small-cap typical)
    r = 0.035       # 3.5% risk-free rate (KTB 10Y approx)

    # --- Compute time to expiry ---
    T = days_to_expiry(issue_date, maturity_date)

    # --- Price the embedded conversion option ---
    call_value = bs_call(S=stock_price_at_issue, K=exercise_price, T=T, r=r, sigma=sigma)
    moneyness = stock_price_at_issue / exercise_price

    print(f"\n{'='*55}")
    print(f"  Korean CB Embedded Option — Fair Value")
    print(f"{'='*55}")
    print(f"  Corp code:        {corp_code}")
    print(f"  Issue date:       {issue_date}")
    print(f"  Maturity:         {maturity_date}")
    print(f"  Time to expiry:   {T:.2f} years")
    print(f"  Conversion price: {exercise_price:>12,.0f} KRW")
    print(f"  Stock price:      {stock_price_at_issue:>12,.0f} KRW")
    print(f"  Moneyness (S/K):  {moneyness:.3f}")
    print(f"  Sigma:            {sigma:.0%}")
    print(f"  Risk-free rate:   {r:.1%}")
    print(f"{'='*55}")
    print(f"  BS call value:    {call_value:>12,.0f} KRW")
    print(f"{'='*55}")

    # --- Forensic issuance score ---
    cb = CBSpec(
        contract_type=ContractType.CB,
        corp_code=corp_code,
        exercise_price=exercise_price,
        issue_date=issue_date,
        maturity_date=maturity_date,
    )
    score = cb_issuance_score(cb, stock_price=stock_price_at_issue, sigma=sigma, r=r)

    print(f"\n  Dilution flag:    {'[!] FLAGGED' if score['dilution_flag'] else '[OK] Clean'}")
    print(f"  Reason:           {score['flag_reason']}")
    print()

    return call_value


if __name__ == "__main__":
    main()
