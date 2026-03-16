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
from kr_derivatives.market.volatility import rolling_hist_vol
from kr_derivatives.utils.constants import (
    DEFAULT_VOL_WINDOW,
    KTB_DEFAULT_RATE,
    MAX_BOARD_ISSUE_GAP_DAYS,
    MIN_HIST_DAYS_FOR_VOL,
    SIGMA_FALLBACK,
)

R = KTB_DEFAULT_RATE

DATA_DIR = Path(__file__).parent.parent / "data" / "input"
CURATED_DIR = Path(__file__).parent.parent / "data" / "curated"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    cb = pd.read_parquet(DATA_DIR / "cb_bw_events.parquet")
    tm = pd.read_parquet(DATA_DIR / "corp_ticker_map.parquet")
    pv = pd.read_parquet(DATA_DIR / "price_volume.parquet")
    ca_path = DATA_DIR / "corp_actions.parquet"
    ca = pd.read_parquet(ca_path) if ca_path.exists() else None
    return cb, tm, pv, ca


def load_manual_k_adjustments() -> pd.DataFrame | None:
    """Load manual K adjustment factors from curated CSV.

    These capture denomination-changing events invisible to crDecsn.json
    (stock splits, par value changes, consolidations filed under other types).
    """
    path = CURATED_DIR / "manual_k_adjustments.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def load_excluded_corp_codes() -> set[str]:
    """Load corp codes to exclude from scoring (DATA_INSUFFICIENT etc.)."""
    path = CURATED_DIR / "excluded_corp_codes.csv"
    if not path.exists():
        return set()
    df = pd.read_csv(path)
    return {str(cc).zfill(8) for cc in df["corp_code"]}


def build_adjustment_factors(
    ca: pd.DataFrame | None,
    manual: pd.DataFrame | None = None,
) -> dict[str, list[tuple[object, float]]]:
    """Build a lookup of (effective_date, consolidation_ratio) per corp_code.

    Returns dict mapping corp_code → sorted list of (effective_date, factor)
    where factor = shares_before / shares_after (e.g. 10.0 for a 10:1 consolidation).

    Merges two sources:
    1. corp_actions.parquet (pipeline-extracted crDecsn events)
    2. manual_k_adjustments.csv (curated overrides for events invisible to crDecsn)
    """
    result: dict[str, list[tuple[object, float]]] = {}

    # Source 1: corp_actions.parquet
    if ca is not None and not ca.empty:
        ca = ca.copy()
        ca["effective_date"] = pd.to_datetime(ca["effective_date"], errors="coerce").dt.date
        ca = ca.dropna(subset=["effective_date", "shares_before", "shares_after"])
        ca = ca[ca["shares_after"] > 0]

        for _, row in ca.iterrows():
            cc = str(row["corp_code"]).zfill(8)
            factor = row["shares_before"] / row["shares_after"]
            if factor <= 1.0:
                continue
            result.setdefault(cc, []).append((row["effective_date"], factor))

    # Source 2: manual_k_adjustments.csv
    if manual is not None and not manual.empty:
        manual = manual.copy()
        manual["effective_date_approx"] = pd.to_datetime(
            manual["effective_date_approx"], errors="coerce"
        ).dt.date
        manual = manual.dropna(subset=["effective_date_approx", "factor"])

        for _, row in manual.iterrows():
            cc = str(row["corp_code"]).zfill(8)
            factor = float(row["factor"])
            if factor <= 1.0:
                continue
            result.setdefault(cc, []).append((row["effective_date_approx"], factor))

    # Sort by date ascending
    for cc in result:
        result[cc].sort(key=lambda x: x[0])

    return result


def cumulative_factor(
    actions: list[tuple[object, float]],
    after_date: object,
) -> float:
    """Compute cumulative consolidation factor for actions occurring after after_date.

    pykrx adjusted prices have ALL consolidations baked in retroactively.
    DART exercise prices are at original denomination. To align them,
    multiply K by the product of all consolidation factors that occurred
    AFTER the CB was issued.
    """
    factor = 1.0
    for eff_date, ratio in actions:
        if eff_date > after_date:
            factor *= ratio
    return factor


def build_price_lookup(
    cb: pd.DataFrame,
    tm: pd.DataFrame,
    pv: pd.DataFrame,
    ca: pd.DataFrame | None = None,
    manual_k: pd.DataFrame | None = None,
    excluded: set[str] | None = None,
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

    # Exclude corp codes with insufficient data for reliable scoring
    if excluded:
        cb["_cc"] = cb["corp_code"].astype(str).str.zfill(8)
        excluded_count = cb["_cc"].isin(excluded).sum()
        if excluded_count:
            print(f"  {excluded_count} rows excluded (corp codes in excluded_corp_codes.csv)")
            cb = cb[~cb["_cc"].isin(excluded)]
        cb = cb.drop(columns=["_cc"])

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

    # Change 4: Adjust exercise_price for post-issuance share consolidations
    adj_factors = build_adjustment_factors(ca, manual=manual_k)
    adjusted_count = 0
    if adj_factors:
        factors = []
        for _, row in cb.iterrows():
            cc = str(row["corp_code"]).zfill(8)
            actions = adj_factors.get(cc)
            if actions and row["issue_date"] is not None:
                f = cumulative_factor(actions, row["issue_date"])
                factors.append(f)
                if f > 1.0:
                    adjusted_count += 1
            else:
                factors.append(1.0)
        cb["k_adjustment_factor"] = factors
        cb["exercise_price_adjusted"] = cb["exercise_price"] * cb["k_adjustment_factor"]
    else:
        cb["k_adjustment_factor"] = 1.0
        cb["exercise_price_adjusted"] = cb["exercise_price"]

    if adjusted_count:
        print(f"  {adjusted_count} rows had exercise_price adjusted for post-issuance consolidations")

    return cb


def build_vol_lookup(
    pv: pd.DataFrame,
    window: int = DEFAULT_VOL_WINDOW,
) -> dict[tuple[str, object], float]:
    """Pre-compute per-ticker trailing volatility for every (ticker, date) pair.

    Uses vectorized rolling vol computation. Returns a dict mapping
    (ticker, date) → annualized vol. Dates with insufficient history
    (< MIN_HIST_DAYS_FOR_VOL) are excluded (caller should use SIGMA_FALLBACK).
    """
    vol_map: dict[tuple[str, object], float] = {}
    pv = pv.copy()
    pv["date"] = pd.to_datetime(pv["date"]).dt.date
    pv = pv.sort_values(["ticker", "date"])

    for ticker, group in pv.groupby("ticker"):
        if len(group) < MIN_HIST_DAYS_FOR_VOL:
            continue
        vols = rolling_hist_vol(group["close"], window=window)
        dates = group["date"].values
        for d, v in zip(dates, vols):
            if pd.notna(v):
                vol_map[(ticker, d)] = float(v)

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
            row_dict = row.to_dict()
            # Use consolidation-adjusted exercise price for CBSpec
            row_dict["exercise_price"] = row.get("exercise_price_adjusted", row["exercise_price"])
            cb = CBSpec.from_parquet_row(row_dict)
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
        score["k_adjustment_factor"] = row.get("k_adjustment_factor", 1.0)
        results.append(score)

    if skipped:
        print(f"  Skipped {skipped} rows (missing exercise_price or invalid spec)")
    if fallback_count:
        print(f"  {fallback_count} rows used fallback sigma={SIGMA_FALLBACK:.0%} (insufficient price history)")

    return pd.DataFrame(results)


def main() -> None:
    print("Loading inputs...")
    cb, tm, pv, ca = load_inputs()
    manual_k = load_manual_k_adjustments()
    excluded = load_excluded_corp_codes()
    print(f"  cb_bw_events:    {len(cb):,} rows")
    print(f"  corp_ticker_map: {len(tm):,} rows")
    print(f"  price_volume:    {len(pv):,} rows")
    if ca is not None:
        print(f"  corp_actions:    {len(ca):,} rows")
    else:
        print("  corp_actions:    not found (no K adjustment)")
    if manual_k is not None:
        print(f"  manual_k_adj:    {len(manual_k):,} entries")
    if excluded:
        print(f"  excluded corps:  {len(excluded):,}")

    print("\nJoining to closing prices...")
    joined = build_price_lookup(cb, tm, pv, ca, manual_k=manual_k, excluded=excluded)
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
