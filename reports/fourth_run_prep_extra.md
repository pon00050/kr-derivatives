# Fourth Run Prep — Supplementary Diagnosis

**Status:** Complete. Run 4 executed 2026-03-16. See `fourth_run_lessons.md`.
**Depends on:** Run 3 completed (2026-03-15), `/diagnose-moneyness` run (2026-03-16), DART API research (2026-03-16)

This document supplements `fourth_run_prep.md` with actual DART investigation results. The original prep assumed 8 companies with no DART data and 2 with partial adjustments. The reality is more nuanced.

---

## What we expected vs what we found

**Expected (from fourth_run_prep.md):**
- 8 companies with `k_adj_factor=1.0`: no DART filing found
- 2 companies with partial adjustment: some events but not enough

**Actual (from diagnosis):**

| Corp code | Original assumption | Actual finding |
|-----------|-------------------|----------------|
| 00349811 | No DART filing | Has 5:1 from 2016 PLUS 4 more filings from 2024-2025 (SPLIT, PAR_VALUE_CHANGE) not in crDecsn |
| 00299464 | No DART filing | Zero DART filings, but two massive price discontinuities (-53%, -79%) |
| 00232007 | Partial (kadj=3.0) | Both crDecsn events are applied; remaining 17.8x is undiscoverable |
| 01259056 | No DART filing | Has 2 crDecsn filings (10:1 + 3.2:1) — consolidations BEFORE CB issuance. kadj=1.0 is correct. **GENUINE_ITM** |
| 00971090 | No DART filing | Has 2 crDecsn filings (20:1 + 3.7:1) — consolidations BEFORE CB issuance. kadj=1.0 is correct. **GENUINE_ITM** |
| 00243979 | No DART filing | 1 PAR_VALUE_CHANGE filing (2024-12). No crDecsn data. No price jumps. |
| 00519252 | No DART filing | Has 10:1 from 2015 in parquet but kadj=1.0 (CBs post-2015). Additional -71.1% price discontinuity (2023-01) not in any DART filing. |
| 00475718 | Partial (kadj=2.0) | 42.3x factor exists in corp_actions.parquet but effective_date=None — **dropped by pipeline**. Also 2026-03-09 consolidation in DART list.json. |
| 00175623 | No DART filing | Confirmed: zero filings, zero price discontinuities. **INCONCLUSIVE** |
| 01003040 | No DART filing | 3 DART list.json filings (CONSOLIDATION, SPLIT, PAR_VALUE_CHANGE) from 2024 — none in crDecsn |

---

## Diagnosis verdicts

| Verdict | Companies | Rows | Corp codes |
|---------|-----------|------|------------|
| **SPLIT_ARTIFACT** | 3 | 8 | 00349811, 00475718, 01003040 |
| **LIKELY_SPLIT_ARTIFACT** | 3 | 18 | 00299464, 00232007, 00519252 |
| **GENUINE_ITM** | 2 | 4 | 01259056, 00971090 |
| **INCONCLUSIVE** | 2 | 2 | 00243979, 00175623 |

---

## Detailed company analysis

### SPLIT_ARTIFACT (confirmed, ratios partially discoverable)

**00349811 (ticker=052300) — 5 rows, max 52.3x**
- corp_actions.parquet: 1 event, 5:1 consolidation (effective 2016-07-01)
- DART list.json found 4 MORE events from 2024-2025: CONSOLIDATION (2024-11-14), SPLIT (2024-12-24), CONSOLIDATION (2025-01-07), PAR_VALUE_CHANGE (2025-01-31)
- These are filed under different disclosure types — crDecsn.json does not capture them
- Price data ends 2022-02-14. The 2024-2025 events are post-price-data, but pykrx adjusted=True retroactively applies them to all historical prices
- Rows with kadj=5.0 (pre-2016 CBs) still show 10.1-10.9x — need ~10x additional factor from the 2024-2025 events
- Rows with kadj=1.0 (post-2016 CBs) show 10.5-52.3x — need the 2024-2025 factor only
- **Resolution:** Ratios not available from crDecsn. Need to query filing detail endpoint or infer from price data.

**00475718 (ticker=083470) — 2 rows, max 10.5x**
- corp_actions.parquet: 2 events
  - effective_date=None, factor=42.3x (rcept_no=20200227003262, cr_rt_ostk=97.64%) — **dropped by pipeline due to NaN date**
  - effective_date=2021-10-27, factor=2.0 — applied (kadj=2.0)
- DART list.json: additional CONSOLIDATION filing (2026-03-09)
- Price discontinuities: -53.7% (2018-02-23), -72.9% (2023-07-27) — consistent with multiple consolidation events
- **Resolution:** Recover the effective_date for the 42.3x event from the filing detail. The 2026-03 event may need to be added as well.

**01003040 (ticker=192250) — 1 row, 10.0x**
- NOT in corp_actions.parquet (crDecsn returns nothing)
- DART list.json: 3 filings — CONSOLIDATION (2024-08-01), SPLIT (2024-10-08), PAR_VALUE_CHANGE (2024-10-31)
- Price data ends 2019-12-30. All events are from 2024, so pykrx adjusted prices for 2016-2019 reflect them retroactively.
- CB cv_prc=2,503, adjusted S=25,100, moneyness=10.0x. If the combined 2024 events represent ~10x, true moneyness ≈ 1.0x (at-the-money).
- **Resolution:** Ratios not in crDecsn (different filing types). Need different DART endpoint or price-based estimation.

### LIKELY_SPLIT_ARTIFACT (inferred, no definitive DART evidence)

**00299464 (ticker=047820) — 5 rows, max 20.7x**
- Zero corporate action filings in both crDecsn and DART list.json
- Two price discontinuities: -53.4% (2018-02-19) suggesting ~2:1, and -79.0% (2024-12-20) suggesting ~5:1
- Combined inferred factor: ~10x. Would bring max moneyness from 20.7x to ~2x — plausible.
- The -79% drop in Dec 2024 screams reverse split, but DART has no filing. Possibly a delisting/relisting event or filed under a category not covered by keyword search.
- **Resolution:** Price-inferred factor (~10x) or exclude.

**00232007 (ticker=042940) — 6 rows, max 17.8x**
- corp_actions.parquet: 2 events — 2:1 (2015-09-01) and 3:1 (2024-09-30)
- kadj=3.0 in scores (only the 2024 3:1 applied — CBs were issued after the 2015 event, so the 2:1 correctly doesn't apply)
- No additional DART filings. No price discontinuities.
- Still 17.8x after kadj=3.0 — would need ~6x more factor, origin unknown
- No evidence of pre-2010 events or restructuring
- **Resolution:** Exclude. Known events are correctly applied; remaining factor is undiscoverable.

**00519252 (ticker=089230, THE E&M) — 7 rows, max 11.0x**
- corp_actions.parquet: 1 event, 10:1 (2015-10-24). kadj=1.0 in scores — CBs issued after 2015, so the 10:1 correctly doesn't apply.
- Price discontinuity: -71.1% (2023-01-09), suggesting ~3.5:1 consolidation. No DART filing for this event.
- If 3.5x factor applied: K=290*3.5=1,015, S=3,180, moneyness ≈ 3.1x — reasonable.
- **Resolution:** Price-inferred factor (~3.5x) or exclude.

### GENUINE_ITM (confirmed, no action needed)

**01259056 (ticker=299910) — 2 rows, 13.8x**
- corp_actions.parquet: 2 events — 10:1 (2023-10-26) and 3.16:1 (2023-10-24). Combined 31.6x.
- kadj=1.0 — both consolidations occurred BEFORE CB issuance. The `cumulative_factor()` logic correctly returns 1.0 (no events after issue_date).
- CB cv_prc=500 KRW (minimum par value). S=6,880. Both prices are in post-consolidation denomination.
- 167 price data points, ALL at exactly 6,880 KRW — flat line. KOSDAQ micro-cap with near-zero liquidity.
- **This is a real forensic signal:** company issued CBs at minimum par value when stock was 13.8x higher.

**00971090 (ticker=263540) — 2 rows, 11.9x**
- corp_actions.parquet: 2 events — 20:1 (2021-09-27) and 3.68:1 (2023-01-25). Combined 73.6x.
- kadj=1.0 — both consolidations occurred BEFORE CB issuance. Same logic as 01259056.
- CB cv_prc=500 KRW (par value). S=5,950. Post-consolidation denomination on both sides.
- Earlier CBs for this company had cv_prc=6,653 and 4,074 (pre-consolidation, normal pricing). The K=500 CBs were issued after massive consolidation events — distressed company issuing at minimum conversion price.
- **This is a real forensic signal.**

### INCONCLUSIVE (insufficient evidence)

**00243979 (ticker=084180) — 1 row, 11.1x**
- No crDecsn data. One PAR_VALUE_CHANGE filing (2024-12-23) in list.json, but no ratio data available.
- Price declined gradually from 34k to 1.5k over years. No discontinuities >50%.
- 26 CB filings (frequent issuer). K=933, S=10,400. Borderline plausible as genuine deep ITM.
- **Resolution:** Exclude due to insufficient evidence. The par value change may have caused a denomination mismatch, but we cannot confirm or quantify.

**00175623 (ticker=050120) — 1 row, 10.4x**
- Zero DART filings. Zero price discontinuities. 242 prices (2019-2022).
- K=855, S=8,930. No evidence of splits.
- **Resolution:** Exclude. Cannot distinguish genuine from artifact with available data.

---

## Structural finding: crDecsn.json blind spot

The most significant finding is that the `crDecsn.json` DART endpoint (감자결정 / capital reduction decisions) **does not capture all share-denomination-changing events**. Corporate actions filed as:

- **주식병합** (share consolidation) — sometimes filed under crDecsn, sometimes not
- **액면변경** (par value change) — separate disclosure type, not in crDecsn
- **주식분할** (stock split) — separate disclosure type, not in crDecsn

These all produce the same denomination mismatch effect on moneyness calculations. The current extractor (`extract_corp_actions.py`) is structurally unable to catch them.

**Evidence:**
- 00349811: 4 filings in list.json (2 CONSOLIDATION, 1 SPLIT, 1 PAR_VALUE_CHANGE), only 1 in crDecsn
- 01003040: 3 filings in list.json (CONSOLIDATION, SPLIT, PAR_VALUE_CHANGE), 0 in crDecsn
- 00243979: 1 PAR_VALUE_CHANGE in list.json, 0 in crDecsn

This is not a bug — crDecsn is designed for capital reduction decisions. But it means the K-adjustment pipeline has a structural blind spot for splits and par value changes that affect ~3-5 companies in the current dataset.

---

## DART API research results (2026-03-16)

### Research process

#### Phase 1: Reference file review

Before writing any research code, read all reference files to understand the existing DART query patterns and current state of knowledge:

- `kr-forensic-finance/02_Pipeline/extract_corp_actions.py` — existing `crDecsn.json` extractor. Showed how `_parse_response()` extracts `cr_std` as the effective_date and how `fetch_with_backoff()` handles DART rate limits.
- `kr-forensic-finance/02_Pipeline/_pipeline_helpers.py` — shared `fetch_with_backoff()`, `_dart_api_key()`, DART status code constants.
- `kr-forensic-finance/.env` — confirmed DART_API_KEY is present and valid.
- `kr-derivatives/reports/fourth_run_prep.md` — original Run 4 plan with the 32-row outlier table and Options A/B/C for resolution.
- `kr-derivatives/reports/fourth_run_prep_extra.md` — diagnosis session results with per-company verdicts and the crDecsn.json blind spot finding.
- Verified that `data/curated/manual_k_adjustments.csv` and `excluded_corp_codes.csv` did not yet exist in kr-derivatives (to be created after research).

#### Phase 2: Research script design

Wrote `research_stock_totqy.py` (now in `kr-derivatives/research/`) implementing all 4 plan steps:

- **Step 1**: Queries `stockTotqySttus.json` for all 10 companies x 11 years (2015-2025), annually (reprt_code=11011). For each company, prints common share timelines and flags year-over-year changes >10%. Uses `fetch_with_backoff()` from `_pipeline_helpers.py` for rate limit handling. 110 API calls at 0.5s sleep.
- **Step 1b**: For every company/year pair where Step 1 detected a >10% change, queries quarterly reports (Q1=11013, H1=11012, Q3=11014) plus the prior year's Q3 for tighter bracketing. ~152 additional API calls.
- **Step 2**: Re-queries `crDecsn.json` for corp 00475718 (bgn_de=20150101, end_de=20260316), extracting ALL response fields — not just `cr_std` (which the pipeline uses), but also `bddd` (board decision date), `crsc_nstklstprd` (new listing date), `crsc_trspprpd_bgd/edd` (trading halt period), `cr_mth` (method text). 1 API call.
- **Step 3**: Queries `irdsSttus.json` for 4 priority companies (00349811, 01003040, 00299464, 00519252) across years where Step 1 showed share count changes. Extracts event types (`isu_dcrs_stle`), dates, quantities, and par values. 14 API calls.
- **Step 4**: Prints a synthesis of per-company common share timelines with detected consolidation ratios and directional markers.

Total: 277 API calls. Actual run time: ~2.5 minutes.

#### Phase 3: Script execution and raw results

The script ran successfully with all 277 calls returning data (no rate limit errors). Key raw findings per step:

**Step 1 findings (annual stockTotqySttus):**

| Corp code | Key share count change | Notes |
|-----------|----------------------|-------|
| 00349811 | 보통주 only visible for 2015-2017 (increase). 합계 shows 2020→2021 drop but script missed it | Script bug — see Phase 4 |
| 00299464 | 보통주 only visible for 2015-2017 (increase). 합계 shows 2021→2022 drop but script missed it | Script bug — see Phase 4 |
| 00232007 | 26.48:1 consolidation 2023→2024 (105.5M→3.98M). All years had 보통주 data | Resolved cleanly |
| 01259056 | 1.74:1 decrease 2022→2023 (8.2M→4.7M) | Confirms pre-CB consolidation — GENUINE_ITM |
| 00971090 | 11.98:1 decrease 2020→2021 (17.9M→1.5M) | Confirms pre-CB consolidation — GENUINE_ITM |
| 00243979 | 6.24:1 consolidation 2023→2024 (111.2M→17.8M) | Resolved |
| 00519252 | 8.48:1 consolidation 2023→2024 (185.7M→21.9M). Also 5x increase in 2017 (stock split) | Resolved |
| 00175623 | **10.00:1 consolidation** 2020→2021 (135.6M→13.6M) — previously INCONCLUSIVE | Biggest surprise |
| 01003040 | **10.00:1 consolidation** 2023→2024 (70.7M→7.07M) | Confirmed |
| 00475718 | Small oscillations (~1.4:1) across years, no big consolidation visible in annual | See Step 2 |

**Step 1b findings (quarterly drill-down):**
- 00232007: Q1 2024 (119.5M) → H1 2024 (11.9M) = 10.003:1 — confirms a separate 10:1 event between March and June 2024, distinct from the crDecsn 3:1 event of Sept 2024
- 01003040: Q1-Q3 2024 all show 70.7M, annual shows 7.07M — consolidation between Q3 (Sept) and year-end (Dec)
- 00175623: Q3 2020 (135.6M) → Q1 2021 (13.6M) = exactly 10.0000:1 — consolidation between Oct 2020 and Jan 2021
- 00243979: Q3 2024 (117.5M) → Annual 2024 (17.8M) = 6.594:1 — consolidation in Q4 2024 (matches PAR_VALUE_CHANGE filing 2024-12-23)
- 00519252: Q1 2024 already shows 20.3M (post-consolidation). Event happened between 2023 annual and 2024 Q1

**Step 2 findings (00475718 crDecsn date recovery):**
Two filings returned. The critical one (rcept_no=20200227003262, the 42.3x event):
- `cr_std` (감자기준일): **None** — this is what the pipeline extracted, causing the NaN
- `bddd` (이사회결의일): 2019-11-06 (board decision date)
- `crsc_nstklstprd` (신주상장예정일): **2020-03-09** — new listing date, serves as effective date
- `cr_mth`: "총 발행 주식 64,793,309주 중 AIG JAPAN의 발행 주식 3,483,345주를 무상소각하고 61,309,964주에 대하여 액면가액 500원의 보통주 40주를 액면가액 500원의 보통주 1주로 병합" — 40:1 consolidation
- `bfcr_tisstk_ostk`: 64,793,309 (before)
- `atcr_tisstk_ostk`: 1,530,516 (after)

**Step 3 findings (irdsSttus for priority companies):**
- 00349811 (2016): `무상감자` date=2016.07.02 qty=69,162,122 par=500 + `주식분할` date=2016.07.02 qty=69,162,120 par=100. Confirms the existing crDecsn 5:1 event (capital reduction + 5:1 split on same day, par 500→100).
- 01003040 (2024): Entry with `date=2024.10.15, par_value=1,000` (vs par=100 for all earlier entries). Confirms 10:1 par value change on 2024-10-15.
- 00519252 (2024): Events from 2024.03.14 onward show `par_value=1,000` (vs 100 for pre-2024 events). Confirms par value changed from 100 to 1000 = 10:1.
- 00299464: Only showed `전환권행사`, `유상증자`, `주식매수선택권행사` — no 무상감자 or 주식분할. The 10:1 consolidation visible in stockTotqySttus is invisible to irdsSttus too.

#### Phase 4: The 보통주 vs 합계 detection bug

The script's year-over-year change detection only tracked rows with `se` containing "보통주" (common shares). For two companies (00349811, 00299464), DART stopped reporting a separate 보통주 breakdown after 2017 — only reporting 합계 (total). The detection logic saw these years as having no data and missed major consolidation events.

**Manual trace of 합계 values recovered the missing data:**

00349811 합계 timeline (all years, from raw Step 1 output):
```
2015: 79,710,017  →  2016: 105,321,000  →  2017: 118,983,162
2018: 162,917,940 →  2019: 202,948,646  →  2020: 305,230,454
2021: 101,021,853 ← 3.02:1 DROP
2022: 144,396,967 →  2023: 144,396,967  →  2024: 168,651,435
```

00299464 합계 timeline (all years, from raw Step 1 output):
```
2015: 49,263,122  →  2016: 49,486,787   →  2017: 64,839,923
2018: 108,706,009 →  2019: 116,068,562  →  2020: 166,618,054
2021: 222,043,395
2022: 22,412,655  ← 9.90:1 DROP
2023: 24,453,930  →  2024: 24,453,930
```

This was a **data extraction bug, not a data availability issue** — the raw API responses contained the consolidation evidence all along. The other 8 companies had 보통주 reported in all years, so their detection was unaffected.

#### Phase 5: Critical corrections from stockTotqySttus

The stockTotqySttus data corrected three conclusions from the diagnosis session:

1. **00299464: Price discontinuities were NOT consolidations.** The diagnosis inferred ~2:1 from a -53.4% price drop (2018-02) and ~5:1 from a -79.0% price drop (2024-12). StockTotqySttus proves share counts only INCREASED through both periods (108M→116M in 2018, 24.5M→24.5M in 2024). These were genuine price crashes. The actual consolidation (10:1) occurred in 2021→2022, at a completely different time.

2. **00519252: The -71.1% price drop (2023-01) was NOT a consolidation.** Diagnosis suggested a ~3.5:1 factor from this price event. StockTotqySttus shows 181.6M→185.7M shares in 2022→2023 (slight increase, no consolidation). The actual consolidation (10:1 par value change) happened between 2023 annual and 2024 Q1.

3. **00175623: Reclassified from INCONCLUSIVE to SPLIT_ARTIFACT.** The diagnosis found zero DART filings and zero price discontinuities, concluding the case was INCONCLUSIVE. StockTotqySttus revealed a 10:1 consolidation (135.6M→13.6M) between Q3 2020 and Q1 2021. This was invisible to all other methods because (a) crDecsn doesn't cover this filing type, (b) pykrx adjusted prices retroactively smooth over consolidations so no price discontinuity appears, and (c) no DART disclosure search keyword matched.

#### Phase 6: Synthesis and curated CSV creation

With all raw data analyzed and the 합계 bug resolved, compiled per-company verdicts and created:

1. `data/curated/manual_k_adjustments.csv` — 7 entries (6 with factor=10.0, 1 with factor=40.0 for 00475718)
2. `data/curated/excluded_corp_codes.csv` — 1 entry (00349811, DATA_INSUFFICIENT)
3. Updated this document (`fourth_run_prep_extra.md`) with comprehensive research findings

---

### Method (summary)

Queried three DART endpoints for all 10 companies using `research_stock_totqy.py` (in `kr-derivatives/research/`):

1. **`stockTotqySttus.json`** — Total issued shares per reporting period (annual 2015-2025 + quarterly drill-down for years with detected changes). 262 API calls.
2. **`crDecsn.json`** — Re-query for 00475718 to extract all date fields. 1 API call.
3. **`irdsSttus.json`** — Capital increase/decrease events for 4 priority companies. 14 API calls.

Total: 277 API calls. Run time: ~2.5 minutes.

**Script location**: Originally placed in `kr-forensic-finance/02_Pipeline/` (co-located with DART helpers). Moved to `kr-derivatives/research/` after architectural review — the research resolves kr-derivatives' outliers and should live in kr-derivatives. The script is standalone: it inlines `fetch_with_backoff()`, `_dart_api_key()`, and DART status constants, loading `.env` from kr-forensic-finance by relative path.

### Key unlock: `stockTotqySttus.json`

This endpoint provides authoritative total issued share counts per reporting period. By comparing year-over-year, we can detect ANY share-count-changing event — including splits and par value changes invisible to `crDecsn.json`. It resolved 8 of 10 companies definitively.

### Per-company findings (authoritative)

**00232007 (ticker=042940) — RECLASSIFIED: LIKELY_SPLIT_ARTIFACT → SPLIT_ARTIFACT**
- StockTotqy reveals **10:1 consolidation** between Q1 2024 (119,454,440) and H1 2024 (11,945,444)
- This event is NOT in crDecsn — it's the "undiscoverable" factor the diagnosis couldn't find
- kadj already has 3.0 from the crDecsn 3:1 event (2024-09-30). The 10:1 is a SEPARATE earlier event
- Additional factor needed: 10.0. Total effective: 30.0
- Corrected moneyness: 17.8x / 10 = 1.78x

**00243979 (ticker=084180) — RECLASSIFIED: INCONCLUSIVE → SPLIT_ARTIFACT**
- StockTotqy reveals consolidation: Q3 2024 (117,470,473) → Annual 2024 (17,816,414) = 6.59:1 net
- PAR_VALUE_CHANGE filing dated 2024-12-23 (from diagnosis list.json). Consistent with par 100→1000 = 10:1
- Net ratio <10 due to post-consolidation share issuances in Dec 2024
- Factor used: 10.0 (denomination change, not net share count change)
- Corrected moneyness: 11.1x / 10 = 1.11x

**00299464 (ticker=047820) — RECLASSIFIED: LIKELY_SPLIT_ARTIFACT → SPLIT_ARTIFACT**
- StockTotqy 합계 reveals **~10:1 consolidation** between 2021 (222,043,395) and 2022 (22,412,655)
- This is invisible to crDecsn AND irdsSttus — no 무상감자/주식분할 events in either endpoint
- **Critical correction**: The -53.4% (2018) and -79.0% (2024) price discontinuities from diagnosis are NOT consolidations — stockTotqySttus shows share counts only INCREASED through those periods. They were genuine price crashes.
- Factor: 10.0 (ratio 9.907:1, clean 10:1 with rounding from concurrent issuances)
- Corrected max moneyness: 20.7x / 10 = 2.07x

**00519252 (ticker=089230) — RECLASSIFIED: LIKELY_SPLIT_ARTIFACT → SPLIT_ARTIFACT**
- StockTotqy: Annual 2023 (185,660,126) → Q1 2024 (20,306,607) = 9.14:1 net
- irdsSttus confirms par value changed from 100 to 1000 in 2024 entries = **10:1 denomination change**
- **Critical correction**: The -71.1% price drop (2023-01-09) from diagnosis was NOT a consolidation — stockTotqySttus shows share count stable through 2023 (181.6M → 185.7M, slight increase). It was a genuine price crash.
- Factor: 10.0 (par 100→1000)
- Corrected max moneyness: 11.0x / 10 = 1.10x

**00175623 (ticker=050120) — RECLASSIFIED: INCONCLUSIVE → SPLIT_ARTIFACT**
- StockTotqy reveals **exactly 10:1 consolidation**: Q3 2020 (135,640,864) → Q1 2021 (13,564,086)
- This was completely invisible before: zero crDecsn filings, zero price discontinuities (pykrx adjusted prices smooth over consolidations)
- No quarterly rounding — ratio is 10.0000:1 to 5 decimal places
- Factor: 10.0
- Corrected moneyness: 10.4x / 10 = 1.04x (essentially at-the-money)

**01003040 (ticker=192250) — CONFIRMED: SPLIT_ARTIFACT with authoritative data**
- StockTotqy: Q3 2024 (70,671,257) → Annual 2024 (7,067,125) = **exactly 10:1**
- irdsSttus confirms: 2024 entry shows par_value=1000 (vs 100 for all earlier entries), event date=2024.10.15
- Effective date: 2024-10-15 (from irdsSttus)
- Factor: 10.0
- Corrected moneyness: 10.0x / 10 = 1.00x (exactly at-the-money)

**00475718 (ticker=083470) — NaN DATE RECOVERED**
- crDecsn re-query extracted ALL date fields for the 42.3x event (rcept_no=20200227003262):
  - `cr_std` (감자기준일): None (this is what the pipeline extracted)
  - `bddd` (이사회결의일): 2019-11-06
  - `crsc_nstklstprd` (신주상장예정일): **2020-03-09** — this is the effective date
  - `cr_mth`: "40주를 1주로 병합" (40 shares consolidated into 1 share)
- StockTotqy shows oscillating share counts (consolidation + issuances within same period), consistent with the 40:1 consolidation being immediately followed by massive CB conversion issuances
- **Action**: Added to `manual_k_adjustments.csv` with factor=40.0, effective_date_approx=2020-03-09. The factor is ADDITIONAL to the pipeline's kadj=2.0 from the separate 2:1 event.
- Initially considered a pipeline fix (crsc_nstklstprd fallback in extract_corp_actions.py), but rejected: (1) modifying a production extractor for 1 edge case has cross-repo blast radius, (2) crsc_nstklstprd is semantically different from cr_std and may not be valid for all companies, (3) the company has 0 rows in current scored output anyway. Curated CSV is the correct solution.

**01259056 (ticker=299910) — GENUINE_ITM confirmed**
- StockTotqy: 8,206,916 (2022, stable through Q3 2023) → 4,721,384 (Annual 2023) = 1.74:1
- This reflects the crDecsn consolidations (31.6:1) partially offset by massive post-consolidation issuances
- Confirms: consolidations occurred before CB issuance. kadj=1.0 is correct.

**00971090 (ticker=263540) — GENUINE_ITM confirmed**
- StockTotqy: 17,914,945 (2020) → 1,495,747 (2021) = 11.98:1
- Quarterly: H1 2021 still 29,914,943 → Q3 2021 drops to 1,495,747 (consolidation in Q3 2021)
- Confirms: consolidations occurred before CB issuance. kadj=1.0 is correct.

**00349811 (ticker=052300) — PARTIALLY RESOLVED → EXCLUDED**
- StockTotqy 합계 reveals **3.02:1 consolidation** between 2020 (305,230,454) and 2021 (101,021,853)
- This is a NEW finding not in crDecsn
- irdsSttus (2016): Confirms 무상감자 + 주식분할 on 2016.07.02 (already in crDecsn as 5:1)
- HOWEVER: 2024-2025 events (4 filings from list.json) have unknown net factor
  - 2024 annual shows 168.7M (UP from 2023's 144.4M) — events partially offset
  - 2025 events (Jan 7, Jan 31) not yet in any stockTotqySttus data
- Applying only the 3:1 from 2020-2021 reduces kadj=1 rows from 10.5-52.3x to 3.5-17.4x — still has residual inflation from unknown 2024-2025 factors
- **Resolution: EXCLUDE** (DATA_INSUFFICIENT — cannot determine complete factor)

---

### Revised verdict table (post-research)

| Verdict | Companies | Rows | Corp codes | Change from diagnosis |
|---------|-----------|------|------------|-----------------------|
| **SPLIT_ARTIFACT (resolvable)** | 6 | 21 | 00232007, 00243979, 00299464, 00519252, 00175623, 01003040 | +3 (was 3+3 uncertain) |
| **SPLIT_ARTIFACT (curated CSV)** | 1 | 2 | 00475718 | NaN date recovered; factor=40.0 via manual_k_adjustments.csv |
| **GENUINE_ITM** | 2 | 4 | 01259056, 00971090 | Confirmed |
| **EXCLUDED** | 1 | 5 | 00349811 | Was SPLIT_ARTIFACT, partially resolved but incomplete |

---

## Curated data files (created 2026-03-16)

### `data/curated/manual_k_adjustments.csv`

7 companies with authoritative additional K adjustment factors:

| Corp code | Factor | Effective date (approx) | Source | Expected corrected moneyness |
|-----------|--------|-------------------------|--------|------------------------------|
| 00232007 | 10.0 | 2024-05-15 | STOCK_TOTQY | 17.8x → 1.78x |
| 00243979 | 10.0 | 2024-12-23 | STOCK_TOTQY+LIST_JSON | 11.1x → 1.11x |
| 00299464 | 10.0 | 2022-01-15 | STOCK_TOTQY | 20.7x → 2.07x |
| 00519252 | 10.0 | 2024-01-15 | IRDS_STTUS+STOCK_TOTQY | 11.0x → 1.10x |
| 00175623 | 10.0 | 2020-12-15 | STOCK_TOTQY | 10.4x → 1.04x |
| 01003040 | 10.0 | 2024-10-15 | IRDS_STTUS+STOCK_TOTQY | 10.0x → 1.00x |
| 00475718 | 40.0 | 2020-03-09 | CR_DECSN_DATE_RECOVERY | NaN cr_std recovered via crsc_nstklstprd; 40:1 consolidation; ADDITIONAL to pipeline kadj=2.0 |

These factors are ADDITIONAL to any existing kadj from corp_actions.parquet. The screen script should multiply K by both kadj AND the manual factor.

### `data/curated/excluded_corp_codes.csv`

1 company excluded:

| Corp code | Reason |
|-----------|--------|
| 00349811 | DATA_INSUFFICIENT — partial 3:1 from 2020-2021 confirmed but 2024-2025 events have unknown net factor |

### 00475718 resolution (curated CSV, not pipeline fix)

Initially considered modifying `extract_corp_actions.py` to use `crsc_nstklstprd` as fallback when `cr_std` is NaN. Rejected after architectural review:
- **Cross-repo blast radius**: modifying a production extractor in kr-forensic-finance for 1 edge case in kr-derivatives' analysis
- **Semantic mismatch**: `crsc_nstklstprd` (new listing date) is not equivalent to `cr_std` (capital reduction record date) for all filings
- **Zero current impact**: 00475718 has 0 rows in the current scored output (filtered out by screen)

Instead, added to `manual_k_adjustments.csv` with factor=40.0, effective_date_approx=2020-03-09, source=CR_DECSN_DATE_RECOVERY. The curated CSV approach keeps the fix in kr-derivatives where the analysis lives.

---

## Open research items — RESOLVED

### 1. Recover 00475718 NaN effective_date → DONE
Recovered: `crsc_nstklstprd` = 2020-03-09. Board decision: 2019-11-06. Method: "40주를 1주로 병합" (40:1 consolidation).

### 2. Get ratios for non-crDecsn filings → DONE
- 01003040: 10:1 from stockTotqySttus + irdsSttus (par 100→1000, date=2024-10-15)
- 00349811: Partially resolved (3:1 from stockTotqySttus 2020-2021), but incomplete — excluded

### 3. Validate price-inferred factors → SUPERSEDED
Price-inferred factors from diagnosis were WRONG. StockTotqySttus proves:
- 00299464: -53.4% and -79% price drops were NOT consolidations (share counts increased). True factor: 10:1 from 2021→2022 share count drop.
- 00519252: -71.1% price drop was NOT a consolidation (share count stable). True factor: 10:1 par value change (100→1000) in late 2023/early 2024.

### 4. Decision on INCONCLUSIVE cases → RESOLVED
Both reclassified:
- 00243979: → SPLIT_ARTIFACT (10:1 par value change from stockTotqySttus)
- 00175623: → SPLIT_ARTIFACT (exactly 10:1 from stockTotqySttus — the discovery that had zero visibility from any other endpoint)

---

## Revised resolution approach (final)

| Category | Companies | Rows | Action | File |
|----------|-----------|------|--------|------|
| Manual K adjustment (authoritative) | 00232007, 00243979, 00299464, 00519252, 00175623, 01003040 | 21 | Apply factor from curated CSV | `manual_k_adjustments.csv` |
| Manual K adjustment (date recovery) | 00475718 | 2 | factor=40.0 in curated CSV (crsc_nstklstprd date recovery) | `manual_k_adjustments.csv` |
| Exclude | 00349811 | 5 | Drop before scoring | `excluded_corp_codes.csv` |
| Keep as-is (genuine ITM) | 01259056, 00971090 | 4 | No change | — |

**Expected Run 4 impact:**

| Metric | Run 3 | Run 4 estimate |
|--------|-------|----------------|
| Moneyness >10x | 32 | 4 (the 2 GENUINE_ITM companies) |
| Rows excluded | 0 | 5 (00349811) |
| Rows manually adjusted | 0 | 23 (21 + 2 from 00475718) |
| Flag rate | 34.0% | ~32-33% |

---

## Methodological insight

`stockTotqySttus.json` is the **authoritative endpoint** for detecting denomination-changing events. Unlike `crDecsn.json` (only captures 감자결정) or `irdsSttus.json` (doesn't always classify consolidations), stockTotqySttus shows the NET effect on total issued shares regardless of the filing type. Combined with quarterly drill-down, it provides date precision to within one quarter.

The previous diagnosis relied on price discontinuities to infer consolidation factors. This research shows that approach is unreliable:
- Price drops can reflect genuine crashes, not consolidations
- pykrx adjusted prices smooth over consolidation events, making them invisible in price data
- stockTotqySttus provides ground truth that corrects both false positives and false negatives

**Recommendation for future pipeline improvements**: Add a `stockTotqySttus.json` extractor stage to systematically capture share count changes for all companies with CB/BW events, not just those identified by crDecsn.

---

## Checklist update (final)

- [x] `/diagnose-moneyness` run on all 10 remaining outlier companies
- [x] Each company classified as SPLIT_ARTIFACT / LIKELY_SPLIT_ARTIFACT / GENUINE_ITM / INCONCLUSIVE
- [x] Identified structural blind spot in crDecsn.json extractor
- [x] Recover 00475718 NaN effective_date → 2020-03-09 from crsc_nstklstprd
- [x] Get ratios for 00349811, 01003040 non-crDecsn filings → resolved via stockTotqySttus
- [x] Decide on price-inferred factors for 00299464, 00519252 → superseded by stockTotqySttus (10:1 each)
- [x] Decide on INCONCLUSIVE handling (00243979, 00175623) → both reclassified as SPLIT_ARTIFACT
- [x] Resolution approach decided (override table + exclusion hybrid)
- [x] Curated CSVs populated (`manual_k_adjustments.csv`, `excluded_corp_codes.csv`)
- [x] 00475718 resolved via curated CSV (factor=40.0, effective_date=2020-03-09) — pipeline fix rejected after architectural review
- [x] Screen script updated to consume curated CSVs (`load_manual_k_adjustments`, `load_excluded_corp_codes`, merged into `build_adjustment_factors`)
- [x] Tests green in kr-derivatives (79 passed)
- [x] Full Run 4 executed (2026-03-16: 2,934 scored, 33.1% flag rate, 4 rows >10x)
- [x] Standard inspection queries run
- [x] `fourth_run_lessons.md` written
