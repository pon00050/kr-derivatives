"""Convertible Bond (전환사채) contract specification."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .base import ContractSpec, ContractType


@dataclass
class CBSpec(ContractSpec):
    """Full specification for a Korean convertible bond.

    Attributes:
        corp_code: DART 8-digit company identifier.
        exercise_price: Initial conversion price (K) in KRW. From DART field.
        issue_date: Bond issuance date.
        maturity_date: Bond maturity / option expiry date.
        refixing_floor: Minimum floor for repricing (e.g. 0.70 = 70% of initial K).
            None if not specified or not applicable.
        bond_type: 'CB' or 'EB' — from DART bond_type column.
        issue_amount: Face value of the bond in KRW. Optional.
        board_date: Board resolution date for issuance. Optional.
        warrant_separable: Whether warrants are detachable (BW only). Optional.
    """

    corp_code: str = ""
    refixing_floor: float | None = None
    bond_type: str = "CB"
    issue_amount: float | None = None
    board_date: date | None = None
    warrant_separable: bool | None = None

    def __post_init__(self) -> None:
        self.contract_type = ContractType.CB

    @classmethod
    def from_parquet_row(cls, row: dict) -> "CBSpec":
        """Construct a CBSpec from a cb_bw_events.parquet row dict.

        Expected keys: corp_code, exercise_price, issue_date, maturity_date,
        refixing_floor, bond_type, issue_amount, board_date, warrant_separable.
        """
        def to_date(v) -> date | None:
            if v is None:
                return None
            if isinstance(v, date):
                return v
            return date.fromisoformat(str(v)[:10])

        issue = to_date(row.get("issue_date"))
        maturity = to_date(row.get("maturity_date"))
        if issue is None or maturity is None:
            raise ValueError(f"Missing issue_date or maturity_date in row: {row}")

        ep = row.get("exercise_price")
        if ep is None:
            raise ValueError(f"exercise_price is null for corp_code={row.get('corp_code')}")

        return cls(
            contract_type=ContractType.CB,
            issue_date=issue,
            maturity_date=maturity,
            exercise_price=float(ep),
            corp_code=str(row.get("corp_code", "")),
            refixing_floor=float(row["refixing_floor"]) if row.get("refixing_floor") is not None else None,
            bond_type=str(row.get("bond_type", "CB")),
            issue_amount=float(row["issue_amount"]) if row.get("issue_amount") is not None else None,
            board_date=to_date(row.get("board_date")),
            warrant_separable=row.get("warrant_separable"),
        )
