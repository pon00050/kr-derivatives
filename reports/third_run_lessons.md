# Third Run Lessons

**Date:** 2026-03-15
**Flag rate:** 49.3% → 34.0%

---

## What happened

Run 3 was designed to fix the denomination mismatch between pykrx adjusted stock prices (S) and DART exercise prices (K) for stocks that underwent share consolidations. The original plan (fetch unadjusted prices via `pykrx adjusted=False`) failed because the KRX direct API returns malformed JSON. We pivoted to **Path B: adjust K using DART corporate action data** instead.

## The pivot

| Approach | Status | Why |
|----------|--------|-----|
| **Path A (original plan):** Upgrade pykrx, fetch `adjusted=False` prices | **Failed** | pykrx 1.2.4 routes `adjusted=False` through KRX data API (`data.krx.co.kr`), which returns malformed JSON for all tickers. Server-side issue — no pykrx version can fix it. |
| **Path A alt:** FinanceDataReader unadjusted prices | **Failed** | FDR also returns adjusted (split-corrected) prices only |
| **Path B (implemented):** Adjust K by consolidation factor from DART 감자결정 | **Succeeded** | DART `crDecsn.json` endpoint returns structured data: shares_before, shares_after, effective_date |

## Implementation

### New pipeline stage: `extract_corp_actions.py` (kr-forensic-finance)

- Queries DART `crDecsn.json` for all 919 corp_codes in `cb_bw_events.parquet`
- Parses shares_before/shares_after to compute consolidation factor
- Output: `corp_actions.parquet` (271 events across 164 companies)
- Runtime: ~9 minutes at 0.3s sleep per call

### Screen script changes: `02_issuance_dilution_screen.py` (kr-derivatives)

- `build_adjustment_factors(ca)` — builds lookup of (effective_date, factor) per corp_code
- `cumulative_factor(actions, after_date)` — computes product of all consolidation factors occurring AFTER a given date (the CB issuance date)
- K_adjusted = K × cumulative_factor → used for CBSpec and moneyness computation
- New output column: `k_adjustment_factor` (1.0 if no adjustment)

### Logic

pykrx `adjusted=True` retroactively multiplies all historical prices by the cumulative consolidation factor. DART exercise prices remain at the original denomination. To align:

```
K_adjusted = K × (shares_before₁/shares_after₁) × (shares_before₂/shares_after₂) × ...
```

for all consolidation events occurring between the CB issuance date and today.

Example — MEDICOX (054180):
- CB issued Dec 2016, K = 2,165 KRW
- Consolidation 1: June 2022, 10:1 (factor = 10)
- Consolidation 2: July 2025, 15:1 (factor = 15)
- K_adjusted = 2,165 × 150 = 324,750 KRW
- S_adjusted = 161,745 KRW
- Corrected moneyness = 161,745 / 324,750 = 0.50x (OTM — was 74.7x)

---

## Results

| Metric | Run 2 | Run 3 | Change |
|--------|-------|-------|--------|
| Rows scored | 2,939 | 2,939 | — |
| Flag rate | 49.3% | 34.0% | -15.3pp |
| Flagged (ITM) | 1,449 | 998 | -451 |
| Moneyness >10x | 241 | 32 | -87% |
| Moneyness >5x | 518 | 98 | -81% |
| Moneyness >2x | — | 259 | — |
| K-adjusted rows | 0 | 864 | +864 |
| Companies with adjustments | 0 | 143 | +143 |
| Sigma fallback rate | 53.6% | 53.6% | unchanged |

## Remaining extreme cases

32 rows across 10 companies still show moneyness >10x. Breakdown:

| Corp code | Rows | Max moneyness | k_adj_factor | Likely cause |
|-----------|------|---------------|--------------|-------------|
| 00349811 | 5 | 52.3x | 1.0 | Possible pre-2015 consolidation or genuine deep-ITM |
| 00299464 | 5 | 20.7x | 1.0 | Same |
| 00232007 | 6 | 17.8x | 3.0 | Partial adjustment — may have additional consolidations |
| 01259056 | 2 | 13.8x | 1.0 | Genuine or uncaptured action |
| 00971090 | 2 | 11.9x | 1.0 | Same |
| 00243979 | 1 | 11.1x | 1.0 | Same |
| 00519252 | 7 | 11.0x | 1.0 | Same |
| 00475718 | 2 | 10.5x | 2.0 | Partial adjustment |
| 00175623 | 1 | 10.4x | 1.0 | Same |
| 01003040 | 1 | 10.0x | 1.0 | Same |

Most have `k_adj_factor=1.0` — no DART 감자결정 filing found. Possible explanations:
1. Consolidation occurred before 2015 (DART crDecsn endpoint starts from 2015)
2. Corporate action not filed as 감자결정 (different disclosure type)
3. Genuinely extreme ITM issuances (KOSDAQ small-caps do issue deeply ITM CBs)

## Key learnings

1. **Never trust API documentation without a live call.** The pykrx upgrade was validated from PyPI docs and function signatures, but the underlying KRX API was broken server-side. Future plans should include a live verification step for any external API dependency.

2. **Path B (adjust K) is architecturally superior to Path A (fetch unadjusted S).** It uses a reliable, authoritative data source (DART corporate filings) instead of depending on a third-party API that can break without notice. The adjustment factors are exact (from regulatory filings), not approximations.

3. **The DART `crDecsn.json` endpoint is underdocumented.** The correct endpoint name was not guessable from the API naming convention — it took web-fetching the DART developer guide to find it. The Run 2 investigation tried `crcRdcpDecsn.json` which was wrong.

4. **164 out of 919 CB/BW issuers (17.8%) have capital reduction filings.** This is a substantial fraction and confirms that share consolidation is a systematic data quality issue for Korean small-cap forensic analysis, not an edge case.

## Dependency changes

- pykrx upgraded from 1.0.51 to 1.2.4 in kr-forensic-finance (numpy downgraded to 1.26.4 as side effect)
- FinanceDataReader 0.9.110 installed via `uv pip install` (not in pyproject.toml — was a quick test, should be cleaned up)

## Files changed

| File | Repo | Change |
|------|------|--------|
| `pyproject.toml` | kr-forensic-finance | `pykrx>=1.2.0` |
| `uv.lock` | kr-forensic-finance | Regenerated |
| `02_Pipeline/extract_corp_actions.py` | kr-forensic-finance | **New** — DART 감자결정 extractor |
| `01_Data/processed/corp_actions.parquet` | kr-forensic-finance | **New** — 271 events |
| `examples/02_issuance_dilution_screen.py` | kr-derivatives | K adjustment via corp_actions |
| `src/kr_derivatives/utils/constants.py` | kr-derivatives | COL_CLOSE_UNADJ constant (unused) |
| `data/input/corp_actions.parquet` | kr-derivatives | **New** — copied from kr-forensic-finance |
| `reports/third_run_prep.md` | kr-derivatives | Updated with execution log |
| `reports/third_run_lessons.md` | kr-derivatives | **New** — this file |
