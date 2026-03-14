"""Golden tests for CB pricing — 3 reference cases with manually verified BS values.

These test that the bs_call implementation matches hand-computed reference values
within 1 KRW tolerance (exact analytic formula, no sampling error).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from kr_derivatives.pricing.black_scholes import bs_call

GOLDEN_FILE = Path(__file__).parent / "reference_data" / "cb_golden.json"
TOLERANCE_KRW = 1.0  # 1 KRW absolute tolerance


def load_golden_cases():
    with open(GOLDEN_FILE, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("case", load_golden_cases(), ids=[c["id"] for c in load_golden_cases()])
def test_golden_bs_call(case):
    """bs_call must match reference value within 1 KRW."""
    result = bs_call(
        S=case["S"],
        K=case["K"],
        T=case["T"],
        r=case["r"],
        sigma=case["sigma"],
    )
    expected = case["expected_call_value"]
    assert abs(result - expected) <= TOLERANCE_KRW, (
        f"{case['id']} ({case['label']}): "
        f"got {result:.4f}, expected {expected:.4f}, diff={abs(result - expected):.4f}"
    )
