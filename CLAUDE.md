# CLAUDE.md — kr-derivatives

Korean derivatives pricing and forensic analytics package.
Standalone — no filesystem dependency on kr-forensic-finance.

---

## Common Commands

```bash
# Install (including dev extras)
uv sync --extra dev

# Run tests
uv run python -m pytest tests/ -v

# Run a single test file
uv run python -m pytest tests/unit/test_black_scholes.py -v

# Type-check
uv run mypy src/

# Run example
uv run python examples/01_cb_fair_value.py

# Screen cb_bw_events.parquet (pass your own path)
uv run python examples/02_issuance_dilution_screen.py \
    --data-path /path/to/cb_bw_events.parquet
```

---

## Architecture

```
src/kr_derivatives/
├── pricing/         # Black-Scholes: bs_call, bs_put, implied_vol, greeks
├── contracts/       # CBSpec, WarrantSpec — match cb_bw_events.parquet schema
├── forensic/        # cb_issuance_score (Phase 1), repricing_coercion_score (Phase 2)
├── market/          # compute_hist_vol, fetch_ktb_rate (FRED fallback 3.5%)
├── calendar/        # KRX trading calendar via exchange_calendars XKRX
├── utils/           # constants (FLOOR_RULE=0.70, KTB_DEFAULT_RATE=0.035), dates
├── surfaces/        # Phase 2: SVI vol surface (stub)
└── data/            # Phase 2: KRX Open API reader (stub)
```

### Forensic signal levels

| Level | Signal | Data source | Status |
|-------|--------|-------------|--------|
| 1 | At-issuance ITM detection (`cb_issuance_score`) | DART `exercise_price` | Implemented |
| 2 | Per-repricing coercion (`repricing_coercion_score`) | SEIBRO repricing events | Phase 2 — `NotImplementedError` |

Level 1 fires when `moneyness (S/K) > 1.0` at issuance — conversion option already in-the-money, bondholder subsidy guaranteed from day one.

---

## Conventions

- **No py_vollib dependency.** IV solver is pure scipy (Newton-Raphson + Brent fallback). py_vollib has no Python 3.11 wheels — source-only, unmaintained since 2017.
- **No KRX scraping in Phase 1.** KRX Marketplace POST endpoint (`data.krx.co.kr/comm/bldAttendant/getJsonData.cmd`) is undocumented and fragile. Phase 2 uses `openapi.krx.co.kr` (official, requires key registration).
- **uv.lock is committed.** After any `pyproject.toml` dependency change, run `uv lock` and commit both files together.
- **TDD.** Tests must exist and fail before implementation. All new behavior goes test-first.
- `src/kr_derivatives/utils/constants.py` — all shared numeric constants; never hardcode in module code.
- Prices in **KRW** (Korean Won) throughout. No unit mixing.
- All functions must handle edge cases: T=0, sigma=0, zero prices → documented return or ValueError.

---

## Knowledge Layer — Work Needed

The following `knowledge/` notes were planned but not written — they require domain research
that hasn't been done yet. Do not fabricate content for these; write them only once you have
verified sources.

| Note | What it needs |
|------|--------------|
| `knowledge/context/cb-mechanics.md` | Regulatory cite for 70% repricing floor; exact text of 2023 FSC amendments to CB/BW rules |
| `knowledge/context/pricing-models.md` | Verified comparison of Black-Scholes vs Tsiveriotis-Fernandes for Korean CBs; when credit-risk adjustment matters at KOSDAQ scale |
| `knowledge/context/forensic-signals.md` | Academic or regulatory sources confirming ITM-at-issuance and repricing coercion as recognised manipulation patterns |
| `knowledge/hypotheses/repricing-coercion.md` | Threshold calibration from actual SEIBRO data — can only be written after repricing events are available (KI-012) |

---

## Phase 2 Prerequisites

Before starting Phase 2 KRX data access:
- Register at `openapi.krx.co.kr` to obtain KRX Open API key
- Do NOT use the unofficial POST endpoint at `data.krx.co.kr`

Before implementing `repricing_coercion_score`:
- SEIBRO API key must be active (see KI-012 in kr-forensic-finance)
- `repricing_history` column in `cb_bw_events.parquet` must be non-empty
