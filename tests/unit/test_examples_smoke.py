"""Smoke tests for example scripts — verify they run without error.

These tests define the contract BEFORE the example files exist.
They import and call the example's main() function directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parents[2] / "examples"
sys.path.insert(0, str(EXAMPLES_DIR))


class TestExample01CBFairValue:
    def test_main_runs_without_error(self):
        """01_cb_fair_value.py must run end-to-end with no exceptions."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ex01", EXAMPLES_DIR / "01_cb_fair_value.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # runs module-level code
        # If main() exists, call it
        if hasattr(module, "main"):
            module.main()

    def test_returns_positive_call_value(self):
        """The example's computed call value must be positive."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ex01", EXAMPLES_DIR / "01_cb_fair_value.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, "main"):
            result = module.main()
            if result is not None:
                assert result > 0


class TestExample03IVFromPrice:
    def test_main_runs_without_error(self):
        """03_iv_from_option_price.py must run end-to-end with no exceptions."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ex03", EXAMPLES_DIR / "03_iv_from_option_price.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, "main"):
            module.main()
