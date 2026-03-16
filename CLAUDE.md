# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Korean derivatives pricing and forensic analytics package.
Standalone — no filesystem dependency on kr-forensic-finance.

## Ecosystem

Part of the Korean forensic accounting toolkit.
- Hub: `../forensic-accounting-toolkit/` | [GitHub](https://github.com/pon00050/forensic-accounting-toolkit)
- Task board: https://github.com/users/pon00050/projects/1
- Role: Analysis library
- Depends on: none (reads data files from kr-forensic-finance, not code imports)
- Consumed by: kr-forensic-finance (CB/BW scoring via MCP tool #11)

---

## Common Commands

```bash
# Install (including dev extras)
uv sync --extra dev

# Run all tests
uv run python -m pytest tests/ -v

# Run a single test file
uv run python -m pytest tests/unit/test_black_scholes.py -v

# Type-check
uv run mypy src/

# Run examples
uv run python examples/01_cb_fair_value.py
uv run python examples/02_issuance_dilution_screen.py \
    --data-path /path/to/cb_bw_events.parquet
```

---

## Architecture

```
src/kr_derivatives/
├── pricing/         # Black-Scholes: bs_call, bs_put, implied_vol, greeks
├── contracts/       # CBSpec, WarrantSpec — match cb_bw_events.parquet schema
├── forensic/        # cb_issuance_score (Level 1), composite_score; repricing_coercion_score (Phase 2)
├── market/          # compute_hist_vol, fetch_ktb_rate (FRED + 3.5% fallback)
├── calendar/        # KRX trading calendar via exchange_calendars XKRX
├── utils/           # constants (FLOOR_RULE=0.70, KTB_DEFAULT_RATE=0.035), dates
├── surfaces/        # Phase 2: SVI vol surface (stub)
└── data/            # Phase 2: KRX Open API reader (stub)
```

### Public API

All primary symbols are importable directly from `kr_derivatives`:

```python
from kr_derivatives import (
    bs_call, bs_put, implied_vol, greeks,       # pricing
    CBSpec, WarrantSpec, ContractType,           # contracts
    cb_issuance_score, composite_score,          # forensic
    compute_hist_vol, fetch_ktb_rate,            # market
)
```

### Forensic signal levels

| Level | Function | Data source | Status |
|-------|----------|-------------|--------|
| 1 | `cb_issuance_score` | DART `exercise_price` | Implemented |
| 1 wrapper | `composite_score` | Wraps Level 1; has_repricing_score=False | Implemented |
| 2 | `repricing_coercion_score` | SEIBRO repricing events | Phase 2 — `NotImplementedError` |

Level 1 fires when `moneyness (S/K) > 1.0` at issuance — conversion option already in-the-money.
`composite_score` severity tiers: `high` (moneyness > 1.10), `medium` (> 1.00), `low`.

**Known data quality issue — adjusted S vs unadjusted K:**
Stock prices from pykrx are split-adjusted; DART exercise prices (cv_prc) are contractual snapshots at original denomination. For stocks with reverse splits/consolidations, this creates false extreme moneyness (e.g., 50-247x). After any screen run with outliers >10x, run `/diagnose-moneyness` from the toolkit hub (`../forensic-accounting-toolkit/`) to classify cases as split artifacts vs genuine ITM. See `reports/second_run_lessons.md` and `reports/third_run_prep.md` for the full investigation trail.

**Why B-S is appropriate for Level 1:** The question is purely "was this option in-the-money at issuance?" — a single-point-in-time snapshot, not a full CB valuation. B-S prices a European call; we are not modelling the path-dependent hold-to-maturity CB value or early conversion. The static moneyness and `bs_call_value` at day zero are all that is needed to establish whether value was transferred to the bondholder at shareholders' expense. Full American/lattice pricing is only relevant for Level 2 (per-repricing event scoring over time).

### Test structure

- `tests/unit/` — isolated unit tests per module; no external I/O
- `tests/golden/` — end-to-end price checks against known CB fair values
- `tests/conftest.py` — shared fixtures: `sample_cb`, `itm_cb`, `price_series`, `market_data`

---

## Known Gaps

| Gap | Why | Status |
|-----|-----|--------|
| T=0 degenerate row — no guard in `CBSpec.time_to_expiry()` | One row where `maturity_date == valuation_date`; B-S returns intrinsic, greeks return `nan` — behavior is correct but undocumented | Unblocked — low priority |
| Phase 2 stubs (`svi.py`, `interpolation.py`, `krx_reader.py`, `repricing.py`) | Blocked on KRX Open API key + SEIBRO API (XB-002, DEFERRED until end of April 2026 — 공공데이터포털 revising API) | Blocked — external |
| 53.6% sigma fallback rate in screen output | KOSDAQ micro-caps lack 30+ days price history; uses `SIGMA_FALLBACK=0.40` | By design — see `fourth_run_lessons.md` |

---

## Conventions

- **No py_vollib dependency.** IV solver is pure scipy (Newton-Raphson + Brent fallback). py_vollib has no Python 3.11 wheels.
- **No KRX scraping in Phase 1.** Phase 2 uses `openapi.krx.co.kr` (official, requires key registration). Do NOT use `data.krx.co.kr`.
- **uv.lock is committed.** After any `pyproject.toml` dependency change, run `uv lock` and commit both files together.
- **TDD.** Tests must exist and fail before implementation.
- `src/kr_derivatives/utils/constants.py` — all shared numeric constants; never hardcode in module code.
- Prices in **KRW** (Korean Won) throughout. No unit mixing.
- All functions must handle edge cases: T=0, sigma=0, zero prices → documented return or `ValueError`.
- `CBSpec.from_parquet_row(row)` is the canonical constructor when loading from `cb_bw_events.parquet`.

---

## Phase 2 Prerequisites

Before starting Phase 2 KRX data access:
- Register at `openapi.krx.co.kr` to obtain KRX Open API key

Before implementing `repricing_coercion_score`:
- SEIBRO API key must be active (see KI-012 in kr-forensic-finance)
- `repricing_history` column in `cb_bw_events.parquet` must be non-empty
- **DEFERRED until end of April 2026** — 공공데이터포털 is revising the SEIBRO dataset/API (KSD not cooperating). Do not attempt until the revised API launches.
