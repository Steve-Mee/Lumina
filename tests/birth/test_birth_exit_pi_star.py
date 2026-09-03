"""GATE 0: π* is a first-class Birth artifact. No silent complete. No ppo fallback."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.birth_exit_policy_export import (
    BirthPiStarExportError,
    candidate_frozen_paths,
    export_birth_exit_pi_star,
    is_gitignored_ppo_zip,
    load_frozen_policy,
    resolve_frozen_policy_path,
    resolve_pi_star_path,
    seal_harvested_pi_star,
)
from lumina_core.birth.foundation_complete import complete_foundation_birth
from tests.birth.test_foundation_loopholes import _v2_receipt


def _save_weights(path: str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"PK\x03\x04pi_star_bytes")
    return str(target)


def _host(tmp_path: Path, *, trainer: object) -> SimpleNamespace:
    receipts = [
        _v2_receipt("stage1_trend", occupancy=None),
        _v2_receipt("stage2_range"),
        _v2_receipt("stage3_mixed"),
        _v2_receipt("stage4_viable_plant"),
        _v2_receipt("stage5_probe_handoff", oos_sharpe=-1.25),
    ]

    class _Buf:
        def __len__(self) -> int:
            return 0

    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        _stage_pass_receipts=receipts,
        cumulative_trades=900,
        workspace_root=tmp_path,
        birth_config=SimpleNamespace(curriculum=SimpleNamespace(polish_ppo_timesteps=100)),
        buffer=_Buf(),
        ppo_trainer=trainer,
        practice_policy_path=tmp_path / "practice.pt",
        final_policy_path=tmp_path / "final.pt",
        practice_completed_flag_path=tmp_path / "state" / "practice.flag",
        completion_flag_path=tmp_path / "state" / "lumina_birth_completed.flag",
        ppo_steps=0,
        _real_data_pct=1.0,
        birth_start_time=0.0,
    )


def test_export_raises_without_save_hook(tmp_path: Path) -> None:
    host = SimpleNamespace(ppo_trainer=SimpleNamespace(), workspace_root=tmp_path)
    with pytest.raises(BirthPiStarExportError, match="no_save_hook"):
        export_birth_exit_pi_star(host)


def test_export_raises_when_save_writes_nothing(tmp_path: Path) -> None:
    host = SimpleNamespace(
        ppo_trainer=SimpleNamespace(save_weights=lambda _p: str(_p)),
        workspace_root=tmp_path,
    )
    with pytest.raises(BirthPiStarExportError, match="export_missing"):
        export_birth_exit_pi_star(host)


def test_complete_fails_closed_without_zip(tmp_path: Path) -> None:
    host = _host(
        tmp_path,
        trainer=SimpleNamespace(
            final_birth_polish=lambda _b: None,
            save_final_birth_policy=lambda _p: None,
        ),
    )
    out = complete_foundation_birth(
        host, training_mode="certified", trade_budget_cap=1000, practice_mode=False
    )
    assert out["status"] == "foundation_incomplete"
    assert out["failure_reason"] == "pi_star_export_failed"
    assert not host.completion_flag_path.is_file()
    dest = resolve_pi_star_path(tmp_path)
    assert not dest.is_file()


def test_complete_requires_zip_then_succeeds(tmp_path: Path) -> None:
    host = _host(
        tmp_path,
        trainer=SimpleNamespace(
            final_birth_polish=lambda _b: None,
            save_final_birth_policy=lambda _p: None,
            save_weights=_save_weights,
        ),
    )
    out = complete_foundation_birth(
        host, training_mode="certified", trade_budget_cap=1000, practice_mode=False
    )
    assert out["status"] == "completed"
    dest = resolve_pi_star_path(tmp_path)
    assert dest.is_file()
    assert dest.stat().st_size > 0
    assert host.completion_flag_path.is_file()


def test_grind_candidates_never_include_ppo(tmp_path: Path) -> None:
    ppo = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    ppo.parent.mkdir(parents=True)
    ppo.write_bytes(b"PK\x03\x04decoy")
    assert is_gitignored_ppo_zip(ppo) is True
    assert resolve_frozen_policy_path(tmp_path) is None
    assert load_frozen_policy(ppo) is None
    names = [p.name for p in candidate_frozen_paths(tmp_path)]
    assert names == ["birth_exit_pi_star.zip"]


def test_seal_refuses_gitignored_ppo(tmp_path: Path) -> None:
    ppo = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    ppo.parent.mkdir(parents=True)
    ppo.write_bytes(b"PK\x03\x04decoy")
    dest = tmp_path / "reports" / "birth_cloud_run" / "artifacts" / "birth_exit_pi_star.zip"
    with pytest.raises(BirthPiStarExportError, match="post-polish"):
        seal_harvested_pi_star(ppo, dest)
    assert not dest.is_file()


def test_seal_copies_pi_star_only(tmp_path: Path) -> None:
    src = tmp_path / "harvest" / "birth_exit_pi_star.zip"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"PK\x03\x04harvested")
    dest = tmp_path / "reports" / "birth_cloud_run" / "artifacts" / "birth_exit_pi_star.zip"
    sealed = seal_harvested_pi_star(src, dest, extra={"harvest_workspace": str(tmp_path / "harvest")})
    assert sealed == dest
    assert dest.read_bytes() == src.read_bytes()
    sidecar = dest.with_name("birth_exit_pi_star.json")
    assert sidecar.is_file()
    assert "harvest_s5_pass_pre_polish" in sidecar.read_text(encoding="utf-8")


def test_complete_does_not_warn_and_continue_without_zip() -> None:
    complete = Path("lumina_core/birth/foundation_complete.py").read_text(encoding="utf-8")
    assert complete.index("export_birth_exit_pi_star") < complete.index("final_birth_polish")
    assert 'logger.warning("birth.foundation.pi_star_export_failed' not in complete
    assert 'failure_reason": "pi_star_export_failed"' in complete
    export = Path("lumina_core/birth/birth_exit_policy_export.py").read_text(encoding="utf-8")
    assert "out.append(root / \"lumina_agents\" / \"ppo\"" not in export
    assert "Never post-polish PPO" in export
