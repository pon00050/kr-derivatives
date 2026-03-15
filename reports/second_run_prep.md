# Second Run Prep

**Status:** Pending
**Depends on:** Resolving items 1 and 2 from `first_run_lessons.md` before launching

---

## Changes Required Before Running

### Change 1 — Split-adjusted prices (BLOCKING)

**Issue identified:** `price_volume.parquet` contains unadjusted closing prices.
Stock splits cause pre-split prices to appear orders of magnitude higher than
the CB exercise price set post-split, producing moneyness values that are
meaningless. Confirmed for ticker 224060: two single-day price drops of -78%
and -89%, consistent with stock splits. This contaminates 527+ rows (the >5×
moneyness tail).

**Where to fix:** kr-forensic-finance — `02_Pipeline/extract_price_volume.py`.

**Options (ranked):**

| Option | Description | Effort | Quality |
|--------|-------------|--------|---------|
| A | Fetch split-adjusted prices from pykrx — use `stock.get_market_ohlcv_by_date` with `adjusted=True` | Low — one flag change | Best |
| B | Fetch a corporate actions (splits) table separately and apply adjustments to existing `price_volume.parquet` | Medium | Good |
| C | Cross-check with Yahoo Finance (`yfinance`) which returns adjusted prices by default | Low | Acceptable as validation |
| D | Filter out affected rows in kr-derivatives using a heuristic (e.g. exclude if any single-day price change >50% exists in the price series for that ticker) | Low — no upstream change needed | Partial — treats symptom, not cause |

**Recommendation:** Option A. Re-run `extract_price_volume.py` with `adjusted=True` in pykrx.
Verify by re-checking ticker 224060 — the Nov 2016 price should be comparable
to the CB exercise price of 740 after split adjustment.

**Measurable target:** Rows with moneyness >10 should drop from 254 to <20.

---

### Change 2 — Exclude large board-to-issue gaps (HIGH PRIORITY)

**Issue identified:** 72 rows have `board_date` more than 2 years before
`issue_date`. Using a stock price from 2+ years before the actual issuance
is not a defensible reference price for the forensic question.

**Where to fix:** `examples/02_issuance_dilution_screen.py` — add a filter
in `build_price_lookup()` after the join, before scoring.

**Proposed filter:**

```python
# Exclude rows where the reference price is >365 days stale relative to issue_date
cb['issue_date'] = pd.to_datetime(cb['issue_date']).dt.date
cb['gap_days'] = (cb['issue_date'] - cb['price_date']).apply(lambda x: x.days)
stale = (cb['gap_days'] > 365).sum()
if stale:
    warnings.warn(f"{stale} rows excluded: price reference >365 days before issue_date")
    cb = cb[cb['gap_days'] <= 365]
```

**Measurable target:** 72 rows removed from input; extreme moneyness tail
further reduced.

---

### Change 3 — Flag `board_date == issue_date` rows in output (LOW PRIORITY)

**Issue identified:** 2,090 rows (58%) have `board_date` defaulted to
`issue_date` in the DART extractor — no independently captured board meeting
date was available. These rows are not wrong but are less precise.

**Where to fix:** Add a boolean column `board_date_is_approximate` to the
score output dict in `cb_issuance_score()` or in the screen script.

**Proposed output field:**

```python
score['board_date_is_approximate'] = (row['board_date'] == row['issue_date'])
```

**Purpose:** Allows downstream users to filter or separately weight results
where the price reference date is approximate. Does not change the flag
decision — only adds transparency.

---

### Change 4 — Per-ticker trailing volatility (MEDIUM PRIORITY)

**Issue identified:** Uniform `sigma = 0.40` makes `bs_call_value` a rough
estimate. The data to compute a better sigma already exists in
`price_volume.parquet`.

**Where to fix:** `examples/02_issuance_dilution_screen.py`.

**Approach:** For each CB, compute the 252-day trailing realized vol for the
issuer's stock as of `price_date`.

```python
from kr_derivatives.market.volatility import compute_hist_vol

def get_sigma(ticker: str, as_of: date, pv: pd.DataFrame, window: int = 252) -> float:
    prices = pv[(pv['ticker'] == ticker) & (pv['date'] <= as_of)].tail(window)
    if len(prices) < 30:  # insufficient history
        return 0.40       # fallback to market default
    return compute_hist_vol(pd.Series(prices['close'].values))
```

**Trade-off:** This adds one `compute_hist_vol` call per CB row. With 3,000
rows and a vectorized implementation it should stay well within the 60s budget.
Profile before committing to ensure it does not materially increase runtime.

**Measurable target:** `sigma` column in output should show variation across
issuers rather than a constant 0.40.

---

### Change 5 — Register BOK_API_KEY (LOW PRIORITY)

**Issue identified:** `fetch_ktb_rate()` falls back to 3.5% because
`BOK_API_KEY` is not set. The rate used for Black-Scholes pricing is
therefore fixed regardless of the actual KTB 10Y rate at the time of
each issuance.

**Where to fix:** Register a free key at `https://ecos.bok.or.kr` and
set `BOK_API_KEY` in the environment before running.

**Note:** For the forensic flag (`dilution_flag`), the risk-free rate has
minimal effect — the flag is driven by moneyness (S/K), not by r. The impact
is on `bs_call_value` precision. Low priority relative to the price
split-adjustment issue.

---

## Expected Outcomes for Run 2

| Metric | Run 1 | Run 2 target |
|--------|-------|--------------|
| Rows scored | 2,988 | ~2,920 (after gap filter) |
| Flag rate | 49.3% | <35% |
| Moneyness >10 count | 254 | <20 |
| Moneyness >5 count | 527 | <50 |
| Clean ITM range (1.0–2.0) | ~657 (~22%) | Stable or slightly lower |
| Uniform sigma | 0.40 | Per-ticker trailing vol |

---

## Pre-Run Checklist

- [x] `price_volume.parquet` regenerated with split-adjusted prices (Option A) — XB-001 fixed 2026-03-15
- [ ] Ticker 224060 Nov 2016 price verified — should be split-adjusted to ~740–2,000 range
- [x] Gap filter (>365 days) added and tested on a sample — `MAX_BOARD_ISSUE_GAP_DAYS` in constants.py
- [x] `board_date_is_approximate` column added to output — flags board_date == issue_date
- [x] `sigma` per-ticker vol computation implemented — `build_vol_lookup()` with `compute_hist_vol()`
- [ ] New `price_volume.parquet` copied to `data/input/`
- [x] Full suite still green: `uv run python -m pytest tests/ -q` — 79 passed
- [ ] Runtime profiled for per-ticker vol computation

---

## Operational Notes

### 2026-03-15 — Wave 1 code changes implemented

Changes 2–4 implemented in `examples/02_issuance_dilution_screen.py`:

1. **Change 2 (gap filter):** Rows where `board_date → issue_date` gap exceeds 365 days are excluded with a warning. Constant `MAX_BOARD_ISSUE_GAP_DAYS = 365` added to `constants.py`.

2. **Change 3 (approximate flag):** New `board_date_is_approximate` boolean column in output. `True` when `board_date == issue_date` (DART defaulted the board date).

3. **Change 4 (per-ticker vol):** `build_vol_lookup()` pre-computes trailing 252-day realized vol for every (ticker, date) pair in `price_volume.parquet`. Falls back to `SIGMA_FALLBACK = 0.40` when fewer than 30 days of history exist. All constants moved to `constants.py`.

**Remaining before run:** Copy new split-adjusted `price_volume.parquet` to `data/input/`, verify ticker 224060, profile runtime.
