"""Risk-free rate fetching: FRED Korea 10Y government bond rate.

Series: IRLTLT01KRM156N (Korea Long-Term Government Bond Yields, 10-Year)
Source: FRED (Federal Reserve Bank of St. Louis), free, no API key required.

Fallback: KTB_DEFAULT_RATE = 3.5% if FRED is unreachable.
"""

from __future__ import annotations

import warnings
from datetime import date

from ..utils.constants import KTB_DEFAULT_RATE

# FRED series IDs for Korean government bond rates
_FRED_SERIES = {
    "10y": "IRLTLT01KRM156N",  # Korea 10Y long-term bond rate (monthly)
    "3y": "IR3TIB01KRM156N",   # Korea 3-month interbank (proxy for short rates)
}


def fetch_ktb_rate(
    maturity: str = "10y",
    as_of: date | None = None,
) -> float:
    """Fetch Korea government bond rate from FRED.

    Args:
        maturity: '10y' for 10-year rate (default), '3y' for 3-month proxy.
        as_of: Fetch the rate as of this date. If None, uses most recent available.

    Returns:
        Annual rate as a decimal (e.g. 0.035 = 3.5%).
        Falls back to KTB_DEFAULT_RATE if FRED is unreachable.
    """
    series_id = _FRED_SERIES.get(maturity, _FRED_SERIES["10y"])

    try:
        import pandas_datareader.data as web  # type: ignore

        end = as_of or date.today()
        # Fetch last 90 days to ensure we get the most recent monthly observation
        start = date(end.year - 1, end.month, 1)

        df = web.DataReader(series_id, "fred", start, end)
        df = df.dropna()
        if df.empty:
            warnings.warn(
                f"FRED returned no data for {series_id}; using default {KTB_DEFAULT_RATE:.1%}",
                stacklevel=2,
            )
            return KTB_DEFAULT_RATE

        # FRED reports as percentage (e.g. 3.5 means 3.5%) — divide by 100
        rate = float(df.iloc[-1, 0]) / 100.0
        return rate

    except Exception as exc:
        warnings.warn(
            f"FRED fetch failed ({exc}); using default rate {KTB_DEFAULT_RATE:.1%}",
            stacklevel=2,
        )
        return KTB_DEFAULT_RATE
