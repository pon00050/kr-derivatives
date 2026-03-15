# Issuance Dilution Screen Run Records

Each screen run produces two documents, written in order:

---

## File Pattern

### `{n}_run_prep.md` — written before the run
Documents everything that happened between the previous lessons document and
the moment the full run is launched. Contains:

- **Pipeline changes** — what was modified in the code or input data and why,
  with a link back to the specific issue identified in the prior `lessons.md`
- **Expected outcomes** — what improvement we expect to see for each change,
  stated as measurable targets where possible (e.g. "extreme moneyness cases
  <5% of flagged rows")
- **Data quality checks** — findings from any pre-run inspection; any filters
  or exclusions added as a result
- **Operational notes** — anything that went wrong during setup or the run
  itself (missing files, schema changes, environment issues, etc.)

### `{n}_run_lessons.md` — written after the run completes
Formal post-mortem of the completed screen run. Contains:

- **Run summary** — input row counts, scored counts, flag counts, runtime
- **Results** — flag rate, moneyness distribution, top flagged cases
- **Data quality findings** — tables or observations comparing this run to
  prior runs; any contamination sources identified
- **What worked** — changes that achieved their target, with evidence
- **Remaining issues** — problems not yet resolved, with root cause analysis
  and concrete remediation options ranked by priority
- **Pipeline health** — rows dropped at each stage, warnings, edge cases

---

## Run Index

| Run | Prep | Lessons | Key change | Flag rate | Outcome |
|-----|------|---------|------------|-----------|---------|
| 1 | — | `first_run_lessons.md` | Initial real-price run (board_date join via `previous_trading_day`) | 49.3% | Unadjusted price contamination identified; clean signal ~22% |
| 2 | `second_run_prep.md` | `second_run_lessons.md` | Split-adjusted prices + gap filter + per-ticker vol | 49.3% | Denomination mismatch found: adjusted S vs unadjusted K |
| 3 | `third_run_prep.md` | `third_run_lessons.md` | Adjust K via DART corporate actions (Path B) | 34.0% | Flag rate -15.3pp, extreme moneyness -87%; 32 outliers remain |
| 4 | `fourth_run_prep.md` | — | Resolve 32 remaining >10x outliers | — | — |

---

## Run Protocol

Follow this sequence for every run:

1. **Write `{n}_run_prep.md`** — document all code/data changes and expected outcomes
2. **Sync input data:** `bash ecosystem.sh copy-parquets` (from the hub repo) — ensures `price_volume.parquet`, `cb_bw_events.parquet`, and `corp_actions.parquet` are current
3. **Inspect input data** — verify row counts, null rates, date ranges, price coverage
4. **Full run:** `uv run python examples/02_issuance_dilution_screen.py`
5. **Inspect output** — run the standard inspection queries (see below)
6. **Write `{n}_run_lessons.md`** — post-mortem including flag rate, quality findings, remaining issues
7. **Commit** — output CSV + both report files

---

## Standard Inspection Queries

Run these after every full run to populate the lessons document:

```python
import pandas as pd

df = pd.read_csv('issuance_dilution_scores.csv')

# Flag rate
print('Flag rate:', df['dilution_flag'].mean())

# Moneyness distribution
bins   = [0, 0.5, 0.8, 1.0, 1.1, 1.5, 2.0, 5.0, 10.0, 999]
labels = ['<0.5','0.5-0.8','0.8-1.0','1.0-1.1','1.1-1.5','1.5-2.0','2.0-5.0','5.0-10.0','>10']
df['bucket'] = pd.cut(df['moneyness'], bins=bins, labels=labels)
print(df['bucket'].value_counts().sort_index())

# Extreme cases (suspect)
print(df[df['moneyness'] > 10][['corp_code','S','K','moneyness']].sort_values('moneyness', ascending=False).head(20))

# T distribution
print(df['T'].describe())
print('T <= 0:', (df['T'] <= 0).sum())
```

```python
import pandas as pd

cb = pd.read_parquet('data/input/cb_bw_events.parquet')
cb['board_date'] = pd.to_datetime(cb['board_date'])
cb['issue_date']  = pd.to_datetime(cb['issue_date'])
cb = cb.dropna(subset=['board_date','issue_date'])
cb['gap_days'] = (cb['issue_date'] - cb['board_date']).dt.days

# Date gap distribution — watch for large-gap contamination
print('board_date == issue_date:', (cb['gap_days'] == 0).sum())
print('gap > 365:', (cb['gap_days'] > 365).sum())
print('gap > 730:', (cb['gap_days'] > 730).sum())
```
