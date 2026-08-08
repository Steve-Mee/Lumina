"""Birth status polling must stay lightweight during active data prep."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from lumina_core.birth.progress import write_birth_progress
from lumina_launcher.services.birth_service import BirthService

birth_service_module = importlib.import_module("lumina_launcher.services.birth_service")
birth_status_enricher_module = importlib.import_module(
    "lumina_launcher.services.birth_status_enricher"
)


@pytest.mark.unit
def test_get_status_skips_launcher_setup_during_enriching_regimes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    launcher_calls: list[Path | str | None] = []

    def _tracked_launcher(workspace_root: Path | str | None = None, **_kwargs: object) -> dict[str, object]:
        launcher_calls.append(workspace_root)
        return {"setup_complete": True, "intelligence_stack_ready": True}

    monkeypatch.setattr(
        birth_status_enricher_module,
        "launcher_setup_status_payload",
        _tracked_launcher,
    )
    monkeypatch.setattr(svc, "is_running", lambda: True)
    monkeypatch.setattr(
        svc,
        "_load_progress",
        lambda: {
            "stage": "loading_data",
            "phase": "enriching_regimes",
            "progress_pct": 22.0,
            "message": "Regime map bouwen: 2000/8000 ticks",
        },
    )
    monkeypatch.setattr(
        svc,
        "_adaptive_intelligence_status",
        lambda **_: {"tier": "light", "mode": "auto"},
    )

    status = svc.get_status()

    assert status["status"] == "running"
    assert launcher_calls == []
    assert status["launcher_setup"] == {}
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_get_status_uses_cached_launcher_setup_when_not_lightweight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    BirthService._instance = None  # type: ignore[attr-defined]
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    launcher_calls = 0

    def _tracked_launcher(workspace_root: Path | str | None = None, **_kwargs: object) -> dict[str, object]:
        nonlocal launcher_calls
        launcher_calls += 1
        return {"setup_complete": True, "intelligence_stack_ready": True, "call": launcher_calls}

    monkeypatch.setattr(
        birth_status_enricher_module,
        "launcher_setup_status_payload",
        _tracked_launcher,
    )
    monkeypatch.setattr(svc, "is_running", lambda: False)
    monkeypatch.setattr(
        svc,
        "_load_progress",
        lambda: {"stage": "not_started", "phase": "idle", "progress_pct": 0},
    )
    monkeypatch.setattr(
        svc,
        "_adaptive_intelligence_status",
        lambda **_: {"tier": "light", "mode": "auto"},
    )

    first = svc.get_status()
    second = svc.get_status()

    assert launcher_calls == 1
    assert first["launcher_setup"]["call"] == 1
    assert second["launcher_setup"]["call"] == 1
    BirthService._instance = None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_enrich_status_uses_artifact_cache_during_active_birth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lumina_os.backend import birth_endpoints
    from lumina_os.backend import birth_endpoints_enrich as enrich

    enrich._ENRICH_ARTIFACT_CACHE = None
    birth_endpoints._ENRICH_ARTIFACT_CACHE = None
    validate_calls = 0

    def _tracked_validate(*_args: object, **_kwargs: object) -> tuple[bool, str, None]:
        nonlocal validate_calls
        validate_calls += 1
        return False, "missing_or_invalid_certificate", None

    # M5: enrich implementation lives in birth_endpoints_enrich.
    monkeypatch.setattr(enrich.birth_service, "workspace_root", tmp_path)
    monkeypatch.setattr(enrich, "validate_certificate_artifacts", _tracked_validate)
    monkeypatch.setattr(enrich, "load_checkpoint_state", lambda _root: {})
    monkeypatch.setattr(enrich.birth_service, "artifacts_ok", lambda: False)
    monkeypatch.setattr(enrich.birth_service, "evolution_proof_ok", lambda: False)
    monkeypatch.setattr(enrich.birth_service, "real_trading_eligible", lambda: False)
    monkeypatch.setattr(
        enrich,
        "should_fast_path_remediation_from_state",
        lambda *_args, **_kwargs: False,
    )

    payload = {
        "status": "running",
        "progress": {"stage": "loading_data", "phase": "enriching_regimes"},
    }
    first = enrich._enrich_status(dict(payload))
    second = enrich._enrich_status(dict(payload))

    assert validate_calls == 1
    assert first["certificate_ok"] is False
    assert second["certificate_ok"] is False
    enrich._ENRICH_ARTIFACT_CACHE = None
    birth_endpoints._ENRICH_ARTIFACT_CACHE = None


@pytest.mark.unit
def test_write_birth_progress_uses_atomic_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    replaced: list[tuple[str, str]] = []

    def _tracked_replace(src: str | Path, dst: str | Path) -> None:
        replaced.append((str(src), str(dst)))

    monkeypatch.setattr("lumina_core.birth.progress.os.replace", _tracked_replace)
    write_birth_progress(
        tmp_path,
        stage="loading_data",
        phase="enriching_regimes",
        message="Regime map bouwen: 2000/8000 ticks",
        progress_pct=22.0,
    )
    assert replaced
    assert replaced[0][0].endswith("lumina_birth_progress.json.tmp")
    assert replaced[0][1].endswith("lumina_birth_progress.json")
