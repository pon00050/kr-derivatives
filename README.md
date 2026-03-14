# kr-derivatives

Korean derivatives pricing and forensic analytics — CB/BW embedded option valuation and repricing coercion detection.

## Install

```bash
pip install kr-derivatives
```

## Quick start

```python
from kr_derivatives import bs_call, CBSpec, cb_issuance_score
from datetime import date

# Price a conversion option
call_value = bs_call(S=10000, K=12000, T=2.0, r=0.035, sigma=0.35)
print(f"Conversion option value: {call_value:,.0f} KRW")

# Forensic: detect ITM issuance
cb = CBSpec(
    corp_code="01051092",
    exercise_price=8000,
    issue_date=date(2022, 1, 15),
    maturity_date=date(2025, 1, 15),
)
score = cb_issuance_score(cb, stock_price=10000, sigma=0.35, r=0.035)
print(f"Dilution flag: {score['dilution_flag']}")  # True — CB issued ITM
print(f"Moneyness: {score['moneyness']:.2f}")
```

## Features

- **Black-Scholes pricing**: `bs_call`, `bs_put`, full Greeks suite
- **Implied volatility**: Newton-Raphson with bisection fallback (pure scipy, no py_vollib)
- **CB/BW contracts**: `CBSpec`, `WarrantSpec` — matches `cb_bw_events.parquet` schema
- **Forensic Level 1**: `cb_issuance_score` — at-issuance ITM detection (SEIBRO-independent)
- **Forensic Level 2**: `repricing_coercion_score` — per-repricing coercion (Phase 2, requires SEIBRO)
- **KRX calendar**: `second_thursday_of_month`, trading day utilities via `exchange_calendars`
- **Historical vol**: `compute_hist_vol` from price series
- **Korea risk-free rate**: `fetch_ktb_rate` via FRED (KTB 10Y, fallback 3.5%)

## Phase 2 (planned)

- KRX Open API integration (requires key registration at openapi.krx.co.kr)
- SVI volatility surface fitting
- `repricing_coercion_score` implementation (after SEIBRO API key activates)
