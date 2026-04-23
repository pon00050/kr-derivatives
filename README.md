# kr-derivatives

**[Read the full write-up →](https://ronanwrites.vercel.app/manuals/cb-bw-dilution-screen-without-seibro)**

Korean derivatives pricing and forensic analytics — CB/BW embedded option valuation and repricing coercion detection.

## The problem

Korean convertible bonds (전환사채) and bonds with warrants (신주인수권부사채) are a known vector for minority shareholder dilution on KOSDAQ. A company issues a CB with a conversion price set *below* the current stock price — the bondholder is already in profit at issuance, before any repricing occurs. Detecting this requires treating the embedded conversion option for what it is: a European call on the underlying stock.

Until now, doing that screen over DART data required either writing the Black-Scholes math from scratch or access to SEIBRO repricing event data (which is behind a separate API key and commercially restricted). Neither was easy.

## What this enables

```python
from kr_derivatives import CBSpec, cb_issuance_score
from kr_derivatives.market import compute_hist_vol, fetch_ktb_rate

sigma = compute_hist_vol(price_series)   # 252-day realized vol from OHLCV
r     = fetch_ktb_rate()                 # KTB 10Y from FRED; falls back to 3.5%

score = cb_issuance_score(
    CBSpec.from_parquet_row(row),        # directly from cb_bw_events.parquet
    stock_price=close_at_board_date,
    sigma=sigma,
    r=r,
)
# => {"dilution_flag": True, "moneyness": 1.23, "bs_call_value": 3241, ...}
```

From a raw DART parquet row to an option-theoretic dilution score in one call — no SEIBRO access required. Applied across the full dataset:

```python
import pandas as pd

df    = pd.read_parquet("cb_bw_events.parquet").dropna(subset=["exercise_price"])
sigma = compute_hist_vol(price_series)
r     = fetch_ktb_rate()

scores = [
    cb_issuance_score(CBSpec.from_parquet_row(row), stock_price=close[row["corp_code"]], sigma=sigma, r=r)
    for _, row in df.iterrows()
]
flagged = [s for s in scores if s["dilution_flag"]]
```

That runs an option-theoretic dilution screen over 3,279 KOSDAQ CBs with non-null exercise prices from DART — using only publicly available data.

## Install

```bash
uv add git+https://github.com/pon00050/kr-derivatives
```

## Quick start

```python
from kr_derivatives import bs_call, CBSpec, cb_issuance_score
from datetime import date

# Price the embedded conversion option directly
call_value = bs_call(S=10_000, K=12_000, T=2.0, r=0.035, sigma=0.35)
print(f"Conversion option value: {call_value:,.0f} KRW")

# Forensic: score a specific CB issuance
cb = CBSpec(
    corp_code="01051092",
    exercise_price=8_000,           # conversion price set below stock price
    issue_date=date(2022, 1, 15),
    maturity_date=date(2025, 1, 15),
)
score = cb_issuance_score(cb, stock_price=10_000, sigma=0.35, r=0.035)
print(score["dilution_flag"])   # True  — CB issued in-the-money
print(score["moneyness"])       # 1.25  — stock was 25% above conversion price
print(score["bs_call_value"])   # KRW   — full option-theoretic value transferred to bondholder
```

## Features

- **Black-Scholes pricing**: `bs_call`, `bs_put`, full analytical Greeks suite
- **Implied volatility**: Newton-Raphson with Brent fallback — pure scipy, no py_vollib dependency
- **CB/BW contracts**: `CBSpec`, `WarrantSpec` with `from_parquet_row()` matching the DART schema
- **Forensic Level 1**: `cb_issuance_score` — at-issuance ITM detection, SEIBRO-independent
- **Forensic Level 2**: `repricing_coercion_score` — per-repricing coercion scoring (Phase 2, requires SEIBRO)
- **Historical vol**: `compute_hist_vol` from a price series (252-day log-return std)
- **Korea risk-free rate**: `fetch_ktb_rate` via FRED KTB 10Y; falls back to 3.5% if unreachable
- **KRX calendar**: `second_thursday_of_month` (KOSPI200 expiry rule), trading day utilities

## What the score returns

`cb_issuance_score()` returns a dict for each CB:

| Field | Meaning |
|-------|---------|
| `dilution_flag` | `True` if stock price exceeded conversion price at issuance |
| `moneyness` | S/K — ratio of stock price to conversion price |
| `bs_call_value` | Black-Scholes value of the embedded conversion option at issuance (KRW) |
| `discount_to_theory` | How much of the option's BS value was above intrinsic — the portion transferred to the bondholder beyond immediate exercise value |
| `flag_reason` | Human-readable explanation |

## Phase 2 (planned)

- `repricing_coercion_score()` — compares each repricing event's new conversion price to the BS option value at that date; flags when the repriced price is set below 70% of theoretical value (requires SEIBRO API access)
- SVI volatility surface fitting for KOSPI200 options
- KRX Open API integration (requires key registration at openapi.krx.co.kr)
