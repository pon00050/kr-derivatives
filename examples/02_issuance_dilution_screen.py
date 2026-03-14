"""Example 2: Screen cb_bw_events.parquet for issuance dilution signals.

Connects kr-derivatives to kr-forensic-finance output.
Reads cb_bw_events.parquet from a path you provide.

Usage:
    uv run python examples/02_issuance_dilution_screen.py \
        --data-path C:/Users/pon00/Projects/kr-forensic-finance/01_Data/processed/cb_bw_events.parquet

Outputs a ranked CSV of issuance dilution scores.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(data_path: Path) -> None:
    try:
        import pandas as pd
    except ImportError:
        print("pandas is required: pip install pandas")
        sys.exit(1)

    from kr_derivatives.contracts.convertible_bond import CBSpec
    from kr_derivatives.contracts.base import ContractType
    from kr_derivatives.forensic.repricing import cb_issuance_score

    df = pd.read_parquet(data_path)
    print(f"Loaded {len(df)} CB/BW events from {data_path}")

    # Only process rows with non-null exercise_price
    valid = df.dropna(subset=["exercise_price"]).copy()
    print(f"Rows with exercise_price: {len(valid)}")

    results = []
    for _, row in valid.iterrows():
        try:
            cb = CBSpec.from_parquet_row(row.to_dict())
        except (ValueError, KeyError):
            continue

        # Without stock price data, we compute a hypothetical score
        # using a placeholder stock price = exercise_price (ATM baseline)
        # In production: join to price_volume.parquet on board_date
        score = cb_issuance_score(
            cb,
            stock_price=cb.exercise_price * 1.05,  # +5% ATM proxy
            sigma=0.40,
            r=0.035,
        )
        results.append(score)

    if not results:
        print("No valid CBs found.")
        return

    out = pd.DataFrame(results)
    out = out.sort_values("moneyness", ascending=False)
    flagged = out[out["dilution_flag"]]
    print(f"\nFlagged (ITM at issuance): {len(flagged)}/{len(out)}")
    print(flagged[["corp_code", "S", "K", "moneyness", "bs_call_value"]].head(20).to_string())

    out_path = Path("issuance_dilution_scores.csv")
    out.to_csv(out_path, index=False, encoding="utf-8")
    print(f"\nFull results saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", required=True, type=Path)
    args = parser.parse_args()
    main(args.data_path)
