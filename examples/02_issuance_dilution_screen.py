"""Example 2: Screen cb_bw_events.parquet for issuance dilution signals.

Joins cb_bw_events → corp_ticker_map → price_volume to obtain the actual
closing price on (or immediately before) each CB's board meeting date.

Inputs (copy from kr-forensic-finance/01_Data/processed/ — see data/input/README.md):
    data/input/cb_bw_events.parquet
    data/input/corp_ticker_map.parquet
    data/input/price_volume.parquet

Usage:
    uv run python examples/02_issuance_dilution_screen.py

Output:
    issuance_dilution_scores.csv  — full ranked results
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from kr_derivatives.calendar.krx import previous_trading_day
from kr_derivatives.contracts.convertible_bond import CBSpec
from kr_derivatives.forensic.repricing import cb_issuance_score
from kr_derivatives.market.volatility import compute_hist_vol
from kr_derivatives.utils.constants import (
    DEFAULT_VOL_WINDOW,
    KTB_DEFAULT_RATE,
    MAX_BOARD_ISSUE_GAP_DAYS,
    MIN_HIST_DAYS_FOR_VOL_FOR_VOL,
    SIGMA_FALLBACK,
)

R = KTB_DEFAULT_RATE

DATA_DIR = Path(__file__).parent.parent / "data" / "input"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cb = pd.read_parquet(DATA_DIR / "cb_bw_events.parquet")
    tm = pd.read_parquet(DATA_DIR / "corp_ticker_map.parquet")
    pv = pd.read_parquet(DATA_DIR / "price_volume.parquet")
    return cb, tm, pv


def build_price_lookup(
    cb: pd.DataFrame,
    tm: pd.DataFrame,
    pv: pd.DataFrame,
) -> pd.DataFrame:
    """Join cb_bw_events to closing price on the last KRX trading day on or
    before each board_date.

    Board meetings may be announced on weekends or public holidays when the
    market is closed. previous_trading_day() snaps each board_date to the
    nearest prior KRX session before the exact-match price lookup, so no
    valid prices are missed due to calendar gaps.
    """
    cb = cb.copy()
    cb["board_date"] = pd.to_datetime(cb["board_date"]).dt.date

    # Drop rows with null board_date — cannot look up a price without a date
    null_dates = cb["board_date"].isna().sum()
    if null_dates:
        warnings.warn(f"{null_dates} rows have no board_date — skipped")
        cb = cb.dropna(subset=["board_date"])

    # Step 1: corp_code → ticker
    cb = cb.merge(tm[["corp_code", "ticker"]], on="corp_code", how="left")
    no_ticker = cb["ticker"].isna().sum()
    if no_ticker:
        warnings.warn(f"{no_ticker} rows have no ticker mapping — skipped")
        cb = cb.dropna(subset=["ticker"])

    # Step 2: snap each board_date to the most recent prior KRX trading session
    cb["price_date"] = cb["board_date"].map(previous_trading_day)

    # Step 3: exact merge on (ticker, price_date)
    pv = pv.copy()
    pv["date"] = pd.to_datetime(pv["date"]).dt.date
    price_index = pv.set_index(["ticker", "date"])["close"]

    cb["close"] = cb.apply(
        lambda r: price_index.get((r["ticker"], r["price_date"])),
        axis=1,
    )

    no_price = cb["close"].isna().sum()
    if no_price:
        warnings.warn(f"{no_price} rows have no price on snapped date — skipped")
        cb = cb.dropna(subset=["close"])

    # Change 2: Exclude rows where board_date → issue_date gap > MAX_BOARD_ISSUE_GAP_DAYS
    cb["issue_date"] = pd.to_datetime(cb["issue_date"]).dt.date
    cb["gap_days"] = cb.apply(
        lambda r: (r["issue_date"] - r["board_date"]).days
        if r["issue_date"] is not None and r["board_date"] is not None
        else 0,
        axis=1,
    )
    stale = (cb["gap_days"] > MAX_BOARD_ISSUE_GAP_DAYS).sum()
    if stale:
        warnings.warn(
            f"{stale} rows excluded: price reference >{MAX_BOARD_ISSUE_GAP_DAYS} days before issue_date"
        )
        cb = cb[cb["gap_days"] <= MAX_BOARD_ISSUE_GAP_DAYS]

    # Change 3: Flag rows where board_date was defaulted to issue_date
    cb["board_date_is_approximate"] = cb["board_date"] == cb["issue_date"]

    return cb


def build_vol_lookup(
    pv: pd.DataFrame,
    window: int = DEFAULT_VOL_WINDOW,
) -> dict[tuple[str, object], float]:
    """Pre-compute per-ticker trailing volatility for every (ticker, date) pair.

    Returns a dict mapping (ticker, date) → annualized vol. Rows with
    insufficient history get no entry (caller should use SIGMA_FALLBACK).
    """
    vol_map: dict[tuple[str, object], float] = {}
    pv = pv.copy()
    pv["date"] = pd.to_datetime(pv["date"]).dt.date
    pv = pv.sort_values(["ticker", "date"])

    for ticker, group in pv.groupby("ticker"):
        prices = group["close"].values
        dates = group["date"].values
        for i in range(len(dates)):
            if i + 1 < MIN_HIST_DAYS_FOR_VOL:
                continue
            start = max(0, i + 1 - window)
            segment = pd.Series(prices[start : i + 1])
            try:
                vol_map[(ticker, dates[i])] = compute_hist_vol(segment, window=window)
            except ValueError:
                continue

    return vol_map


def run_screen(
    joined: pd.DataFrame,
    vol_lookup: dict[tuple[str, object], float],
) -> pd.DataFrame:
    results = []
    skipped = 0
    fallback_count = 0

    for _, row in joined.iterrows():
        if pd.isna(row.get("exercise_price")):
            skipped += 1
            continue
        try:
            cb = CBSpec.from_parquet_row(row.to_dict())
        except (ValueError, KeyError):
            skipped += 1
            continue

        sigma = vol_lookup.get(
            (row["ticker"], row["price_date"]), SIGMA_FALLBACK
        )
        if sigma == SIGMA_FALLBACK:
            fallback_count += 1

        score = cb_issuance_score(
            cb,
            stock_price=float(row["close"]),
            sigma=sigma,
            r=R,
        )
        score["sigma"] = sigma
        score["board_date_is_approximate"] = row["board_date_is_approximate"]
        results.append(score)

    if skipped:
        print(f"  Skipped {skipped} rows (missing exercise_price or invalid spec)")
    if fallback_count:
        print(f"  {fallback_count} rows used fallback sigma={SIGMA_FALLBACK:.0%} (insufficient price history)")

    return pd.DataFrame(results)


def main() -> None:
    print("Loading inputs...")
    cb, tm, pv = load_inputs()
    print(f"  cb_bw_events:    {len(cb):,} rows")
    print(f"  corp_ticker_map: {len(tm):,} rows")
    print(f"  price_volume:    {len(pv):,} rows")

    print("\nJoining to closing prices...")
    joined = build_price_lookup(cb, tm, pv)
    print(f"  Rows with price: {len(joined):,}")

    print("\nComputing per-ticker trailing volatility...")
    vol_lookup = build_vol_lookup(pv)
    print(f"  Volatilities computed for {len(vol_lookup):,} (ticker, date) pairs")

    print(f"\nScoring (per-ticker sigma, fallback={SIGMA_FALLBACK:.0%}, r={R:.1%})...")
    out = run_screen(joined, vol_lookup)

    if out.empty:
        print("No results.")
        return

    out = out.sort_values("moneyness", ascending=False)
    flagged = out[out["dilution_flag"]]

    print(f"\nFlagged (ITM at issuance): {len(flagged):,} / {len(out):,}")
    print(f"Flag rate: {len(flagged)/len(out):.1%}\n")
    print(
        flagged[["corp_code", "S", "K", "moneyness", "bs_call_value"]]
        .head(20)
        .to_string(index=False)
    )

    out_path = Path("issuance_dilution_scores.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nFull results saved to {out_path}")


if __name__ == "__main__":
    main()
