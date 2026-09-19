"""Apprenticeship multi-day SIM bridge + TTL telegram tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

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


@pytest.mark.unit
def test_multi_day_bridge_refuses_backtest_days(tmp_path: Path) -> None:
    out = run_apprenticeship_multi_day_sim(tmp_path, days=3)
    assert out["ok"] is False
    assert out["reason"] == "backtest_is_not_a_session_day"
    assert out["days_written"] == 0
    runs = tmp_path / "state" / "test_runs"
    assert list(runs.glob("apprenticeship_sim_day_*.json")) == [] if runs.exists() else True


@pytest.mark.unit
def test_multi_day_hard_fail_writes_nothing(tmp_path: Path) -> None:
    out = run_apprenticeship_multi_day_sim(tmp_path, days=2)
    assert out["ok"] is False
    assert out["days_written"] == 0


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
def test_apprenticeship_runner_does_not_call_multi_day_bridge(tmp_path: Path) -> None:
    from lumina_core.maturity.phase_runners.apprenticeship import run_apprenticeship

    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=[])

    with patch(
        "lumina_core.maturity.apprenticeship_sim.run_apprenticeship_multi_day_sim",
    ) as bridge:
        result = run_apprenticeship(tmp_path, should_stop=lambda: True)

    assert bridge.called is False
    assert result["ok"] is False
    assert result.get("status") == "incomplete"
