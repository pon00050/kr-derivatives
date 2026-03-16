# Fourth Run Lessons

**Date:** 2026-03-16
**Flag rate:** 34.0% → 33.1%

---

## What happened

Run 4 resolved the 32 remaining rows (10 companies) with moneyness >10x identified in Run 3. The approach was a three-step investigation:

1. **Diagnosis** (`/diagnose-moneyness`) — classified each company as SPLIT_ARTIFACT, GENUINE_ITM, or INCONCLUSIVE
2. **DART API research** — queried `stockTotqySttus.json`, `crDecsn.json`, and `irdsSttus.json` to obtain authoritative share count data
3. **Curated data layer** — created manual override CSVs consumed by the screen script

See `fourth_run_prep_extra.md` for the full research narrative.

---

## Key discovery: `stockTotqySttus.json`

The Run 3 extractor uses `crDecsn.json` (감자결정 / capital reduction decisions), which has a **structural blind spot** — it only captures events filed as capital reductions. Stock splits (주식분할), par value changes (액면변경), and some consolidations (주식병합) filed under different disclosure types are invisible.

`stockTotqySttus.json` provides total issued share counts per reporting period. By comparing year-over-year, it detects ANY share-count-changing event regardless of filing type. Combined with quarterly drill-down, it provides date precision to within one quarter.

This endpoint resolved 8 of 10 companies definitively, including 3 that were previously INCONCLUSIVE.

---

## Results

| Metric | Run 3 | Run 4 | Change |
|--------|-------|-------|--------|
| Rows scored | 2,939 | 2,934 | -5 (excluded) |
| Flag rate | 34.0% | 33.1% | -0.9pp |
| Flagged (ITM) | 998 | 970 | -28 |
| Moneyness >10x | 32 | 4 | -87.5% |
| Moneyness >5x | 98 | 57 | -41.8% |
| Moneyness >2x | 259 | 211 | -18.5% |
| K-adjusted rows | 864 | 944 | +80 |
| Rows excluded | 0 | 6 | +6 |
| Sigma fallback rate | 53.6% | 53.6% | unchanged |

### Moneyness bucket distribution

| Bucket | Count |
|--------|-------|
| <0.5 | 605 |
| 0.5-0.8 | 247 |
| 0.8-1.0 | 1,112 |
| 1.0-1.1 | 430 |
| 1.1-1.5 | 256 |
| 1.5-2.0 | 73 |
| 2.0-5.0 | 154 |
| 5.0-10.0 | 53 |
| >10 | 4 |

---

## Resolution of 10 outlier companies

| Corp code | Run 3 moneyness | Run 4 moneyness | Action | Source |
|-----------|-----------------|-----------------|--------|--------|
| 00232007 | 17.8x | 1.8x | Manual K adj (10.0) | STOCK_TOTQY |
| 00243979 | 11.1x | 1.1x | Manual K adj (10.0) | STOCK_TOTQY+LIST_JSON |
| 00299464 | 20.7x | 2.1x | Manual K adj (10.0) | STOCK_TOTQY |
| 00519252 | 11.0x | 1.1x | Manual K adj (10.0) | IRDS_STTUS+STOCK_TOTQY |
| 00175623 | 10.4x | 1.0x | Manual K adj (10.0) | STOCK_TOTQY |
| 01003040 | 10.0x | 1.0x | Manual K adj (10.0) | IRDS_STTUS+STOCK_TOTQY |
| 00475718 | 10.5x | 8.0x | Manual K adj (40.0) | CR_DECSN_DATE_RECOVERY |
| 00349811 | 52.3x | excluded | DATA_INSUFFICIENT | — |
| 01259056 | 13.8x | 13.8x | No change (GENUINE_ITM) | Confirmed via STOCK_TOTQY |
| 00971090 | 11.9x | 11.9x | No change (GENUINE_ITM) | Confirmed via STOCK_TOTQY |

### The 4 remaining >10x rows

All belong to 2 companies confirmed as GENUINE_ITM:

- **01259056** (2 rows, 13.8x): KOSDAQ micro-cap, issued CBs at minimum par value (K=500) when stock was 6,880. 167 consecutive days at exactly 6,880 — near-zero liquidity. Consolidations (31.6:1 combined) occurred BEFORE CB issuance; kadj=1.0 is correct.
- **00971090** (2 rows, 11.9x): Similar pattern — distressed company issued K=500 CBs after massive consolidation events (73.6:1 combined). Post-consolidation denomination on both S and K.

These are real forensic signals, not data artifacts.

### 00475718 note

Moneyness dropped from 10.5x to 8.0x (not fully resolved to ~1x). The 40:1 factor applies only to CBs issued before 2020-03-09. Of the 8 rows in output, most CBs were issued after the consolidation (kadj=1.0 or 2.0). The rows that did receive the full 80x adjustment (2.0 from pipeline × 40.0 from manual) are now correctly scored. The remaining 8.0x row likely reflects a genuinely deep-ITM issuance or an additional event not yet in the data.

---

## What worked

1. **`stockTotqySttus.json` as ground truth.** Resolved 8/10 companies definitively, including 3 reclassified from INCONCLUSIVE. No false positives — every detected share count change was corroborated by at least one other source.

2. **Curated data layer architecture.** `manual_k_adjustments.csv` and `excluded_corp_codes.csv` in kr-derivatives cleanly separate the manual research findings from the automated pipeline. The screen script merges both sources into a single adjustment lookup — no special-casing.

3. **Price-discontinuity correction.** The diagnosis session had inferred consolidation factors from price drops. StockTotqySttus proved 3 of these were wrong (genuine crashes, not consolidations). Without this correction, the manual factors would have been incorrect.

---

## Remaining issues

### 1. Sigma fallback rate: 53.6%

Over half the scored rows use the fallback sigma (40%) because their ticker has insufficient price history (<30 days before the board_date). This has been stable across all 4 runs and is structural — many CB issuers are KOSDAQ micro-caps with thin price coverage in pykrx.

**Impact:** Overstates Black-Scholes call values for low-vol stocks, understates for high-vol stocks. The flag (moneyness >1) is unaffected (sigma doesn't change S/K), but `bs_call_value` and `underpricing_pct` are approximate for these rows.

**Remediation options:**
- Accept as inherent limitation (current approach)
- Source additional price data from NAVER Finance or KRX direct feeds
- Report sigma source in output for downstream consumers to filter

### 2. T=0 row (1 row)

One row has T=0 (maturity date equals valuation date). Black-Scholes is degenerate at T=0. Low priority — single row.

### 3. `COL_CLOSE_UNADJ` constant

Added in Run 3 but never used. Should be removed from `constants.py`.

### 4. FinanceDataReader in kr-forensic-finance venv

Installed via `uv pip install` (not in pyproject.toml) during Run 3 investigation. Should be removed.

---

## Pipeline health

| Stage | Input | Output | Dropped | Reason |
|-------|-------|--------|---------|--------|
| Load cb_bw_events | 3,676 | 3,676 | — | — |
| Exclude corp codes | 3,676 | 3,670 | 6 | excluded_corp_codes.csv (00349811) |
| Drop null board_date | 3,670 | 3,569 | 101 | No board_date |
| Join ticker | 3,569 | 3,569 | 0 | — |
| Join price | 3,569 | 3,242 | 327 | No price on snapped date |
| Gap filter (>365d) | 3,242 | 3,187 | 55 | Stale price reference |
| Score (valid spec) | 3,187 | 2,934 | 253 | Missing exercise_price or invalid CBSpec |

### K adjustment breakdown

- 2,040 rows: kadj=1.0 (no adjustment needed)
- 894 rows: kadj>1.0 (adjusted for post-issuance consolidations)
  - Of these, 80 are new in Run 4 (from manual_k_adjustments.csv)
  - Remaining 814 from corp_actions.parquet (same as Run 3)

---

## Files changed

| File | Repo | Change |
|------|------|--------|
| `examples/02_issuance_dilution_screen.py` | kr-derivatives | Added curated CSV loading, merged into build_adjustment_factors |
| `data/curated/manual_k_adjustments.csv` | kr-derivatives | **New** — 7 entries |
| `data/curated/excluded_corp_codes.csv` | kr-derivatives | **New** — 1 entry |
| `research/research_stock_totqy.py` | kr-derivatives | **New** — standalone DART research script |
| `reports/fourth_run_prep_extra.md` | kr-derivatives | **New** — supplementary diagnosis and research narrative |
| `reports/fourth_run_lessons.md` | kr-derivatives | **New** — this file |

---

## Post-run assessment: is Run 5 warranted?

### Diminishing returns

The flag rate trajectory tells the story:

| Run | Change | Effort |
|-----|--------|--------|
| 1→2 | 0pp (discovered root cause) | Medium |
| 2→3 | -15.3pp (crDecsn K adjustment) | Medium |
| 3→4 | -0.9pp (manual research for 10 companies) | High (277 API calls, multi-hour investigation) |

Run 4 delivered its real value not in flag rate reduction but in **credibility** — the 4 remaining >10x rows are now defensible as genuine forensic signals, not data noise.

### The 5x-10x band: not worth chasing

A hypothetical Run 5 investigating the 5x-10x range would target 52 rows across 23 companies — 5.4% of flagged rows. Even if every single one turned out to be a false positive (unlikely), the flag rate would only drop from 33.1% to 31.3%.

Breakdown of the 53 rows in the 5x-10x band:

- **46 rows have kadj=1.0** — many are likely genuine deep-ITM cases (KOSDAQ micro-caps do this), not artifacts. Unlike >10x where denomination mismatch was economically implausible, 5-8x moneyness is plausible for distressed issuers.
- **7 rows have kadj>1.0** (partial correction applied) — could have additional hidden events, but the same stockTotqySttus research approach would require 23 companies × 11 years = 253+ API calls for a diminishing tail.

### The real quality limiters are structural, not K-adjustment

The biggest sources of imprecision in the flagged population:

1. **53.6% sigma fallback rate.** Over half of scored rows use the made-up 40% volatility because their ticker has insufficient price history (<30 days). This affects `bs_call_value` and `underpricing_pct` for every row that uses the fallback.

2. **56.1% approximate board dates among flagged rows.** 544 of 970 flagged rows use `issue_date` as proxy for `board_date`, meaning the price reference (S) is potentially months off from the actual decision date.

3. **44% of flags are barely ITM (1.0-1.1x).** These 430 borderline rows are the most sensitive to both the sigma and board_date limitations above. A stock that moved 5-10% between the true board_date and the approximate date could flip from OTM to ITM or vice versa.

None of these are addressable through more K-adjustment research.

### Conclusion

No Run 5 for K-adjustment refinement. The denomination mismatch problem is solved to the point of diminishing returns. If a future run is warranted, it should target one of the structural quality limiters (sigma source diversification or board_date precision), not the long tail of potential 5-8x denomination artifacts.
