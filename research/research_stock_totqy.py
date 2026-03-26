"""
research_stock_totqy.py — DART API research to resolve 10 outlier companies.

This is a one-off diagnostic script that was used on 2026-03-16 to resolve
32 rows (10 companies) with moneyness >10x in the issuance dilution screen.
Findings are documented in reports/fourth_run_prep_extra.md.

Queries three DART endpoints to gather authoritative share count data:
  1. stockTotqySttus.json — Total issued shares per reporting period
  2. crDecsn.json — Capital reduction events (re-query for NaN date recovery)
  3. irdsSttus.json — Capital increase/decrease event classification

Dependencies:
  - requests, python-dotenv (both in kr-derivatives' pyproject.toml)
  - DART_API_KEY from krff-shell/.env (read by path)

Output: Prints structured findings per company. Does NOT modify any files.

Usage:
  cd C:/Users/pon00/Projects/kr-derivatives
  uv run python research/research_stock_totqy.py

Known limitation:
  The year-over-year detection in Step 1 and Step 4 only tracks rows with
  se containing "보통주" (common shares). Some companies stop reporting this
  breakdown and only report "합계" (total). The raw data is printed for all
  rows, but the automated detection misses 합계-only years. Manual trace of
  합계 values was required for 00349811 and 00299464 — see Phase 4 in
  fourth_run_prep_extra.md.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ─── DART API infrastructure (standalone, no external code imports) ──────────────

# Load DART_API_KEY from krff-shell's .env
_KR_FF_ENV = Path(__file__).resolve().parent.parent.parent / "krff-shell" / ".env"
load_dotenv(_KR_FF_ENV)

DART_STATUS_OK = "000"
DART_STATUS_NOT_FOUND = "013"
DART_STATUS_RATE_LIMIT = "020"


def _dart_api_key() -> str:
    key = os.getenv("DART_API_KEY", "")
    if not key or key == "your_opendart_api_key_here":
        raise EnvironmentError(
            f"DART_API_KEY not set. Looked in {_KR_FF_ENV}"
        )
    return key


def fetch_with_backoff(
    url: str, params: dict, max_retries: int = 4, base_delay: float = 2.0
) -> dict:
    """GET with exponential backoff on DART Error 020 (rate limit)."""
    delays = [base_delay * (2 ** i) for i in range(max_retries)]
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0.0] + delays):
        if delay:
            print(f"  DART rate limit — retrying in {delay:.0f}s (attempt {attempt}/{max_retries})")
            time.sleep(delay)
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            if str(data.get("status", "")) == DART_STATUS_RATE_LIMIT:
                raise Exception("Error 020 rate limit")
            return data
        except Exception as exc:
            last_exc = exc
            if DART_STATUS_RATE_LIMIT not in str(exc):
                raise
    raise last_exc  # type: ignore[misc]


# ─── Constants ────────────────────────────────────────────────────────────────

SLEEP = 0.5

STOCK_TOTQY_URL = "https://opendart.fss.or.kr/api/stockTotqySttus.json"
CR_DECSN_URL = "https://opendart.fss.or.kr/api/crDecsn.json"
IRDS_STTUS_URL = "https://opendart.fss.or.kr/api/irdsSttus.json"

# Report codes
ANNUAL = "11011"       # 사업보고서
H1 = "11012"           # 반기보고서
Q1 = "11013"           # 1분기보고서
Q3 = "11014"           # 3분기보고서

TARGET_CORPS = [
    "00349811",  # ticker=052300
    "00299464",  # ticker=047820
    "00232007",  # ticker=042940
    "01259056",  # ticker=299910
    "00971090",  # ticker=263540
    "00243979",  # ticker=084180
    "00519252",  # ticker=089230
    "00475718",  # ticker=083470
    "00175623",  # ticker=050120
    "01003040",  # ticker=192250
]

YEARS = list(range(2015, 2026))

# Companies needing irdsSttus follow-up (Step 3 priorities)
IRDS_PRIORITY = ["00349811", "01003040", "00299464", "00519252"]


def _configure_stdout():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def _parse_int(raw) -> int | None:
    """Parse comma-formatted integer."""
    if not raw:
        return None
    s = str(raw).strip().replace(",", "")
    if not s or s == "-":
        return None
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


# ─── Step 1: stockTotqySttus.json ─────────────────────────────────────────────

def query_stock_totqy(api_key: str, corp_code: str, year: int, reprt_code: str) -> list[dict]:
    """Query stockTotqySttus.json for a single company/year/report."""
    data = fetch_with_backoff(
        STOCK_TOTQY_URL,
        params={
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": reprt_code,
        },
    )
    status = str(data.get("status", ""))
    if status == DART_STATUS_NOT_FOUND:
        return []
    if status != DART_STATUS_OK:
        return []
    return data.get("list", [])


def run_step1(api_key: str) -> dict[str, dict]:
    """Query stockTotqySttus for all 10 companies across 2015-2025 annual reports.

    Returns: {corp_code: {year: [{se, istc_totqy, ...}, ...]}}
    """
    print("=" * 80)
    print("STEP 1: stockTotqySttus.json — Total issued shares timeline")
    print("=" * 80)

    results: dict[str, dict] = {}
    call_count = 0

    for corp_code in TARGET_CORPS:
        results[corp_code] = {}
        print(f"\n--- {corp_code} ---")

        for year in YEARS:
            items = query_stock_totqy(api_key, corp_code, year, ANNUAL)
            call_count += 1
            time.sleep(SLEEP)

            if items:
                results[corp_code][year] = items
                # Extract common shares total
                for item in items:
                    se = (item.get("se") or "").strip()
                    totqy = item.get("istc_totqy", "")
                    if "보통주" in se or "합계" in se:
                        print(f"  {year}: {se} = {totqy}")

        # Detect year-over-year changes
        common_shares_by_year = {}
        for year, items in sorted(results[corp_code].items()):
            for item in items:
                se = (item.get("se") or "").strip()
                if "보통주" in se:
                    val = _parse_int(item.get("istc_totqy"))
                    if val is not None:
                        common_shares_by_year[year] = val

        if len(common_shares_by_year) >= 2:
            years_sorted = sorted(common_shares_by_year.keys())
            print(f"\n  Year-over-year changes (common shares):")
            for i in range(1, len(years_sorted)):
                prev_y = years_sorted[i - 1]
                curr_y = years_sorted[i]
                prev_v = common_shares_by_year[prev_y]
                curr_v = common_shares_by_year[curr_y]
                if prev_v > 0:
                    ratio = prev_v / curr_v
                    pct = (curr_v - prev_v) / prev_v * 100
                    if abs(pct) > 10:
                        print(f"  *** {prev_y}→{curr_y}: {prev_v:,} → {curr_v:,} "
                              f"(change: {pct:+.1f}%, ratio: {ratio:.2f}:1)")
        elif len(common_shares_by_year) == 0:
            print("  (no common share data found)")

    print(f"\n  [Step 1 complete: {call_count} API calls]")
    return results


def run_step1_quarterly(api_key: str, step1_results: dict) -> dict[str, dict]:
    """For years where annual data shows a change, query quarterly for precision."""
    print("\n" + "=" * 80)
    print("STEP 1b: Quarterly precision for years with detected changes")
    print("=" * 80)

    # Detect which corp/years need quarterly drill-down
    drill_down: list[tuple[str, int]] = []
    for corp_code, year_data in step1_results.items():
        common_shares_by_year: dict[int, int] = {}
        for year, items in sorted(year_data.items()):
            for item in items:
                se = (item.get("se") or "").strip()
                if "보통주" in se:
                    val = _parse_int(item.get("istc_totqy"))
                    if val is not None:
                        common_shares_by_year[year] = val

        years_sorted = sorted(common_shares_by_year.keys())
        for i in range(1, len(years_sorted)):
            prev_y = years_sorted[i - 1]
            curr_y = years_sorted[i]
            prev_v = common_shares_by_year[prev_y]
            curr_v = common_shares_by_year[curr_y]
            if prev_v > 0 and abs((curr_v - prev_v) / prev_v) > 0.10:
                drill_down.append((corp_code, curr_y))

    if not drill_down:
        print("  No year-over-year changes >10% detected. Skipping quarterly queries.")
        return {}

    quarterly_results: dict[str, dict] = {}
    call_count = 0

    for corp_code, year in drill_down:
        key = f"{corp_code}_{year}"
        quarterly_results[key] = {}
        print(f"\n--- {corp_code} year={year} quarterly drill-down ---")

        for reprt_code, label in [(Q1, "Q1"), (H1, "H1"), (Q3, "Q3")]:
            items = query_stock_totqy(api_key, corp_code, year, reprt_code)
            call_count += 1
            time.sleep(SLEEP)

            if items:
                quarterly_results[key][label] = items
                for item in items:
                    se = (item.get("se") or "").strip()
                    totqy = item.get("istc_totqy", "")
                    if "보통주" in se or "합계" in se:
                        print(f"  {year} {label}: {se} = {totqy}")

        # Also query prior year's Q3 for tighter bracket
        prev_year = year - 1
        items = query_stock_totqy(api_key, corp_code, prev_year, Q3)
        call_count += 1
        time.sleep(SLEEP)
        if items:
            quarterly_results[key][f"{prev_year}_Q3"] = items
            for item in items:
                se = (item.get("se") or "").strip()
                totqy = item.get("istc_totqy", "")
                if "보통주" in se or "합계" in se:
                    print(f"  {prev_year} Q3: {se} = {totqy}")

    print(f"\n  [Step 1b complete: {call_count} API calls]")
    return quarterly_results


# ─── Step 2: crDecsn.json NaN date recovery for 00475718 ──────────────────────

def run_step2(api_key: str):
    """Re-query crDecsn.json for 00475718 and print ALL date fields."""
    print("\n" + "=" * 80)
    print("STEP 2: crDecsn.json date recovery for 00475718")
    print("=" * 80)

    data = fetch_with_backoff(
        CR_DECSN_URL,
        params={
            "crtfc_key": api_key,
            "corp_code": "00475718",
            "bgn_de": "20150101",
            "end_de": "20260316",
        },
    )
    time.sleep(SLEEP)

    status = str(data.get("status", ""))
    if status == DART_STATUS_NOT_FOUND:
        print("  No crDecsn data found for 00475718")
        return

    items = data.get("list", [])
    if not items:
        print("  Empty list returned")
        return

    print(f"  Found {len(items)} crDecsn filings:\n")

    # Date-related fields to extract
    date_fields = [
        ("rcept_no", "접수번호"),
        ("rcept_dt", "접수일자"),
        ("cr_std", "감자기준일"),
        ("bddd", "이사회결의일"),
        ("cr_mth", "감자방법"),
        ("cr_rt_ostk", "감자비율(보통주)"),
        ("bfcr_tisstk_ostk", "감자전 발행주식수(보통주)"),
        ("atcr_tisstk_ostk", "감자후 발행주식수(보통주)"),
        ("crsc_nstklstprd", "신주상장예정일"),
        ("crsc_trspprpd_bgd", "매매거래정지기간 시작"),
        ("crsc_trspprpd_edd", "매매거래정지기간 종료"),
    ]

    for item in items:
        print(f"  Filing rcept_no={item.get('rcept_no', '?')}:")
        for field, label in date_fields:
            val = item.get(field, "(missing)")
            if val is None:
                val = "None"
            val_str = str(val).strip()
            if val_str and val_str != "-":
                print(f"    {label} ({field}): {val_str}")
        print()


# ─── Step 3: irdsSttus.json for priority companies ────────────────────────────

def run_step3(api_key: str, step1_results: dict):
    """Query irdsSttus.json for priority companies in years with share changes."""
    print("\n" + "=" * 80)
    print("STEP 3: irdsSttus.json — Capital increase/decrease event classification")
    print("=" * 80)

    call_count = 0

    for corp_code in IRDS_PRIORITY:
        print(f"\n--- {corp_code} ---")

        # Determine which years to query: all years from step1 that showed changes,
        # plus surrounding years
        query_years = set()
        year_data = step1_results.get(corp_code, {})
        common_shares_by_year: dict[int, int] = {}

        for year, items in sorted(year_data.items()):
            for item in items:
                se = (item.get("se") or "").strip()
                if "보통주" in se:
                    val = _parse_int(item.get("istc_totqy"))
                    if val is not None:
                        common_shares_by_year[year] = val

        years_sorted = sorted(common_shares_by_year.keys())
        for i in range(1, len(years_sorted)):
            prev_y = years_sorted[i - 1]
            curr_y = years_sorted[i]
            prev_v = common_shares_by_year[prev_y]
            curr_v = common_shares_by_year[curr_y]
            if prev_v > 0 and abs((curr_v - prev_v) / prev_v) > 0.10:
                query_years.add(curr_y)
                query_years.add(prev_y)

        # If no changes detected from step1, query broad range
        if not query_years:
            query_years = {2017, 2018, 2019, 2023, 2024, 2025}
            print("  (no step1 changes detected, querying broad range)")

        for year in sorted(query_years):
            data = fetch_with_backoff(
                IRDS_STTUS_URL,
                params={
                    "crtfc_key": api_key,
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": ANNUAL,
                },
            )
            call_count += 1
            time.sleep(SLEEP)

            status = str(data.get("status", ""))
            if status == DART_STATUS_NOT_FOUND:
                print(f"  {year}: no data")
                continue
            if status != DART_STATUS_OK:
                print(f"  {year}: status={status}")
                continue

            items = data.get("list", [])
            if not items:
                print(f"  {year}: empty list")
                continue

            print(f"  {year}: {len(items)} entries")
            for item in items:
                # Print all fields for understanding the structure
                isu_dcrs_de = item.get("isu_dcrs_de", "")
                isu_dcrs_stle = item.get("isu_dcrs_stle", "")
                isu_dcrs_stock_knd = item.get("isu_dcrs_stock_knd", "")
                isu_dcrs_qy = item.get("isu_dcrs_qy", "")
                isu_dcrs_mstvdv_fval_amount = item.get("isu_dcrs_mstvdv_fval_amount", "")
                se = item.get("se", "")
                print(f"    se={se}, type={isu_dcrs_stle}, date={isu_dcrs_de}, "
                      f"qty={isu_dcrs_qy}, par_value={isu_dcrs_mstvdv_fval_amount}, "
                      f"stock_knd={isu_dcrs_stock_knd}")

    print(f"\n  [Step 3 complete: {call_count} API calls]")


# ─── Step 4: Synthesis ────────────────────────────────────────────────────────

def run_step4(step1_results: dict):
    """Synthesize findings from all steps into per-company summaries."""
    print("\n" + "=" * 80)
    print("STEP 4: SYNTHESIS — Per-company share count timelines")
    print("=" * 80)

    for corp_code in TARGET_CORPS:
        year_data = step1_results.get(corp_code, {})
        common_shares: dict[int, int] = {}

        for year, items in sorted(year_data.items()):
            for item in items:
                se = (item.get("se") or "").strip()
                if "보통주" in se:
                    val = _parse_int(item.get("istc_totqy"))
                    if val is not None:
                        common_shares[year] = val

        print(f"\n{'='*60}")
        print(f"Corp: {corp_code}")
        print(f"{'='*60}")

        if not common_shares:
            print("  NO STOCK TOTQY DATA AVAILABLE")
            continue

        print(f"  Common shares timeline:")
        prev_val = None
        for year in sorted(common_shares.keys()):
            val = common_shares[year]
            marker = ""
            if prev_val is not None and prev_val > 0:
                ratio = prev_val / val
                if ratio > 1.1:
                    marker = f"  ◄◄◄ DECREASE: {ratio:.2f}:1 consolidation"
                elif ratio < 0.9:
                    marker = f"  ◄◄◄ INCREASE: {1/ratio:.2f}x"
            print(f"    {year}: {val:>15,}{marker}")
            prev_val = val


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    _configure_stdout()
    api_key = _dart_api_key()

    print("DART API Research: Resolve 10 Outlier Companies")
    print(f"Target corps: {len(TARGET_CORPS)}")
    print(f"Years: {YEARS[0]}-{YEARS[-1]}")
    print()

    # Step 1: stockTotqySttus for all 10 companies
    step1_results = run_step1(api_key)

    # Step 1b: Quarterly precision for years with changes
    run_step1_quarterly(api_key, step1_results)

    # Step 2: crDecsn date recovery for 00475718
    run_step2(api_key)

    # Step 3: irdsSttus for priority companies
    run_step3(api_key, step1_results)

    # Step 4: Synthesis
    run_step4(step1_results)


if __name__ == "__main__":
    main()
