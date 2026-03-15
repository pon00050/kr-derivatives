# Third Run Prep

**Status:** Pending
**Depends on:** Resolving the adjusted/unadjusted price denomination mismatch identified in `second_run_lessons.md`

---

## Root Cause (confirmed in Run 2 investigation)

Run 2 flag rate was unchanged at 49.3% despite implementing gap filter, approximate board date flag, and per-ticker trailing volatility. Post-run investigation confirmed the root cause:

**pykrx `adjusted=True` retroactively scales historical prices for corporate actions (reverse splits, share consolidations), but DART exercise prices (cv_prc) are contractual snapshots at the original denomination.** This creates false extreme moneyness for stocks that underwent share consolidations after CB issuance.

### Verified example: ticker 054180 (corp_code 00356839, MEDICOX)

| Event | Date | Ratio | Shares before | Shares after |
|-------|------|-------|---------------|--------------|
| 1st consolidation | 2022-06-13 | 10:1 | 96,286,151 | 9,628,615 |
| 2nd consolidation | 2025-06-30 | 15:1 | ~8,290,000 | ~550,000 |
| **Cumulative** | — | **150:1** | — | — |

- DART CB filing: cv_prc = 2,165 KRW (Dec 2016, pre-consolidation denomination)
- pykrx adjusted close on 2016-12-14: 161,745 KRW (retroactively multiplied by consolidation factors)
- False moneyness: 161,745 / 2,165 = **74.7x** (artifact)
- Estimated true moneyness: ~161,745 / 150 / 2,165 ≈ **0.50x** (OTM — economically plausible)

Source: DART disclosures 20220511000837 (감자결정) and 20250604000284 (감자결정), confirmed via DART API query.

### Scale of the problem

| Metric | Count |
|--------|-------|
| Extreme moneyness rows (>10x) | 241 |
| Unique corp_codes affected | 50 |
| Tickers with >50% single-day price jumps (clear discontinuity) | 32 / 50 (64%) |
| Tickers without visible jumps but still >10x moneyness | 18 / 50 (36%) |

The 18 tickers without visible discontinuities likely had corporate actions that:
- Were spread across multiple smaller adjustments
- Had adjustment ratios that produced <50% single-day changes (e.g., 2:1 consolidation = +100% adjusted, but the threshold may not catch all patterns)
- Or had adjustments applied by pykrx in a way that smoothed the discontinuity

All 50 tickers should be resolved by using unadjusted prices, regardless of whether the adjustment shows as a visible jump.

---

## Changes Required Before Running

### Change 1 — Upgrade pykrx (BLOCKING, prerequisite for everything else)

**Problem:** pykrx 1.0.51 (currently installed) has a broken `adjusted=False` — it returns empty DataFrames for all tickers tested, including Samsung Electronics (005930).

**Fix:** Upgrade to pykrx 1.2.4 (latest on PyPI as of 2026-03-15).

**Evidence that 1.2.4 supports `adjusted=False`:** The PyPI package description explicitly documents it:
> *"adjusted 파라미터를 사용해서 수정주가가 반영되지 않은 OHLCV 정보를 가져올 수도 있습니다"*
> ```python
> df = stock.get_market_ohlcv("20180427", "20180504", "005930", adjusted=False)
> ```

**Where to fix:** kr-forensic-finance `pyproject.toml` — update pykrx version constraint.

**Verification:** After upgrade, run:
```python
from pykrx import stock
df = stock.get_market_ohlcv_by_date("20180102", "20180105", "005930", adjusted=False)
# Should return Samsung pre-split unadjusted close ~2,550,000 KRW
assert not df.empty
assert df.iloc[0]["종가"] > 2_000_000  # unadjusted pre-split price
```

---

### Change 2 — Dual price columns in extract_price_volume.py (BLOCKING)

**Problem:** `extract_price_volume.py` currently fetches only `adjusted=True` prices (line 59). The screen script needs both:
- **Unadjusted close** for S/K moneyness comparison (same denomination as DART exercise price)
- **Adjusted close** for volatility computation (avoids false return spikes at split dates)

**Where to fix:** kr-forensic-finance `02_Pipeline/extract_price_volume.py`

**Proposed change:**
```python
# Current (line 59):
df = krx_stock.get_market_ohlcv_by_date(start_dt, end_dt, ticker, adjusted=True)

# New:
df_adj = krx_stock.get_market_ohlcv_by_date(start_dt, end_dt, ticker, adjusted=True)
df_unadj = krx_stock.get_market_ohlcv_by_date(start_dt, end_dt, ticker, adjusted=False)
# Merge: keep adjusted close as 'close', add unadjusted as 'close_unadj'
```

**Output schema change:** `price_volume.parquet` gains a new column `close_unadj` (float64). Existing `close` column remains as adjusted (for backward compatibility with volatility computation).

**Risk:** Doubling the pykrx API calls will approximately double the extraction time. Profile this. If too slow, consider fetching unadjusted only for tickers that appear in `cb_bw_events.parquet` (the ~916 tickers used for scoring, not all ~3,900 tickers in the registry).

---

### Change 3 — Use unadjusted price for moneyness in screen script

**Where to fix:** kr-derivatives `examples/02_issuance_dilution_screen.py`

**Changes:**
1. In `build_price_lookup()`: look up `close_unadj` for stock_price (S), keep `close` (adjusted) available for vol computation
2. In `build_vol_lookup()`: continue using `close` (adjusted) — adjusted prices are correct for return-based volatility
3. In `run_screen()`: pass unadjusted S to `cb_issuance_score()`, adjusted-derived sigma to the same function

**New output column:** `price_is_adjusted` (bool) — True if `close_unadj` was unavailable and fallback to adjusted price was used. Allows downstream filtering.

---

### Change 4 — Validate with known cases (verification step, not code change)

After Changes 1-3, before full run:

| Ticker | Corp code | K (DART) | S_adjusted | Expected S_unadj | Expected moneyness |
|--------|-----------|----------|-----------|-------------------|-------------------|
| 054180 | 00356839 | 2,165 | 161,745 | ~1,078 (÷150) | ~0.50 (OTM) |
| 214310 | 00957568 | 1,945 | 480,800 | TBD (delisted) | TBD |
| 060230 | 00363510 | 1,365 | 71,662 | TBD | TBD |
| 005930 | (Samsung) | N/A | 51,020 | ~2,550,000 | N/A (control) |

If ticker 214310 is delisted and pykrx returns no data even with `adjusted=False`, those rows will be dropped (no price available). This is acceptable — delisted stocks with no unadjusted price history cannot be scored reliably.

---

## Intelligence Summary

### Data source capabilities (verified 2026-03-15)

| Source | Adjusted prices | Unadjusted prices | Corporate action history |
|--------|----------------|-------------------|------------------------|
| pykrx 1.0.51 (installed) | Yes | **Broken** (empty) | No |
| pykrx 1.2.4 (PyPI latest) | Yes | **Yes** (documented) | No |
| yfinance | Yes (Close = split-adj) | **No** (Close is adjusted) | No |
| KRX Open API (openapi.krx.co.kr) | Unknown | Unknown | **No** dedicated endpoint |
| KRX Data Marketplace (data.krx.co.kr) | Yes | Yes (via pykrx) | No |
| DART API (opendart.fss.or.kr) | N/A | N/A | **Partial** — 감자결정 disclosures available via list.json endpoint |

### DART API findings

- CB disclosures confirmed authentic: `cvbdIsDecsn.json` returns correct cv_prc values
- Corporate action disclosures: queryable via `list.json` general disclosure search (not via dedicated endpoints — the specific URLs like `crcRdcpDecsn.json` returned "wrong URL" errors)
- For 054180: two 감자결정 (capital reduction) filings found with full detail (ratios, dates, share counts)

### pykrx behavior

- `adjusted=True`: Works correctly. Retroactively scales all historical prices for splits/consolidations.
- `adjusted=False` in 1.0.51: Returns empty DataFrames for ALL tickers (confirmed with Samsung, 214310, 054180).
- API signature supports the parameter: `(fromdate, todate, ticker, freq='d', adjusted=True, name_display=False)`
- The parameter exists but the implementation is broken in 1.0.51. PyPI docs for 1.2.4 show working examples.

### Existing code architecture

- `extract_price_volume.py` has three backends: pykrx (default), FinanceDataReader, yfinance
- All three backends currently return adjusted prices only
- The pykrx backend explicitly passes `adjusted=True` on line 59
- The FinanceDataReader backend is scaffolded but not installed in pyproject.toml
- kr-derivatives `data/sources/krx_reader.py` is a Phase 2 stub (empty)

---

## Expected Outcomes for Run 3

| Metric | Run 2 | Run 3 target | Rationale |
|--------|-------|--------------|-----------|
| Rows scored | 2,939 | ~2,900 (some delisted tickers may lose unadj data) | Acceptable loss |
| Flag rate | 49.3% | <35% | Removing false extreme moneyness from denominator |
| Moneyness >10 count | 241 | <20 | Most are consolidation artifacts |
| Moneyness >5 count | 518 | <50 | Same cause |
| Clean ITM range (1.0-2.0) | 645 | Stable or slightly different | Unadjusted prices change S but not dramatically for non-consolidated stocks |
| Sigma fallback rate | 53.6% | ~53% (unchanged) | Vol still uses adjusted prices |

---

## Pre-Run Checklist

- [ ] pykrx upgraded from 1.0.51 to 1.2.4 in kr-forensic-finance
- [ ] `adjusted=False` verified working (Samsung pre-split test)
- [ ] `extract_price_volume.py` modified to output both `close` and `close_unadj`
- [ ] `price_volume.parquet` regenerated with dual columns
- [ ] Validation cases checked (054180, 214310, 060230)
- [ ] New `price_volume.parquet` copied to kr-derivatives `data/input/`
- [ ] `02_issuance_dilution_screen.py` updated to use `close_unadj` for moneyness
- [ ] Full test suite green in both repos
- [ ] Full run executed
- [ ] Standard inspection queries run
- [ ] `third_run_lessons.md` written

---

## Operational Notes

*(to be filled in during the run)*
