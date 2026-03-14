"""Warrant (신주인수권) specification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .base import ContractSpec, ContractType


@dataclass
class WarrantSpec(ContractSpec):
    """Bond with Warrant (신주인수권부사채) specification.

    Attributes:
        corp_code: DART 8-digit identifier.
        exercise_price: Warrant exercise price in KRW.
        issue_date: Issuance date.
        maturity_date: Expiry of the warrant.
        exercise_ratio: Number of new shares per warrant unit. Default 1.0.
        separable: Whether the warrant is detachable from the bond.
    """

    corp_code: str = ""
    exercise_ratio: float = 1.0
    separable: bool = True

    def __post_init__(self) -> None:
        self.contract_type = ContractType.BW
