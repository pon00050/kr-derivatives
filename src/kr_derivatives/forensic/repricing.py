"""Forensic signals for Korean CB/BW repricing coercion detection.

Level 1 — At-issuance dilution (SEIBRO-independent, uses DART exercise_price):
    cb_issuance_score() — fires when CB is issued deep in-the-money.
    A company that issues a CB with conversion price below current stock price
    is giving bondholders an immediate profit at shareholders' expense.

Level 2 — Per-repricing coercion (requires SEIBRO data, Phase 2):
    repricing_coercion_score() — compares each repricing price to BS fair value.
    Currently raises NotImplementedError. DEFERRED until end of April 2026 —
    공공데이터포털 is revising the SEIBRO dataset/API (KSD not cooperating with
    data.go.kr). See XB-002 in the hub.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..contracts.convertible_bond import CBSpec
from ..pricing.black_scholes import bs_call
from ..utils.constants import ITM_AT_ISSUANCE_FLAG, FLOOR_RULE


def cb_issuance_score(
    cb: CBSpec,
    stock_price: float,
    sigma: float,
    r: float,
    valuation_date: date | None = None,
) -> dict[str, Any]:
    """Compute Level 1 forensic score: embedded option value at issuance.

    Measures whether a CB was issued with the conversion option already
    in-the-money — i.e., bondholder guaranteed a profit from day one.

    Signal fires when moneyness (S/K) > ITM_AT_ISSUANCE_FLAG (1.0):
    the stock price exceeds the conversion price at issuance.

    Args:
        cb: CBSpec with exercise_price, issue_date, maturity_date.
        stock_price: Stock price on the issuance date (or board_date).
            From price_volume.parquet close at board_date.
        sigma: Annualized volatility at issuance. Use compute_hist_vol().
        r: Risk-free rate. Use fetch_ktb_rate().
        valuation_date: Override for the valuation date. Defaults to cb.issue_date.

    Returns:
        Dict with:
            corp_code: str
            valuation_date: date
            S: float — stock price used
            K: float — conversion price (exercise_price)
            T: float — years to maturity
            sigma: float
            r: float
            bs_call_value: float — Black-Scholes call value of conversion option
            moneyness: float — S/K ratio
            discount_to_theory: float — (bs_call_value - intrinsic) / bs_call_value
                Negative means the conversion was worth less than BS theory predicts.
                For ITM issuances, this quantifies "how much" was given away.
            dilution_flag: bool — True if moneyness > ITM_AT_ISSUANCE_FLAG
            flag_reason: str — human-readable explanation

    Raises:
        ValueError: If stock_price <= 0 or exercise_price <= 0.
    """
    if stock_price <= 0:
        raise ValueError(f"stock_price must be positive, got {stock_price}")
    if cb.exercise_price <= 0:
        raise ValueError(f"exercise_price must be positive, got {cb.exercise_price}")

    vdate = valuation_date or cb.issue_date
    T = cb.time_to_expiry(vdate)
    S = stock_price
    K = cb.exercise_price

    bs_value = bs_call(S, K, T, r, sigma)
    moneyness = S / K
    intrinsic = max(S - K, 0.0)

    # discount_to_theory: how much extra value above intrinsic BS assigns
    # Positive bs_value with high moneyness means "deep ITM — bondholder gift"
    if bs_value > 0:
        discount_to_theory = (bs_value - intrinsic) / bs_value
    else:
        discount_to_theory = 0.0

    dilution_flag = moneyness > ITM_AT_ISSUANCE_FLAG

    if dilution_flag:
        flag_reason = (
            f"CB issued ITM: stock {S:,.0f} KRW > conversion price {K:,.0f} KRW "
            f"(moneyness={moneyness:.3f}). Bondholder received in-the-money option "
            f"worth {bs_value:,.0f} KRW at issuance."
        )
    else:
        flag_reason = (
            f"CB issued OTM/ATM: moneyness={moneyness:.3f}. "
            f"Conversion option BS value={bs_value:,.0f} KRW."
        )

    return {
        "corp_code": cb.corp_code,
        "valuation_date": vdate,
        "S": S,
        "K": K,
        "T": T,
        "sigma": sigma,
        "r": r,
        "bs_call_value": bs_value,
        "moneyness": moneyness,
        "discount_to_theory": discount_to_theory,
        "dilution_flag": dilution_flag,
        "flag_reason": flag_reason,
    }


def repricing_coercion_score(
    cb: CBSpec,
    repricing_events: list[dict],
    price_series: Any,
    sigma: float,
    r: float,
) -> list[dict]:
    """Level 2 forensic score: per-repricing coercion detection.

    Compares each repricing event's new conversion price to the Black-Scholes
    fair value of the conversion option at that repricing date.

    Flag fires when: new_conversion_price < bs_call_value × FLOOR_RULE (0.70)
    i.e., the repriced conversion price was set far below option theoretical value.

    NOT IMPLEMENTED YET — requires SEIBRO data (KI-012: SEIBRO API key pending).
    repricing_history column in cb_bw_events.parquet is all empty [] until SEIBRO activates.

    Args:
        cb: CBSpec for the bond.
        repricing_events: List of repricing event dicts from SEIBRO.
            Each dict: {repricing_date, new_exercise_price, reason}.
        price_series: pd.Series of stock prices (date-indexed) for the CB period.
        sigma: Annualized volatility for the period.
        r: Risk-free rate.

    Returns:
        List of score dicts (one per repricing event).

    Raises:
        NotImplementedError: Until SEIBRO data is available.
    """
    raise NotImplementedError(
        "repricing_coercion_score requires SEIBRO repricing event data. "
        "The repricing_history column in cb_bw_events.parquet is currently all empty [] "
        "until SEIBRO API key activates (see KI-012). "
        "Phase 2 implementation pending."
    )
