"""Base contract types and specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class ContractType(str, Enum):
    """Korean CB/BW contract types as reported in DART filings."""
    CB = "CB"          # Convertible Bond (전환사채)
    BW = "BW"          # Bond with Warrant (신주인수권부사채)
    EB = "EB"          # Exchangeable Bond (교환사채)
    OPTION = "OPTION"  # KRX listed option
    FUTURE = "FUTURE"  # KRX listed future


@dataclass
class ContractSpec:
    """Base contract specification."""
    contract_type: ContractType
    issue_date: date
    maturity_date: date
    exercise_price: float  # KRW

    def time_to_expiry(self, valuation_date: date | None = None) -> float:
        """Return years to maturity from valuation_date (default: issue_date)."""
        start = valuation_date if valuation_date is not None else self.issue_date
        days = (self.maturity_date - start).days
        return max(days / 365.0, 0.0)
