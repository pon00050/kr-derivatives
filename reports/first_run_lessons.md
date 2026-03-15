# First Run Lessons

**Run date:** 2026-03-15
**Script:** `examples/02_issuance_dilution_screen.py`
**Runtime:** 12.6 seconds

---

## Run Summary

| Stage | Count |
|-------|-------|
| Total CB/BW events in `cb_bw_events.parquet` | 3,676 |
| Dropped — null `board_date` | 101 |
| Dropped — no price on snapped date | 328 |
| Dropped — null `exercise_price` or invalid spec | 259 |
| **Scored** | **2,988** |
| **Flagged ITM at issuance** | **1,474 (49.3%)** |

**Assumptions:**
- `sigma = 0.40` — uniform KOSDAQ small-cap realized vol baseline
- `r = 0.035` — KTB default fallback (`BOK_API_KEY` not set)
- Price reference: closing price on the most recent KRX trading day on or before `board_date` (via `previous_trading_day()`)

---

## Results

### Moneyness distribution

| Bucket | Count | Assessment |
|--------|-------|-----------|
| < 0.5 | 250 | Far OTM — may include split-contaminated cases |
| 0.5–0.8 | 197 | OTM |
| 0.8–1.0 | 1,067 | Near but below conversion price |
| 1.0–1.1 (marginal ITM) | 393 | Forensically meaningful |
| 1.1–1.5 | 184 | Clearly ITM |
| 1.5–2.0 | 80 | Strongly ITM |
| 2.0–5.0 | 290 | Very strongly ITM — verify |
| 5.0–10.0 | 273 | Likely contaminated |
| > 10 | 254 | Almost certainly contaminated |

### Top flagged cases (moneyness ranked)

| corp_code | S | K | moneyness | valuation_date |
|-----------|---|---|-----------|----------------|
| 00530413 | 247,017 | 740 | 333.8 | 2018-05-10 |
| 00957568 | 480,800 | 1,945 | 247.2 | 2018-06-22 |
| 00957568 | 147,200 | 844 | 174.4 | 2020-08-26 |
| 00205687 | 45,718 | 500 | 91.4 | 2016-02-26 |
| 00618401 | 172,948 | 1,940 | 89.1 | 2018-04-30 |

---

## Evaluation

### The 49.3% flag rate — inflated, but the core signal is real

The rate is split across a clean signal and a contaminated tail:

| Moneyness bucket | Count | Assessment |
|---|---|---|
| 1.0–1.1 (marginal ITM) | 393 | Forensically meaningful |
| 1.1–2.0 | 264 | Clearly ITM |
| 2.0–5.0 | 290 | Strong signal, verify |
| 5.0–10.0 | 273 | Likely contaminated |
| >10 | 254 | Almost certainly contaminated |

The 527 rows above 5× moneyness are the main problem. The top case — moneyness 334× — shows why: ticker 224060 had two single-day price drops of -78% and -89%, both characteristic of stock splits. The `price_volume.parquet` contains **unadjusted prices**. When a split happened between the board date and when the price series was captured, the historical price is on a pre-split basis while the exercise price is on a post-split basis — the moneyness number is meaningless.

Removing the >5× bucket from the flag count gives roughly **947 flagged of 2,988 scored — ~32%**. That is still a substantial forensic finding, and it is consistent with the academic literature (MDPI 2020 documented that a large proportion of Korean KOSDAQ CBs systematically harm ordinary shareholders).

---

## Three Specific Data Quality Issues

### 1. Unadjusted prices in `price_volume.parquet` (primary issue)

Stock splits are not reflected. Any CB where the issuer executed a stock split between the board date and the price observation date will produce meaningless moneyness. This needs to be resolved at the kr-forensic-finance pipeline level — split-adjusted prices, or a splits table to apply adjustments.

Confirmed evidence: ticker 224060 (corp 00530413, top moneyness case at 334×) showed single-day price drops of -78% (2020-06-29) and -89% (2024-05-17) — both characteristic of stock splits. The stock was trading at ~247,000 KRW in November 2016 and ~3,000 KRW by 2025.

### 2. `board_date == issue_date` for 58% of rows

2,090 of 3,575 rows have no independently captured board meeting date — `board_date` defaulted to `issue_date` in the DART extractor (`extract_cb_bw.py` in kr-forensic-finance). The forensic question asks about the price *when the decision was made*, not when the paperwork was filed. For most CBs these dates are within days of each other (median gap = 0 days), so the impact on the flag decision is small — but it is worth knowing.

### 3. 72 rows with `board_date` more than 2 years before `issue_date`

Using a stock price from 2+ years before the actual issuance is not defensible as a reference price. These rows should be excluded or separately flagged. They contribute disproportionately to extreme moneyness cases — a stock can move enormously over two years with no manipulation involved. The top case (corp 00104810) has a gap of 3,543 days (~9.7 years).

---

## What This Means for the Tool

The **clean signal range (1.0–2.0 moneyness, ~22% of scored CBs)** is defensible and actionable today. The tail above 5× needs the split-adjustment problem solved before those cases can be included in any output that goes to a human reviewer or regulator.

The fix is entirely upstream in kr-forensic-finance's `extract_price_volume.py` — split-adjusted OHLCV is a standard data quality requirement, not a change to kr-derivatives itself.

---

## Pipeline Health

| Warning | Count | Cause |
|---------|-------|-------|
| Null `board_date` — skipped | 101 | Missing in DART source data |
| No price on snapped date | 328 | Ticker not in `price_volume.parquet` coverage window |
| Null `exercise_price` or invalid spec | 259 | Missing DART field or date validation failure |

The 328 rows with no price after date snapping (which handles weekends/holidays) indicate tickers whose price history is not covered in `price_volume.parquet`. These are likely companies where the CB issuance date falls outside the ±60 trading-day window that `extract_price_volume.py` captured.

---

## Remaining Issues (Ranked by Priority)

1. **Unadjusted prices** — primary contamination source; affects 527+ rows in the flagged set; must be fixed in kr-forensic-finance before results are defensible above 5× moneyness
2. **Large board-to-issue gaps** — 72 rows with >2 year gap; wrong reference price date; should be excluded or flagged separately
3. **Missing board_date** — 2,090 rows defaulted to issue_date; low impact on flag decision but should be documented in output
4. **328 rows with no price** — investigate whether these are tickers outside the price window or genuinely missing; recover via wider price window if possible
5. **Uniform sigma** — `bs_call_value` precision limited by σ=0.40 assumption; per-date trailing vol is computable from `price_volume.parquet` data already available
6. **BOK_API_KEY not set** — r=3.5% hardcoded; register key at ecos.bok.or.kr for live KTB rate
