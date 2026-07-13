"""Tests for production headless runtime modules."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lumina_core.runtime.daemon_registry import RuntimeDaemonRegistry
from lumina_core.runtime.headless_telemetry import HeadlessTelemetry
from lumina_core.runtime.never_stop_recovery import NeverStopRecovery
from lumina_core.runtime.runtime_preflight import (
    RuntimePreflightReport,
    merge_preflight_reports,
    run_preflight_early,
)
from lumina_core.runtime.runtime_reconciliation_loop import RuntimeReconciliationLoop
from lumina_core.runtime.runtime_slo_monitor import RuntimeSloMonitor
from lumina_core.runtime.safe_restart_policy import SafeRestartPolicy


@pytest.fixture(autouse=True)
def _reset_daemon_registry() -> None:
    RuntimeDaemonRegistry.reset()
    yield
    RuntimeDaemonRegistry.reset()


class TestRuntimePreflight:
    def test_early_preflight_fails_without_birth_certificate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "lumina_core.runtime.runtime_preflight._check_birth_certificate",
            lambda *, required: (False, "birth_certificate:missing"),
        )
        monkeypatch.setattr(
            "lumina_core.runtime.runtime_preflight._check_config_startup",
            lambda: (True, None),
        )
        report = run_preflight_early(mode="sim", prod_cfg={"preflight": {"require_birth_certificate": True}})
        assert report.ok is False
        assert "birth_certificate:missing" in report.failure_reasons

    def test_merge_preflight_reports_combines_failures(self) -> None:
        a = RuntimePreflightReport(ok=False, mode="sim", failure_reasons=("a",))
        b = RuntimePreflightReport(ok=False, mode="sim", failure_reasons=("b",))
        merged = merge_preflight_reports(a, b)
        assert merged.ok is False
        assert merged.failure_reasons == ("a", "b")


class TestSafeRestartPolicy:
    def _container(self, *, open_position: bool = False) -> SimpleNamespace:
        pos = SimpleNamespace(live_qty=1 if open_position else 0, sim_qty=0, paper_qty=0)
        engine = SimpleNamespace(position_state=pos, save_state=MagicMock())
        broker = SimpleNamespace(get_positions=lambda: [{"qty": 1}] if open_position else [])
        return SimpleNamespace(engine=engine, broker=broker)

    def test_real_blocks_restart_with_open_position(self) -> None:
        policy = SafeRestartPolicy(mode="real")
        decision = policy.evaluate_process_restart(self._container(open_position=True))
        assert decision.allowed is False
        assert "open_positions" in decision.reasons

    def test_sim_allows_restart_when_flat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "lumina_core.runtime.safe_restart_policy._check_reconciler",
            lambda *, status_path: (True, None),
        )
        policy = SafeRestartPolicy(mode="sim")
        decision = policy.evaluate_process_restart(self._container(open_position=False))
        assert decision.allowed is True

    def test_real_supervisor_in_process_restart_blocked(self) -> None:
        policy = SafeRestartPolicy(mode="real")
        assert policy.in_process_restart_allowed(daemon_name="supervisor-loop") is False
        assert policy.in_process_restart_allowed(daemon_name="trade-reconciler") is True

    def test_deferred_restart_tracks_age(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "lumina_core.runtime.safe_restart_policy._check_reconciler",
            lambda *, status_path: (True, None),
        )
        policy = SafeRestartPolicy(
            mode="real",
            prod_cfg={"deferred_restart_alert_s": 10, "slo": {"deferred_restart_max_s": 60}},
        )
        policy.request_process_restart("test")
        policy._restart_requested_at = time.time() - 20  # noqa: SLF001
        state = policy.evaluate_deferred_restart(self._container(open_position=True))
        assert state.should_alert is True
        assert state.age_s >= 20


class TestRuntimeSloMonitor:
    def test_detects_stale_supervisor_tick_legacy_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        monitoring = {"timestamp": "2000-01-01T00:00:00+00:00"}
        (state_dir / "runtime_monitoring.json").write_text(json.dumps(monitoring), encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        monitor = RuntimeSloMonitor(
            mode="sim",
            prod_cfg={"slo": {"supervisor_tick_stale_s": 10}},
            started_at=time.time() - 500,
        )
        evaluation = monitor.evaluate()
        assert evaluation.status in {"warn", "fail"}
        assert any("supervisor_tick_stale" in b for b in evaluation.breaches)

    def test_reads_monitoring_runtime_metrics_first(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        fresh = {"timestamp": "2099-01-01T00:00:00+00:00"}
        stale = {"timestamp": "2000-01-01T00:00:00+00:00"}
        (state_dir / "monitoring_runtime_metrics.json").write_text(json.dumps(fresh), encoding="utf-8")
        (state_dir / "runtime_monitoring.json").write_text(json.dumps(stale), encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        monitor = RuntimeSloMonitor(
            mode="sim",
            prod_cfg={"slo": {"supervisor_tick_stale_s": 120}},
            started_at=time.time() - 500,
        )
        evaluation = monitor.evaluate()
        assert not any("supervisor_tick_stale" in b for b in evaluation.breaches)

    def test_missing_supervisor_after_grace_is_warning_in_sim(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        monkeypatch.chdir(tmp_path)

        monitor = RuntimeSloMonitor(
            mode="sim",
            prod_cfg={"slo": {"startup_grace_s": 1}},
            started_at=time.time() - 10,
        )
        evaluation = monitor.evaluate()
        assert "supervisor_tick_missing" in evaluation.warnings


class TestRuntimeReconciliationLoop:
    def test_detects_position_drift_read_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        status = {"pending_count": 0, "timestamp": "2099-01-01T00:00:00+00:00"}
        (state_dir / "trade_reconciler_status.json").write_text(json.dumps(status), encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        engine = SimpleNamespace(
            live_position_qty=0,
            config=SimpleNamespace(instrument="MES"),
        )
        broker = SimpleNamespace(
            get_positions=lambda: [SimpleNamespace(symbol="MES", quantity=2)],
        )
        container = SimpleNamespace(engine=engine, broker=broker)
        policy = SafeRestartPolicy(mode="real")
        loop = RuntimeReconciliationLoop(mode="real", container=container, restart_policy=policy)

        result = loop.evaluate()
        assert not result.ok
        assert any("position_drift" in issue for issue in result.issues)

    def test_persists_reconciliation_report(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        monkeypatch.chdir(tmp_path)

        container = SimpleNamespace(engine=SimpleNamespace(live_position_qty=0, config=SimpleNamespace(instrument="MES")), broker=None)
        policy = SafeRestartPolicy(mode="sim")
        loop = RuntimeReconciliationLoop(mode="sim", container=container, restart_policy=policy)
        loop.tick()
        report_path = tmp_path / "state" / "runtime_reconciliation_report.json"
        assert report_path.exists()


class TestHeadlessTelemetry:
    def test_record_uptime_tick_sets_gauge(self) -> None:
        collector = MagicMock()
        obs = SimpleNamespace(collector=collector)
        container = SimpleNamespace(observability_service=obs)
        telemetry = HeadlessTelemetry(mode="sim", container=container, started_at=time.time() - 30)
        telemetry.record_uptime_tick()
        collector.set.assert_called()
        collector.inc.assert_called()

    def test_smoke_summary_includes_alert_count(self) -> None:
        telemetry = HeadlessTelemetry(mode="sim")
        telemetry.alert("test", alert_type="test")
        summary = telemetry.smoke_summary()
        assert summary["alert_count"] == 1
        assert summary["mode"] == "sim"


class TestNeverStopRecovery:
    def test_restarts_dead_daemon_thread(self) -> None:
        registry = RuntimeDaemonRegistry.get()
        stop = threading.Event()

        def _worker() -> None:
            stop.wait(0.01)

        thread = threading.Thread(target=_worker, daemon=True, name="test-daemon")
        thread.start()
        thread.join(timeout=1.0)
        assert thread.is_alive() is False

        restarted = threading.Event()

        def _factory() -> None:
            restarted.set()
            while True:
                time.sleep(0.2)

        registry.register("test-daemon", thread, target_factory=_factory)

        container = SimpleNamespace(trade_reconciler=None)
        policy = SafeRestartPolicy(mode="sim", prod_cfg={"max_in_process_recovery_attempts": 3})
        recovery = NeverStopRecovery(mode="sim", container=container, restart_policy=policy)

        with patch.object(registry, "restart_daemon", wraps=registry.restart_daemon) as restart_mock:
            result = recovery.tick()
            assert "test-daemon" in result.dead_daemons
            restart_mock.assert_called()
        time.sleep(0.05)

    def test_blocked_supervisor_counts_toward_escalation(self) -> None:
        registry = RuntimeDaemonRegistry.get()
        stop = threading.Event()

        def _worker() -> None:
            stop.wait(0.01)

        thread = threading.Thread(target=_worker, daemon=True, name="supervisor-loop")
        thread.start()
        thread.join(timeout=1.0)
        registry.register("supervisor-loop", thread, target_factory=lambda: None)

        container = SimpleNamespace(trade_reconciler=None)
        policy = SafeRestartPolicy(mode="real", prod_cfg={"max_in_process_recovery_attempts": 1})
        recovery = NeverStopRecovery(
            mode="real",
            container=container,
            restart_policy=policy,
            prod_cfg={"max_in_process_recovery_attempts": 1},
        )

        result = recovery.tick()
        assert "supervisor-loop" in result.blocked
        assert policy.restart_requested() or result.escalated


class TestWatchdogRateLimit:
    def test_loads_max_restarts_per_hour_from_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = {"headless": {"production": {"max_process_restarts_per_hour": 9}}}
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        monkeypatch.setenv("LUMINA_CONFIG", str(cfg_path))
        monkeypatch.delenv("LUMINA_MAX_RESTARTS_PER_HOUR", raising=False)

        import importlib.util

        repo_root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("lumina_repo_watchdog", repo_root / "watchdog.py")
        assert spec is not None and spec.loader is not None
        lumina_watchdog = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lumina_watchdog)
        assert lumina_watchdog._load_max_restarts_per_hour() == 9


class TestSmokeModeRouting:
    def test_smoke_flag_parsed(self) -> None:
        from lumina_core.engine.runtime_entrypoint import _build_parser, _smoke_mode_requested

        parser = _build_parser()
        args = parser.parse_args(["--smoke", "--mode", "sim", "--duration", "5m"])
        assert _smoke_mode_requested(args) is True

    def test_headless_without_smoke_is_production(self) -> None:
        from lumina_core.engine.runtime_entrypoint import _build_parser, _smoke_mode_requested

        parser = _build_parser()
        args = parser.parse_args(["--headless", "--mode", "sim"])
        assert _smoke_mode_requested(args) is False

    def test_production_cfg_override_parsed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from lumina_core.engine.runtime_entrypoint import _load_production_cfg_override

        monkeypatch.setenv("LUMINA_HEADLESS_PRODUCTION_JSON", '{"heartbeat_interval_s": 5}')
        override = _load_production_cfg_override()
        assert override == {"heartbeat_interval_s": 5}
