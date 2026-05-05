from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.engine import runtime_entrypoint
from lumina_core.first_boot_ui import normalize_first_boot_training_trades
from lumina_core.infinite_simulator import InfiniteSimulator


def _mk_tick(price: float = 5000.0) -> dict[str, Any]:
    return {
        "timestamp": "2026-01-01T00:00:00Z",
        "last": price,
        "bid": price - 0.125,
        "ask": price + 0.125,
        "volume": 1000,
    }


@pytest.mark.unit
def test_runtime_first_boot_failure_blocks_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime_entrypoint, "_first_boot_needed", lambda: True)
    monkeypatch.setattr(runtime_entrypoint, "_run_first_boot_training", lambda: 1)
    called: list[bool] = []
    monkeypatch.setattr(runtime_entrypoint, "_run_real_runtime", lambda **_kwargs: called.append(True) or 0)
    rc = runtime_entrypoint.run_with_mode("auto", argv=["--mode", "real"])
    assert rc == 1
    assert called == []


@pytest.mark.unit
def test_runtime_first_boot_success_continues_to_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime_entrypoint, "_first_boot_needed", lambda: True)
    monkeypatch.setattr(runtime_entrypoint, "_run_first_boot_training", lambda: 0)
    called: list[bool] = []
    monkeypatch.setattr(runtime_entrypoint, "_run_real_runtime", lambda **_kwargs: called.append(True) or 0)
    rc = runtime_entrypoint.run_with_mode("auto", argv=["--mode", "real"])
    assert rc == 0
    assert called == [True]


@pytest.mark.unit
def test_runtime_skips_first_boot_when_artifacts_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime_entrypoint, "_first_boot_needed", lambda: False)
    called_first_boot: list[bool] = []
    monkeypatch.setattr(
        runtime_entrypoint,
        "_run_first_boot_training",
        lambda: called_first_boot.append(True) or 0,
    )
    monkeypatch.setattr(runtime_entrypoint, "_run_real_runtime", lambda **_kwargs: 0)
    rc = runtime_entrypoint.run_with_mode("auto", argv=["--mode", "real"])
    assert rc == 0
    assert called_first_boot == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("force_training", "flag_exists", "policy_exists", "expected"),
    [
        (True, False, False, True),
        (True, True, False, True),
        (True, False, True, True),
        (True, True, True, False),
        (False, False, False, False),
        (False, True, False, False),
        (False, False, True, False),
        (False, True, True, False),
    ],
)
def test_first_boot_needed_respects_force_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    force_training: bool,
    flag_exists: bool,
    policy_exists: bool,
    expected: bool,
) -> None:
    flag_path = tmp_path / "state" / "first_boot_completed.flag"
    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    monkeypatch.setattr(runtime_entrypoint, "FIRST_BOOT_FLAG_PATH", flag_path)
    monkeypatch.setattr(runtime_entrypoint, "FIRST_BOOT_POLICY_PATH", policy_path)
    monkeypatch.setattr(
        runtime_entrypoint,
        "_load_first_boot_config",
        lambda: {
            "training_trades": 500_000,
            "prefer_real_data_only": True,
            "max_real_days": 90,
            "allow_minimal_synthetic_fallback": False,
            "force_training": force_training,
        },
    )
    if flag_exists:
        flag_path.parent.mkdir(parents=True, exist_ok=True)
        flag_path.write_text("ok", encoding="utf-8")
    if policy_exists:
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text("ok", encoding="utf-8")
    assert runtime_entrypoint._first_boot_needed() is expected


@pytest.mark.unit
def test_runtime_load_first_boot_config_snaps_to_shared_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        runtime_entrypoint.ConfigLoader,
        "section",
        staticmethod(lambda *args, **kwargs: {"training_trades": 155_000, "max_real_days": 5}),
    )
    cfg = runtime_entrypoint._load_first_boot_config()
    assert cfg["training_trades"] == normalize_first_boot_training_trades(155_000) == 200_000
    assert cfg["max_real_days"] == 30
    assert cfg["force_training"] is True


@pytest.mark.unit
def test_runtime_first_boot_writes_flag_on_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    flag_path = tmp_path / "state" / "first_boot_completed.flag"
    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    progress_path = tmp_path / "state" / "first_boot_progress.json"
    monkeypatch.setattr(runtime_entrypoint, "FIRST_BOOT_FLAG_PATH", flag_path)
    monkeypatch.setattr(runtime_entrypoint, "FIRST_BOOT_POLICY_PATH", policy_path)
    monkeypatch.setattr(runtime_entrypoint, "FIRST_BOOT_PROGRESS_PATH", progress_path)
    monkeypatch.setattr(
        runtime_entrypoint,
        "_load_first_boot_config",
        lambda: {
            "training_trades": 100_000,
            "prefer_real_data_only": True,
            "max_real_days": 365,
            "allow_minimal_synthetic_fallback": False,
        },
    )

    class _FakeContainer:
        def __init__(self) -> None:
            self.infinite_simulator = SimpleNamespace(
                run_first_boot_training=lambda **_kwargs: {"status": "ok_real_only", "trades": 100_000}
            )

    monkeypatch.setattr(runtime_entrypoint, "ApplicationContainer", _FakeContainer)
    rc = runtime_entrypoint._run_first_boot_training()
    assert rc == 0
    assert flag_path.exists()
    assert progress_path.exists()
    assert '"stage": "completed"' in progress_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_runtime_first_boot_success_message_mentions_synthetic_when_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    flag_path = tmp_path / "state" / "first_boot_completed.flag"
    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    progress_path = tmp_path / "state" / "first_boot_progress.json"
    monkeypatch.setattr(runtime_entrypoint, "FIRST_BOOT_FLAG_PATH", flag_path)
    monkeypatch.setattr(runtime_entrypoint, "FIRST_BOOT_POLICY_PATH", policy_path)
    monkeypatch.setattr(runtime_entrypoint, "FIRST_BOOT_PROGRESS_PATH", progress_path)
    monkeypatch.setattr(
        runtime_entrypoint,
        "_load_first_boot_config",
        lambda: {
            "training_trades": 100_000,
            "prefer_real_data_only": True,
            "max_real_days": 365,
            "allow_minimal_synthetic_fallback": True,
        },
    )

    class _FakeContainer:
        def __init__(self) -> None:
            self.infinite_simulator = SimpleNamespace(
                run_first_boot_training=lambda **_kwargs: {
                    "status": "ok_minimal_synthetic_fallback",
                    "trades": 100_000,
                    "synthetic_ticks": 12_000,
                }
            )

    monkeypatch.setattr(runtime_entrypoint, "ApplicationContainer", _FakeContainer)
    rc = runtime_entrypoint._run_first_boot_training()
    out = capsys.readouterr().out
    assert rc == 0
    assert "Eerste keer starten gedetecteerd. Lumina voert nu haar initiële leer-cyclus uit..." in out
    assert "synthetische aanvulling" in out


@pytest.mark.unit
def test_infinite_simulator_first_boot_caps_trades_for_real_only(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = SimpleNamespace(load_historical_ohlc_extended=lambda **_kwargs: [_mk_tick() for _ in range(5000)])
    runtime = SimpleNamespace(engine=SimpleNamespace(config=SimpleNamespace(instrument="MES JUN26")), INSTRUMENT="MES JUN26")
    sim = InfiniteSimulator(runtime=runtime, market_data_service=svc, ppo_trainer=None, workers=1)
    monkeypatch.setattr(
        InfiniteSimulator,
        "_run_parallel_simulation",
        lambda self, _ticks, total_target: {
            "trades": total_target,
            "winrate": 0.5,
            "net_pnl": 10.0,
            "mean_worker_sharpe": 1.0,
        },
    )

    report = sim.run_first_boot_training(
        target_trades=300_000,
        prefer_real_data_only=True,
        max_real_days=100,
        allow_minimal_synthetic_fallback=False,
    )
    assert report["status"] == "ok_capped_real_only"
    assert report["target_trades"] == 10_000
    assert report["actual_real_trade_capacity"] == 10_000
    assert report["synthetic_ticks"] == 0
    assert report["executed_trades"] == 10_000
    assert report["real_days_loaded"] >= 1
    assert float(report["synthetic_ratio"]) == 0.0


@pytest.mark.unit
def test_infinite_simulator_first_boot_can_use_minimal_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = SimpleNamespace(load_historical_ohlc_extended=lambda **_kwargs: [_mk_tick() for _ in range(5000)])
    runtime = SimpleNamespace(engine=SimpleNamespace(config=SimpleNamespace(instrument="MES JUN26")), INSTRUMENT="MES JUN26")
    sim = InfiniteSimulator(runtime=runtime, market_data_service=svc, ppo_trainer=None, workers=1)
    monkeypatch.setattr(
        InfiniteSimulator,
        "_run_parallel_simulation",
        lambda self, _ticks, total_target: {
            "trades": total_target,
            "winrate": 0.5,
            "net_pnl": 10.0,
            "mean_worker_sharpe": 1.0,
        },
    )

    report = sim.run_first_boot_training(
        target_trades=300_000,
        prefer_real_data_only=True,
        max_real_days=100,
        allow_minimal_synthetic_fallback=True,
    )
    assert report["status"] == "ok_minimal_synthetic_fallback"
    assert report["target_trades"] == 300_000
    assert int(report["synthetic_ticks"]) > 0
    assert float(report["synthetic_ratio"]) > 0.0
    assert report["executed_trades"] == 300_000


@pytest.mark.unit
def test_infinite_simulator_first_boot_fail_closed_on_no_real_data() -> None:
    svc = SimpleNamespace(load_historical_ohlc_extended=lambda **_kwargs: [])
    runtime = SimpleNamespace(engine=SimpleNamespace(config=SimpleNamespace(instrument="MES JUN26")), INSTRUMENT="MES JUN26")
    sim = InfiniteSimulator(runtime=runtime, market_data_service=svc, ppo_trainer=None, workers=1)
    report = sim.run_first_boot_training(
        target_trades=100_000,
        prefer_real_data_only=True,
        max_real_days=90,
        allow_minimal_synthetic_fallback=False,
    )
    assert report["status"] == "blocked_no_real_data"
    assert report["trades"] == 0
    assert report["executed_trades"] == 0
    assert float(report["synthetic_ratio"]) == 0.0


@pytest.mark.unit
def test_infinite_simulator_first_boot_allows_flexible_data_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    svc = SimpleNamespace(load_historical_ohlc_extended=lambda **_kwargs: [_mk_tick() for _ in range(5000)])
    runtime = SimpleNamespace(engine=SimpleNamespace(config=SimpleNamespace(instrument="MES JUN26")), INSTRUMENT="MES JUN26")
    sim = InfiniteSimulator(runtime=runtime, market_data_service=svc, ppo_trainer=None, workers=1)
    monkeypatch.setattr(
        InfiniteSimulator,
        "_run_parallel_simulation",
        lambda self, _ticks, total_target: {
            "trades": total_target,
            "winrate": 0.55,
            "net_pnl": 12.0,
            "mean_worker_sharpe": 1.2,
        },
    )
    report = sim.run_first_boot_training(
        target_trades=500_000,
        prefer_real_data_only=False,
        max_real_days=90,
        allow_minimal_synthetic_fallback=False,
    )
    assert report["status"] == "ok_flexible_data_policy"
    assert report["target_trades"] == 500_000
    assert report["executed_trades"] == 500_000
