"""Birth history preflight messaging must not push CROSSTRADE on ninjatrader path."""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_launcher.services.birth_runner_preflight import (
    _fabric_history_remediation,
    _resolve_live_provider_from_yaml,
    demote_stale_history_failure_progress,
)
from lumina_launcher.services.fabric_link_certificate import (
    BIRTH_FABRIC_LINK_MAX_AGE_HOURS,
    is_fabric_link_green,
    is_fabric_link_green_for_birth,
    write_certificate,
)


def test_fabric_remediation_never_mentions_crosstrade_token() -> None:
    msg = _fabric_history_remediation(instrument="MES SEP26", stale_msg="", connect_refused=True)
    assert "CROSSTRADE" not in msg.upper()
    assert "50051" in msg
    assert "NinjaTrader" in msg or "Fabric" in msg


def test_fabric_remediation_auth_failed_mentions_token() -> None:
    msg = _fabric_history_remediation(
        instrument="MES SEP26", stale_msg="", connect_refused=False, auth_failed=True
    )
    assert "CROSSTRADE" not in msg.upper()
    assert "token" in msg.lower() or "Token" in msg
    assert "herstart" in msg.lower() or "restart" in msg.lower() or "Repair" in msg


def test_resolve_live_provider_from_workspace_config(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "broker:\n  live_provider: ninjatrader\n  ninjatrader:\n    enabled: true\n",
        encoding="utf-8",
    )
    assert _resolve_live_provider_from_yaml(tmp_path) == "ninjatrader"


def test_demote_skips_fresh_auth_failure(tmp_path: Path) -> None:
    """Fresh AUTH/token diagnostics must not be rewritten to 'Vorige birth-run'."""
    from datetime import datetime, timezone

    (tmp_path / "config.yaml").write_text(
        "broker:\n  live_provider: ninjatrader\n",
        encoding="utf-8",
    )
    live_msg = (
        "Fabric host draait, maar Brain-authenticatie faalt (token mismatch). "
        "Repair connection + herstart NT."
    )
    prog = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": "error",
        "phase": "loading_history_failed",
        "message": live_msg,
        "last_error": live_msg,
        "attention_reason_code": "history_unavailable",
    }
    pf = tmp_path / "state" / "lumina_birth_progress.json"
    pf.parent.mkdir(parents=True)
    pf.write_text(json.dumps(prog), encoding="utf-8")
    svc = SimpleNamespace(
        workspace_root=tmp_path,
        progress_file=pf,
        is_running=lambda: False,
        _load_progress=lambda: json.loads(pf.read_text(encoding="utf-8")),
    )
    assert demote_stale_history_failure_progress(svc) is False
    out = json.loads(pf.read_text(encoding="utf-8"))
    assert "token mismatch" in out["message"].lower() or "authenticatie" in out["message"].lower()
    assert "Vorige birth-run" not in out["message"]


def test_demote_rewrites_crosstrade_residual(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "broker:\n  live_provider: ninjatrader\n",
        encoding="utf-8",
    )
    prog = {
        "stage": "error",
        "phase": "loading_history_failed",
        "message": "Geen historische... CROSSTRADE_TOKEN ...",
        "last_error": "Geen historische... CROSSTRADE_TOKEN ...",
        "attention_reason_code": "history_unavailable",
    }
    pf = tmp_path / "state" / "lumina_birth_progress.json"
    pf.parent.mkdir(parents=True)
    pf.write_text(json.dumps(prog), encoding="utf-8")
    svc = SimpleNamespace(
        workspace_root=tmp_path,
        progress_file=pf,
        is_running=lambda: False,
        _load_progress=lambda: json.loads(pf.read_text(encoding="utf-8")),
    )
    assert demote_stale_history_failure_progress(svc) is True
    out = json.loads(pf.read_text(encoding="utf-8"))
    assert "CROSSTRADE" not in out["message"].upper()
    assert out.get("residual_failure") is True


def test_stale_fabric_cert_not_green_for_birth(tmp_path: Path) -> None:
    """Birth gate rejects paper-only / host-down; vault paper helper may still pass."""
    write_certificate(
        overall="green",
        target="127.0.0.1:50051",
        token="tok",
        workspace_root=tmp_path,
    )
    cert_path = tmp_path / "state" / "fabric_link_certificate.json"
    payload = json.loads(cert_path.read_text(encoding="utf-8"))
    # Older than birth max age, younger than 14-day vault window.
    payload["ts_unix"] = time.time() - (BIRTH_FABRIC_LINK_MAX_AGE_HOURS + 1.0) * 3600
    cert_path.write_text(json.dumps(payload), encoding="utf-8")

    # Birth SSOT requires live host + proof — paper cert alone is never enough.
    ok_birth, reason = is_fabric_link_green_for_birth(workspace_root=tmp_path)
    assert ok_birth is False
    assert reason in {
        "FABRIC_HOST_DOWN",
        "FABRIC_LINK_STALE",
        "FABRIC_LINK_NOT_GREEN",
    }

    ok_vault, _ = is_fabric_link_green(workspace_root=tmp_path, max_age_hours=24.0 * 14)
    assert ok_vault is True


def test_start_rejects_when_history_preflight_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_launcher.services import birth_runner_start as start_mod

    (tmp_path / "config.yaml").write_text(
        "broker:\n  live_provider: ninjatrader\nfirst_boot:\n  training_trades: 25000\n  max_real_days: 365\n",
        encoding="utf-8",
    )
    (tmp_path / "state").mkdir(parents=True)

    def _fail_preflight(svc: object, days: int) -> tuple[bool, str]:
        return False, "Fabric connect failed for historical data"

    monkeypatch.setattr(start_mod, "preflight_historical_data", _fail_preflight)
    monkeypatch.setattr(start_mod, "launcher_setup_status", lambda _svc: {"ok": True})
    monkeypatch.setattr(start_mod, "adaptive_intelligence_status", lambda _svc: {"tier": "light"})

    thread_started = {"n": 0}

    class _FakeThread:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def start(self) -> None:
            thread_started["n"] += 1

    monkeypatch.setattr(start_mod.threading, "Thread", _FakeThread)

    svc = SimpleNamespace(
        workspace_root=tmp_path,
        is_running=lambda: False,
        is_completed=lambda: False,
        pause_flag_path=tmp_path / "state" / "pause.flag",
        _stop_requested=MagicMock(),
        _result=None,
        _error=None,
        _start_time=None,
        _stalled_auto_resume_attempted=False,
        _thread=None,
    )
    svc._stop_requested.clear = MagicMock()

    result = start_mod.start_birth(
        svc,
        target_trades=25000,
        force=True,
        practice_mode=False,
        explicit_user_start=True,
        continue_training=False,
        reuse_data=False,
    )
    assert result["status"] == "history_unavailable"
    assert "Fabric" in str(result.get("message") or "")
    assert thread_started["n"] == 0
    assert svc._thread is None
    prog = json.loads((tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8"))
    assert prog["phase"] == "loading_history_failed"
    assert prog["stage"] == "error"


def test_preflight_invalidates_cert_on_empty_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lumina_launcher.services import birth_runner_preflight as pf

    (tmp_path / "config.yaml").write_text(
        "broker:\n  live_provider: ninjatrader\n",
        encoding="utf-8",
    )
    write_certificate(
        overall="green",
        target="127.0.0.1:50051",
        token="tok",
        workspace_root=tmp_path,
    )
    cert = tmp_path / "state" / "fabric_link_certificate.json"
    assert cert.is_file()

    class _EmptyMds:
        def load_historical_ohlc_extended(self, **_kwargs: object) -> list:
            return []

    class _Container:
        config = SimpleNamespace(broker_live_provider="ninjatrader", instrument="MES SEP26")
        market_data_service = _EmptyMds()

    monkeypatch.setattr(pf, "ApplicationContainer", lambda: _Container())
    monkeypatch.setattr(pf, "_bind_headless_runtime_app", lambda _c: None)
    monkeypatch.setattr(pf.time, "sleep", lambda _s: None)

    svc = SimpleNamespace(workspace_root=tmp_path)
    ok, msg = pf.preflight_historical_data(svc, 56)
    assert ok is False
    assert "Fabric" in msg or "NinjaTrader" in msg
    assert not cert.is_file()