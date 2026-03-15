# Fourth Run Prep

**Status:** Ready to plan
**Depends on:** Run 3 completed (2026-03-15). 32 remaining outliers with moneyness >10x.

---

## What Run 3 resolved

Run 3 implemented Path B (adjust K via DART `crDecsn.json` corporate action data) and reduced the flag rate from 49.3% to 34.0%. Extreme moneyness (>10x) dropped 87%, from 241 to 32 cases. 864 rows across 143 companies were corrected.

See `third_run_lessons.md` for full post-mortem.

---

## Remaining problem: 32 rows, 10 companies still >10x moneyness

| Corp code | Rows | Max moneyness | k_adj_factor | Likely cause |
|-----------|------|---------------|--------------|-------------|
| 00349811 | 5 | 52.3x | 1.0 | No DART 감자결정 found — pre-2015 consolidation or different disclosure type |
| 00299464 | 5 | 20.7x | 1.0 | Same |
| 00232007 | 6 | 17.8x | 3.0 | Partial adjustment — additional consolidations likely exist |
| 01259056 | 2 | 13.8x | 1.0 | No DART 감자결정 found |
| 00971090 | 2 | 11.9x | 1.0 | Same |
| 00243979 | 1 | 11.1x | 1.0 | Same |
| 00519252 | 7 | 11.0x | 1.0 | Same |
| 00475718 | 2 | 10.5x | 2.0 | Partial adjustment — additional consolidations likely exist |
| 00175623 | 1 | 10.4x | 1.0 | No DART 감자결정 found |
| 01003040 | 1 | 10.0x | 1.0 | Same |

### Two categories

1. **`k_adj_factor=1.0` (8 companies, 24 rows):** No corporate action found in DART `crDecsn.json`. Possible explanations:
   - Consolidation before 2015 (DART endpoint coverage starts 2015)
   - Filed under a different disclosure type (not 감자결정)
   - Genuinely extreme ITM issuances (KOSDAQ small-caps do issue deeply ITM CBs, though >10x is rare)

2. **Partial adjustment (2 companies, 8 rows):** DART returned some consolidation events but the cumulative factor doesn't fully explain the moneyness. Additional events may exist outside the query range or under different filing types.

---

## Investigation plan

### Step 1: Classify each company with `/diagnose-moneyness`

Run the diagnostic skill on all 10 companies. For each, determine:
- Was there a consolidation? (Check DART `list.json` general disclosure search for 감자, 병합, 액면분할)
- What was the actual consolidation ratio? (Cross-reference shares outstanding changes)
- Is this genuinely deep-ITM? (Check company fundamentals, stock price trajectory)

### Step 2: Decide per-company resolution

| Classification | Action |
|----------------|--------|
| **SPLIT_ARTIFACT** with known ratio | Add manual adjustment factor to a curated override table |
| **SPLIT_ARTIFACT** pre-2015, ratio discoverable | Same — manual override |
| **SPLIT_ARTIFACT** ratio undiscoverable | Exclude from screen (mark as `DATA_INSUFFICIENT`) |
| **GENUINE_ITM** | Keep as-is — these are real findings |
| **DATA_ERROR** | Fix upstream data |

### Step 3: Implement resolution

Options (choose based on Step 2 findings):

**Option A — Curated override table** (if most are discoverable artifacts):
- Create `data/curated/manual_k_adjustments.csv` with columns: `corp_code, factor, source, notes`
- Screen script loads overrides and applies them after DART-derived adjustments
- Pros: transparent, auditable, handles pre-2015 cases
- Cons: manual maintenance

**Option B — Exclusion filter** (if most are undiscoverable):
- Add `data/curated/excluded_corp_codes.csv` listing companies with known data quality issues
- Screen script drops these before scoring
- Pros: simple, honest about data limitations
- Cons: loses potentially real signals

**Option C — Hybrid** (most likely):
- Override table for companies where the ratio can be determined
- Exclusion for companies where it cannot
- Document the genuine ITM cases prominently in results

### Step 4: Run the screen

After implementing the resolution, re-run the full screen and compare:

---

## Expected outcomes

| Metric | Run 3 | Run 4 target | Rationale |
|--------|-------|--------------|-----------|
| Rows scored | 2,939 | ~2,920-2,939 | May lose a few if excluded |
| Flag rate | 34.0% | 30-33% | Removing up to 32 false-positive rows |
| Moneyness >10x | 32 | <5 | Most should be reclassified or excluded |
| Moneyness >5x | 98 | <80 | Some cascade benefit |

---

## Cleanup items from Run 3

These should also be addressed in Run 4:

1. **FinanceDataReader removal:** Installed via `uv pip install` in kr-forensic-finance (not in pyproject.toml). Remove from venv if not needed.
2. **`COL_CLOSE_UNADJ` constant:** Added to kr-derivatives `constants.py` but unused. Remove or use.
3. **Run index update:** `reports/README.md` run index needs Run 3 results filled in.

---

## Pre-Run Checklist

- [ ] `/diagnose-moneyness` run on all 10 remaining outlier companies
- [ ] Each company classified as SPLIT_ARTIFACT / GENUINE_ITM / DATA_ERROR / INCONCLUSIVE
- [ ] Resolution approach decided (override table, exclusion, or hybrid)
- [ ] Implementation complete (curated CSV + screen script changes)
- [ ] Tests green in kr-derivatives
- [ ] Full run executed
- [ ] Standard inspection queries run
- [ ] `fourth_run_lessons.md` written
