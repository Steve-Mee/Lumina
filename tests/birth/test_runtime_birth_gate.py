"""SIM runtime uses Birth foundation exit. REAL still requires the certificate."""
from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.runtime_bootstrap import _assert_runtime_birth_gate


@pytest.mark.unit
def test_sim_runtime_opens_on_foundation_exit_without_certificate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "lumina_core.maturity.birth_exit.is_birth_exit_sufficient",
        lambda _root: True,
    )
    monkeypatch.setattr(
        "lumina_core.runtime_bootstrap.validate_certificate_artifacts",
        lambda *_a, **_k: (False, "missing_or_invalid_certificate", None),
    )
    _assert_runtime_birth_gate(tmp_path, trade_mode="sim")


@pytest.mark.unit
def test_sim_runtime_stays_closed_without_foundation_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "lumina_core.maturity.birth_exit.is_birth_exit_sufficient",
        lambda _root: False,
    )
    with pytest.raises(RuntimeError, match="ADR-0046"):
        _assert_runtime_birth_gate(tmp_path, trade_mode="SIM")


@pytest.mark.unit
def test_real_runtime_still_requires_the_certificate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "lumina_core.maturity.birth_exit.is_birth_exit_sufficient",
        lambda _root: True,
    )
    monkeypatch.setattr(
        "lumina_core.runtime_bootstrap.validate_certificate_artifacts",
        lambda *_a, **_k: (False, "missing_or_invalid_certificate", None),
    )
    with pytest.raises(RuntimeError, match="certificate"):
        _assert_runtime_birth_gate(tmp_path, trade_mode="real")
