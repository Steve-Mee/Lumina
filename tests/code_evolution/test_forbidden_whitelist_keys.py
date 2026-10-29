from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.code_evolution.operators import FORBIDDEN_PARAMETER_KEYS, validate_parameter_tweak

REQUIRED = (
    "live_release",
    "sim_account_whitelist",
    "account_name",
    "RealAccountName",
    "research_execution_mode",
    "mode",
    "trade_mode",
)


@pytest.mark.unit
def test_forbidden_parameter_keys_include_s1_names() -> None:
    for key in REQUIRED:
        assert key in FORBIDDEN_PARAMETER_KEYS
        assert "forbidden_parameter_key" in validate_parameter_tweak(key, 0.0, 1.0)


@pytest.mark.unit
def test_sandboxed_worker_copy_matches_operator_keys() -> None:
    source = Path("lumina_core/safety/sandboxed_code_worker.py").read_text(encoding="utf-8")
    for key in REQUIRED:
        assert f'"{key}"' in source or f"'{key}'" in source
