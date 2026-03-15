# Second Run Lessons

**Run date:** 2026-03-15
**Commit:** d8eb32c (prep changes) + bugfix for MIN_HIST_DAYS_FOR_VOL rename

---

## Run Summary

| Metric | Value |
|--------|-------|
| Input cb_bw_events | 3,676 rows |
| Null board_date dropped | 101 |
| No ticker mapping | (merged away) |
| No price on snapped date | 328 |
| Gap filter (>365 days) removed | 55 |
| Rows scored | 2,939 |
| Skipped (no exercise_price / invalid) | 253 |
| **Flag rate** | **49.3%** |

---

## Results

| Metric | Run 1 | Run 2 | Target | Met? |
|--------|-------|-------|--------|------|
| Rows scored | 2,988 | 2,939 | ~2,920 | ~Yes |
| Flag rate | 49.3% | 49.3% | <35% | **No** |
| Moneyness >10 count | 254 | 241 | <20 | **No** |
| Moneyness >5 count | 527 | 518 | <50 | **No** |
| Clean ITM range (1.0-2.0) | ~657 | 645 | Stable | Yes |
| Uniform sigma | 0.40 | Per-ticker | Per-ticker | **Yes** |

### Moneyness Distribution

```
<0.5        245
0.5-0.8     193
0.8-1.0    1053
1.0-1.1     386
1.1-1.5     181
1.5-2.0      78
2.0-5.0     285
5.0-10.0    277
>10         241
```

### Sigma Distribution

- Mean: 0.632, Median: 0.400 (fallback)
- 1,576 / 2,939 rows (53.6%) used fallback sigma=0.40
- Per-ticker vol range: 0.000 - 2.962 (annualized)
- Fallback dominance caused by many tickers having <252 trading days in price_volume.parquet

### Approximate Board Dates

- 1,947 / 2,939 (66.3%) have `board_date_is_approximate == True`
- These are rows where DART defaulted board_date to issue_date

---

## What Worked

1. **Gap filter (Change 2):** 55 rows with >365-day gap correctly excluded. No impact on flag rate (they were a small fraction), but removes indefensible price references from the output.

2. **board_date_is_approximate flag (Change 3):** Working correctly. 66% of rows are flagged as approximate, consistent with the Run 1 observation that 2,090/3,575 (58%) had board_date == issue_date.

3. **Per-ticker volatility (Change 4):** Implemented with `rolling_hist_vol()` (vectorized, 1.2s runtime vs 38s naive). Vol values show meaningful variation across issuers. However, 54% of rows fell back to sigma=0.40 because their tickers had fewer than 252 trading days of history in price_volume.parquet.

4. **Optimized vol computation:** `build_vol_lookup()` runs in 1.2s for 347k price rows across 916 tickers, producing 159k (ticker, date) vol entries.

---

## Remaining Issues

### Issue 1 — Adjusted S vs unadjusted K denomination mismatch (ROOT CAUSE of unchanged flag rate)

**Priority: BLOCKING for Run 3**

The split-adjusted prices from XB-001 fix created a new problem: **adjusted stock prices and DART exercise prices are in different denominations for stocks that underwent reverse splits/consolidations.**

#### Evidence (verified via DART API + pykrx + yfinance)

| corp_code | ticker | K (DART) | S (adjusted) | S/K | Verification |
|-----------|--------|----------|-------------|------|-------------|
| 00957568 | 214310 | 1,945 | 480,800 | 247x | DART cv_prc=1,945 confirmed. Ticker delisted. |
| 00356839 | 054180 | 2,165 | 161,745 | 75x | +130% adjusted jump on 2018-08-06 suggests corporate action. Current price ~3,690. |
| 00363510 | 060230 | 1,365 | 71,662 | 52x | Same pattern. |

#### Root cause (confirmed)

pykrx `adjusted=True` retroactively scales all historical prices to match the current share denomination. For stocks that had reverse splits (e.g., 50:1 consolidation), pre-consolidation prices are multiplied up by 50x. DART exercise prices (cv_prc) are contractual snapshots from the filing date — they are NOT retroactively adjusted. Comparing adjusted-S to unadjusted-K creates false extreme moneyness.

**Example:** If 054180 had a ~75:1 reverse split after 2016, the unadjusted price in Dec 2016 would have been ~2,157 (161,745/75), making moneyness = 2,157/2,165 = 1.00 (ATM). This is economically plausible; 75x ITM is not.

#### Constraint: unadjusted prices are unavailable from current sources

- **pykrx `adjusted=False`**: Returns empty DataFrames for all tickers tested (broken in installed version)
- **yfinance `Close`**: Also split-adjusted (Samsung pre-50:1 split shows 51,020, not ~2.55M)
- **yfinance `Adj Close`**: Split + dividend adjusted (no help)
- Neither source provides true unadjusted (raw trading) prices

#### Fix options for Run 3 (ranked)

| Option | Description | Effort | Quality |
|--------|-------------|--------|---------|
| A | **KRX KIND corporate action API** — fetch split/consolidation history per ticker, compute adjustment factor, normalize K upward to post-adjustment denomination | High | Best — uses authoritative data |
| B | **Heuristic adjustment factor** — for each ticker, compare earliest and latest adjusted prices to detect suspiciously large ranges; compute implied split ratio from the adjusted time series discontinuities (>100% single-day jumps) | Medium | Good — catches most cases |
| C | **Moneyness cap** — flag rows with moneyness >10 as "likely adjustment artifact" rather than forensic signal; exclude from flag rate | Low | Partial — treats symptom |
| D | **Upgrade pykrx** — check if a newer version fixes `adjusted=False`; if so, fetch both series | Low | Best if it works |

**Recommendation:** Try Option D first (quick win). If pykrx still broken, fall back to Option B (detect from time series) combined with Option C (cap extreme outliers). Option A is the definitive fix but requires KRX KIND API registration.

**Measurable target for Run 3:** After correcting the denomination mismatch, moneyness >10 count should drop from 241 to <20. Flag rate should drop to <35%.

### Issue 2 — High fallback sigma rate

**Priority: MEDIUM**

53.6% of scored rows used the fallback sigma=0.40 because their tickers lacked 252 trading days of price history. Two contributing factors:

1. **price_volume.parquet coverage:** Only covers dates where the pipeline fetched data. Small-cap tickers may have gaps or limited history.
2. **Window size:** 252 days is a full year. Reducing `DEFAULT_VOL_WINDOW` to 126 (6 months) or 63 (3 months) would increase coverage but produce noisier vol estimates.

**Recommendation:** Accept 0.40 fallback for now. The flag decision depends on moneyness (S/K > 1.0), not on sigma. Sigma affects `bs_call_value` precision, which is secondary. Revisit if vol-based severity tiers are added later.

### Issue 3 — Approximate board dates dominate

**Priority: LOW (informational)**

66% of scored rows have board_date defaulted to issue_date. This means the stock price reference is taken on the issue date rather than the true board meeting date (when the CB terms were actually decided). For forensic purposes, the board_date price is more meaningful because that is when insiders knew the conversion terms.

**No fix needed now** — the `board_date_is_approximate` flag lets downstream users filter or weight these rows differently. Improving board_date extraction in kr-forensic-finance's DART parser would require sub-document parsing (Phase 3, May 2026).

---

## Pipeline Health

| Stage | In | Out | Dropped | Reason |
|-------|-----|------|---------|--------|
| Load | 3,676 | 3,676 | 0 | — |
| Drop null board_date | 3,676 | 3,575 | 101 | No date to look up price |
| Ticker mapping | 3,575 | ~3,520 | ~55 | No corp_code in ticker map |
| Price lookup | ~3,520 | 3,192 | 328 | No price on snapped date |
| Gap filter | 3,192 | 3,137 | 55 | board-to-issue gap >365 days |
| Scoring | 3,137 | 2,939 | 253 | No exercise_price or invalid spec |
| **Final** | — | **2,939** | — | — |

No unexpected drops. All filters logged warnings as designed.

---

## Changes for Run 3

### Change 1 — Resolve denomination mismatch (BLOCKING)

**Problem:** Adjusted stock prices and unadjusted DART exercise prices are incomparable for stocks with corporate actions. Unadjusted prices are unavailable (pykrx `adjusted=False` broken, yfinance Close also split-adjusted).

**Approach (try in order):**

1. **Check if pykrx upgrade fixes `adjusted=False`** — current installed version returns empty. Check PyPI for updates. If a newer version works, add `close_unadjusted` column to `price_volume.parquet`.

2. **If still broken: detect adjustment factors from the time series.** For each ticker, identify single-day jumps >100% in the adjusted series (reverse split signature). Compute the cumulative adjustment factor between each CB's board_date and the most recent corporate action date. Apply the inverse factor to the adjusted price to recover the approximate unadjusted price.

3. **As a floor: cap moneyness at 10x and flag as artifact.** Rows with moneyness >10 are marked `moneyness_is_suspect = True` and excluded from the aggregate flag rate. This prevents false signals while the data pipeline is improved.

### Change 2 — Reduce vol fallback rate

53.6% of rows used fallback sigma. Consider:
- Reducing `DEFAULT_VOL_WINDOW` from 252 to 126 days
- OR extending price_volume.parquet date coverage for small-cap tickers

Lower priority than Change 1.
