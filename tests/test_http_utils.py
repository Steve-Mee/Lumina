"""Tests for lumina_os.frontend.http_utils."""

from __future__ import annotations

import logging

import httpx
import pytest
import requests

from lumina_os.frontend.http_utils import is_backend_unreachable, log_fetch_failure


def test_is_backend_unreachable_requests_connection_error() -> None:
    assert is_backend_unreachable(requests.exceptions.ConnectionError("down"))


def test_is_backend_unreachable_httpx_connect_error() -> None:
    assert is_backend_unreachable(httpx.ConnectError("down"))


def test_is_backend_unreachable_value_error() -> None:
    assert not is_backend_unreachable(ValueError("bad json"))


def test_log_fetch_failure_debug_when_offline(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    log = logging.getLogger("test.http_utils")
    log_fetch_failure(log, "health", requests.exceptions.ConnectionError("refused"))
    assert "backend offline" in caplog.text.lower() or "refused" in caplog.text
    assert not any(r.levelno >= logging.ERROR for r in caplog.records)
