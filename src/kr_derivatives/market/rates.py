"""Risk-free rate fetching: Bank of Korea (BOK) KTB 10-year yield.

Series: table 817Y002, item 010210000 (Treasury Bonds 10-year, daily)
Source: BOK ECOS API (ecos.bok.or.kr) — the authoritative publisher of KTB yields.
Auth:   BOK_API_KEY environment variable (free registration at ecos.bok.or.kr).
        If the key is absent or the request fails, falls back to KTB_DEFAULT_RATE = 3.5%.

Note: FRED (api.stlouisfed.org) was the original source but is wrong on two counts:
  - it requires its own API key (request returns HTTP 400 without one)
  - it is a US Fed mirror of OECD data which itself mirrors BOK — two unnecessary hops
  See knowledge/context/ktb-rate-data-source.md for the full audit trail.
"""

from __future__ import annotations

import os
import warnings
from datetime import date

import requests

from ..utils.constants import KTB_DEFAULT_RATE

# BOK ECOS table/item codes for KTB market yields (table 817Y002, daily)
_ECOS_TABLE = "817Y002"
_ECOS_ITEMS = {
    "10y": "010210000",  # Treasury Bonds 10-year
    "5y":  "010200001",  # Treasury Bonds 5-year
    "1y":  "010190000",  # Treasury Bonds 1-year
}
_ECOS_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"


def fetch_ktb_rate(
    maturity: str = "10y",
    as_of: date | None = None,
) -> float:
    """Fetch Korea government bond yield from BOK ECOS.

    Args:
        maturity: '10y' (default), '5y', or '1y'.
        as_of: Target date. If None, uses today. The most recent available
               observation on or before this date is returned (ECOS is daily
               but has a ~1-2 business day publication lag).

    Returns:
        Annual rate as a decimal (e.g. 0.035 = 3.5%).
        Falls back to KTB_DEFAULT_RATE if BOK_API_KEY is unset or request fails.
    """
    api_key = os.environ.get("BOK_API_KEY", "")
    if not api_key:
        warnings.warn(
            "BOK_API_KEY not set; using default KTB rate "
            f"{KTB_DEFAULT_RATE:.1%}. Register free at ecos.bok.or.kr.",
            stacklevel=2,
        )
        return KTB_DEFAULT_RATE

    item_code = _ECOS_ITEMS.get(maturity, _ECOS_ITEMS["10y"])
    end = (as_of or date.today()).strftime("%Y%m%d")
    # Cast a wide enough start window to catch the most recent observation
    start = "19000101"

    # ECOS URL pattern:
    # /StatisticSearch/{key}/json/en/{start_row}/{end_row}/{table}/{freq}/{start}/{end}/{item}
    # Fetch last 1 row in descending order by requesting rows 1-1 (most recent)
    url = (
        f"{_ECOS_BASE}/{api_key}/json/en/1/1"
        f"/{_ECOS_TABLE}/D/{start}/{end}/{item_code}"
    )

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        rows = data.get("StatisticSearch", {}).get("row", [])
        if not rows:
            warnings.warn(
                f"BOK ECOS returned no data for item {item_code}; "
                f"using default {KTB_DEFAULT_RATE:.1%}",
                stacklevel=2,
            )
            return KTB_DEFAULT_RATE

        value_str = rows[-1].get("DATA_VALUE", "")
        if not value_str or value_str == ".":
            warnings.warn(
                f"BOK ECOS returned missing value for item {item_code}; "
                f"using default {KTB_DEFAULT_RATE:.1%}",
                stacklevel=2,
            )
            return KTB_DEFAULT_RATE

        # ECOS reports as percent (e.g. 3.288 means 3.288%)
        return float(value_str) / 100.0

    except Exception as exc:
        warnings.warn(
            f"BOK ECOS fetch failed ({exc}); using default rate {KTB_DEFAULT_RATE:.1%}",
            stacklevel=2,
        )
        return KTB_DEFAULT_RATE
