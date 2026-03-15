"""Tests for fetch_ktb_rate.

Contracts:
- Returns KTB_DEFAULT_RATE with a warning when BOK_API_KEY is unset
- Returns KTB_DEFAULT_RATE with a warning when the HTTP request fails
- Returns KTB_DEFAULT_RATE with a warning when ECOS returns an empty row list
- Returns KTB_DEFAULT_RATE with a warning when DATA_VALUE is the '.' sentinel
- Correctly parses a well-formed ECOS response and divides by 100
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kr_derivatives.utils.constants import KTB_DEFAULT_RATE


def _mock_get(json_data: dict, raise_exc: Exception | None = None):
    """Return a mock for requests.get."""
    if raise_exc is not None:
        return patch("kr_derivatives.market.rates.requests.get", side_effect=raise_exc)
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = json_data
    return patch("kr_derivatives.market.rates.requests.get", return_value=mock_resp)


def _ecos_payload(value: str) -> dict:
    return {"StatisticSearch": {"row": [{"DATA_VALUE": value, "TIME": "20260101"}]}}


class TestFetchKtbRateNoKey:
    def test_returns_default_when_key_absent(self, monkeypatch):
        monkeypatch.delenv("BOK_API_KEY", raising=False)
        from kr_derivatives.market.rates import fetch_ktb_rate

        with pytest.warns(UserWarning, match="BOK_API_KEY not set"):
            rate = fetch_ktb_rate()

        assert rate == KTB_DEFAULT_RATE


class TestFetchKtbRateWithKey:
    @pytest.fixture(autouse=True)
    def set_key(self, monkeypatch):
        monkeypatch.setenv("BOK_API_KEY", "testkey123")

    def test_parses_valid_response(self):
        from kr_derivatives.market.rates import fetch_ktb_rate

        with _mock_get(_ecos_payload("3.288")):
            rate = fetch_ktb_rate()
        assert rate == pytest.approx(0.03288)

    def test_divides_by_100(self):
        """ECOS returns percent — 3.5 must become 0.035."""
        from kr_derivatives.market.rates import fetch_ktb_rate

        with _mock_get(_ecos_payload("3.5")):
            rate = fetch_ktb_rate()
        assert rate == pytest.approx(0.035)

    def test_empty_rows_returns_default(self):
        from kr_derivatives.market.rates import fetch_ktb_rate

        with _mock_get({"StatisticSearch": {"row": []}}):
            with pytest.warns(UserWarning):
                rate = fetch_ktb_rate()
        assert rate == KTB_DEFAULT_RATE

    def test_dot_sentinel_returns_default(self):
        """ECOS returns '.' for unreleased/missing values."""
        from kr_derivatives.market.rates import fetch_ktb_rate

        with _mock_get(_ecos_payload(".")):
            with pytest.warns(UserWarning):
                rate = fetch_ktb_rate()
        assert rate == KTB_DEFAULT_RATE

    def test_http_error_returns_default(self):
        from kr_derivatives.market.rates import fetch_ktb_rate

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        with patch("kr_derivatives.market.rates.requests.get", return_value=mock_resp):
            with pytest.warns(UserWarning, match="BOK ECOS fetch failed"):
                rate = fetch_ktb_rate()
        assert rate == KTB_DEFAULT_RATE

    def test_request_exception_returns_default(self):
        from kr_derivatives.market.rates import fetch_ktb_rate

        with _mock_get({}, raise_exc=Exception("timeout")):
            with pytest.warns(UserWarning, match="BOK ECOS fetch failed"):
                rate = fetch_ktb_rate()
        assert rate == KTB_DEFAULT_RATE
