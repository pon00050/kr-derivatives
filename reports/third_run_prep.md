# Third Run Prep

**Status:** Blocked — pykrx `adjusted=False` broken at KRX API level (see Execution Log below)
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
| pykrx 1.2.4 (PyPI latest) | Yes | **Broken** (KRX API returns malformed JSON — verified 2026-03-15) | No |
| yfinance | Yes (Close = split-adj) | **No** (Close is adjusted) | No |
| KRX Open API (openapi.krx.co.kr) | Unknown | Unknown | **No** dedicated endpoint |
| KRX Data Marketplace (data.krx.co.kr) | **Broken** (JSON parse error) | **Broken** | No |
| DART API (opendart.fss.or.kr) | N/A | N/A | **Partial** — 감자결정 disclosures available via list.json endpoint |

### DART API findings

- CB disclosures confirmed authentic: `cvbdIsDecsn.json` returns correct cv_prc values
- Corporate action disclosures: queryable via `list.json` general disclosure search (not via dedicated endpoints — the specific URLs like `crcRdcpDecsn.json` returned "wrong URL" errors)
- For 054180: two 감자결정 (capital reduction) filings found with full detail (ratios, dates, share counts)

### pykrx behavior (updated 2026-03-15 after upgrade to 1.2.4)

- `adjusted=True`: Works correctly via Naver backend. Retroactively scales all historical prices for splits/consolidations.
- `adjusted=False` in 1.0.51: Returns empty DataFrames — parameter existed but was non-functional.
- `adjusted=False` in 1.2.4: Parameter is functional in code, routes to KRX direct API (`data.krx.co.kr`), but **KRX API itself returns malformed JSON** — empty DataFrames for ALL tickers. Server-side issue, not a pykrx bug.
- API signature: `(fromdate, todate, ticker, freq='d', adjusted=True, name_display=False)`
- Naver backend (adjusted=True) and KRX backend (adjusted=False) are completely independent code paths — one working does not imply the other works.

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

- [x] pykrx upgraded from 1.0.51 to 1.2.4 in kr-forensic-finance
- [ ] ~~`adjusted=False` verified working (Samsung pre-split test)~~ **FAILED — see Execution Log**
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

## Execution Log — 2026-03-15 Attempt

### Step 1: pykrx upgrade — COMPLETED, GATE FAILED

**What succeeded:**
- `pyproject.toml` updated: `"pykrx"` → `"pykrx>=1.2.0"`
- `uv lock && uv sync` resolved to pykrx 1.2.4 (also downgraded numpy 2.4.2 → 1.26.4, removed datetime/xlrd/zope-interface)
- `adjusted=True` continues to work via Naver backend (Samsung returns 53,700 KRW for 2025-03-10)

**What failed:**
- `adjusted=False` returns **empty DataFrame for all tickers**, including Samsung (005930) on recent dates (2025-03-10 to 2025-03-14)
- This is NOT a version issue — pykrx 1.2.4 has the correct API signature but the underlying data source is broken

### Root cause analysis

pykrx 1.2.4 routes `adjusted=True` and `adjusted=False` through **completely different backends**:

| Parameter | Backend | Endpoint | Status |
|-----------|---------|----------|--------|
| `adjusted=True` | Naver Finance | `fchart.stock.naver.com/sise.nhn` (XML) | **Working** |
| `adjusted=False` | KRX direct API | `data.krx.co.kr/comm/bldAttendant/getJsonData.cmd` | **Broken** |

The failure chain for `adjusted=False`:
1. `stock_api.get_market_ohlcv_by_date(adjusted=False)` calls `krx.get_market_ohlcv_by_date()`
2. That calls `get_stock_ticker_isin(ticker)` to convert ticker → ISIN
3. `get_stock_ticker_isin()` instantiates `StockTicker()` singleton
4. `StockTicker.__init__()` calls `상장종목검색().fetch("ALL")` — a POST to `data.krx.co.kr`
5. KRX returns HTTP 200 but with **malformed JSON** (line 15, column 3)
6. `requests.JSONDecodeError` is raised
7. The `@dataframe_empty_handler` decorator catches the exception and returns `DataFrame()`
8. `StockTicker().listed` is an empty DataFrame → ticker lookup returns None → ISIN is None → OHLCV fetch is skipped

The error: `simplejson.errors.JSONDecodeError: Expecting value: line 15 column 3 (char 33)`

This is a **KRX server-side issue** — the API endpoint either changed its response format, added anti-scraping protection, or requires different request headers/cookies that pykrx 1.2.4 doesn't send. Even calling the KRX endpoint directly with known ISINs fails with the same JSON parse error.

### Other KRX-dependent endpoints also broken

- `get_market_cap_by_date()` — also uses KRX backend, also returns empty (would have been useful for share count / adjustment factor computation)
- `전종목시세().fetch()` — same JSON decode error
- `개별종목시세().fetch()` with hardcoded ISIN — same error

### What the research phase got wrong

The planning research verified that:
1. pykrx >=1.2.0 has `adjusted=False` in its function signature ✓
2. PyPI documentation shows working examples ✓
3. The parameter didn't exist in 1.0.51 ✓

But it **did not make a live API call** to verify that KRX actually returns data. The PyPI examples may have worked when they were written but the KRX endpoint has since broken. This is a runtime dependency on an external government API that cannot be verified from documentation alone.

### Alternatives explored (not yet resolved)

| Alternative | Status | Notes |
|-------------|--------|-------|
| Direct KRX API call (bypass pykrx) | Failed | Same JSON parse error — server-side issue |
| `get_market_cap_by_date()` for share counts | Failed | Also uses broken KRX backend |
| Naver Finance unadjusted prices | Not available | Naver only serves adjusted (split-corrected) data |
| FinanceDataReader | Not yet tested | Scaffolded in extract_price_volume.py but not installed |
| yfinance | No unadjusted | `auto_adjust=True` is the only reliable mode |
| Compute adjustment factor from listed shares | Blocked | Would need working `get_market_cap_by_date()` or alternative share data source |

### Current state of kr-forensic-finance

- `pyproject.toml` has been modified (`pykrx>=1.2.0`) and `uv.lock` regenerated
- No code changes to `extract_price_volume.py` yet (blocked on gate check)
- pykrx 1.2.4 is installed in `.venv`
- numpy was downgraded to 1.26.4 as a side effect — need to verify this doesn't break anything

### Decision needed

The plan cannot proceed as written. Options:

1. **Find an alternative unadjusted price source** (FinanceDataReader, direct Naver scraping, KRX Open API portal)
2. **Compute adjustment factors from corporate action data** (DART 감자결정 filings already queryable — confirmed in Run 2 investigation)
3. **Build a manual adjustment table** for the 50 affected tickers from DART disclosures
4. **Accept adjusted prices and adjust K instead** — multiply DART exercise prices by cumulative split factors derived from DART filings

Option 4 is architecturally inverted (adjusting K to match S instead of getting raw S to match raw K) but may be more robust since DART API is reliable and under our control.

---

## Operational Notes

*(to be filled in during the run)*
