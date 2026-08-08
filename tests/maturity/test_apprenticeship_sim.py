"""Apprenticeship multi-day SIM bridge + TTL telegram tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lumina_core.evolution.multi_day_sim_types import SimResult
from lumina_core.maturity.advance_policy import confirm_telegram_advance, reissue_telegram_advance
from lumina_core.maturity.apprenticeship_sim import run_apprenticeship_multi_day_sim
from lumina_core.maturity.continuum import (
    clear_expired_pending_advance,
    load_continuum,
    mark_phase_completed,
    pending_advance_expired,
    set_advance_mode,
    set_pending_advance,
)


def _finite_result(days: int = 3) -> SimResult:
    return SimResult(
        dna_hash="abc123",
        day_count=days,
        avg_pnl=25.0,
        max_drawdown_ratio=0.01,
        regime_fit_bonus=0.0,
        fitness=1.2,
        shadow_mode=False,
        hypothetical_fills=None,
    )


def _inf_result(days: int = 3) -> SimResult:
    return SimResult(
        dna_hash="bad",
        day_count=days,
        avg_pnl=100.0,
        max_drawdown_ratio=0.5,
        regime_fit_bonus=0.0,
        fitness=float("-inf"),
        shadow_mode=False,
        hypothetical_fills=None,
    )


@pytest.mark.unit
def test_multi_day_bridge_writes_sim_summaries(tmp_path: Path) -> None:
    with patch(
        "lumina_core.evolution.multi_day_sim_runner.MultiDaySimRunner.evaluate_variants",
        return_value=[_finite_result(3)],
    ):
        out = run_apprenticeship_multi_day_sim(tmp_path, days=3)

    assert out["ok"] is True
    assert out["days_written"] == 3
    runs = tmp_path / "state" / "test_runs"
    files = list(runs.glob("apprenticeship_sim_day_*.json"))
    assert len(files) == 3
    import json

    sample = json.loads(files[0].read_text(encoding="utf-8"))
    assert sample["mode"] == "sim"
    assert sample["source"] == "apprenticeship_multi_day_sim"


@pytest.mark.unit
def test_multi_day_hard_fail_writes_negative_days(tmp_path: Path) -> None:
    with patch(
        "lumina_core.evolution.multi_day_sim_runner.MultiDaySimRunner.evaluate_variants",
        return_value=[_inf_result(2)],
    ):
        out = run_apprenticeship_multi_day_sim(tmp_path, days=2)

    assert out["ok"] is True
    assert out["sim_result"]["fitness_is_inf"] is True
    assert all(d["pnl_realized"] < 0 for d in out["day_pnls"])


@pytest.mark.unit
def test_telegram_token_not_expired_confirms(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    set_advance_mode(tmp_path, "telegram")
    data = set_pending_advance(tmp_path, from_phase="birth", to_phase="awakening", ttl_sec=3600)
    pending = data["pending_advance"]
    assert pending.get("expires_at")
    assert pending_advance_expired(pending) is False
    ok = confirm_telegram_advance(tmp_path, token=str(pending["telegram_token"]))
    assert ok["ok"] is True
    assert ok["start_phase"] == "awakening"


@pytest.mark.unit
def test_telegram_token_expired_rejected(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    data = set_pending_advance(tmp_path, from_phase="birth", to_phase="awakening", ttl_sec=300)
    pending = dict(data["pending_advance"])
    # Force past expiry
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    continuum = load_continuum(tmp_path)
    continuum["pending_advance"] = {**pending, "expires_at": past}
    from lumina_core.maturity.continuum import save_continuum

    save_continuum(tmp_path, continuum)

    assert pending_advance_expired(continuum["pending_advance"]) is True
    bad = confirm_telegram_advance(tmp_path, token=str(pending["telegram_token"]))
    assert bad["ok"] is False
    assert bad["error"] == "token_expired"
    # Pending cleared
    assert load_continuum(tmp_path).get("pending_advance") is None


@pytest.mark.unit
def test_clear_expired_pending_advance(tmp_path: Path) -> None:
    data = set_pending_advance(tmp_path, from_phase="a", to_phase="b", ttl_sec=300)
    pending = dict(data["pending_advance"])
    continuum = load_continuum(tmp_path)
    continuum["pending_advance"] = {
        **pending,
        "expires_at": (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(),
    }
    from lumina_core.maturity.continuum import save_continuum

    save_continuum(tmp_path, continuum)
    result = clear_expired_pending_advance(tmp_path)
    assert result["cleared"] is True
    assert load_continuum(tmp_path).get("pending_advance") is None


@pytest.mark.unit
def test_reissue_telegram_advance(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    set_advance_mode(tmp_path, "telegram")
    with patch("lumina_core.maturity.advance_policy._notify_telegram_advance"):
        result = reissue_telegram_advance(tmp_path)
    assert result["ok"] is True
    assert result["to"] == "awakening"
    assert result["expires_at"]
    pending = load_continuum(tmp_path).get("pending_advance")
    assert isinstance(pending, dict)
    assert pending.get("telegram_token")


@pytest.mark.unit
def test_apprenticeship_runner_calls_multi_day_bridge(tmp_path: Path) -> None:
    from lumina_core.maturity.phase_runners.apprenticeship import run_apprenticeship

    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=[])

    cfg = MagicMock(
        apprenticeship_min_green_days=5,
        apprenticeship_sim_days=2,
        strict_exit_proofs=True,
        experimental_soft_complete=False,
        playground_require_first_order=True,
        proving_require_promotion_or_shadow=True,
        awakening_min_twin_samples=10,
        apprenticeship_sim_days_probe=0,
    )
    with patch(
        "lumina_core.maturity.maturation_progress.sync_stability_milestone",
    ), patch(
        "lumina_core.engine.sim_stability_checker.generate_stability_report",
        return_value={"READY_FOR_REAL": False, "consecutive_green_days": 0, "failures": ["positive_expectancy_5d"]},
    ), patch(
        "lumina_core.maturity.apprenticeship_sim.run_apprenticeship_multi_day_sim",
        return_value={"ok": True, "days_written": 2, "days_requested": 2},
    ) as bridge, patch(
        "lumina_core.maturity.phase_runners.apprenticeship.cfg",
        return_value=cfg,
    ), patch(
        "lumina_core.maturity.phase_runners.common.load_maturity_config",
        return_value=cfg,
    ), patch(
        "lumina_core.maturity.phase_specs.load_maturity_config",
        return_value=cfg,
    ):
        result = run_apprenticeship(tmp_path)

    assert bridge.called
    assert result["ok"] is False
    assert result.get("status") == "incomplete"
