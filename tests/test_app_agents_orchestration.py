"""Integration checks: full ApplicationContainer + agent surfaces used by the launcher/runtime.

These tests approximate 'all agents work in the app' without starting the full GUI loop or live trading.
Nightly coordination is covered via ``MetaAgentOrchestrator.run_nightly_reflection`` (dry_run), which is
also invoked at the end of ``InfiniteSimulator.run_nightly`` in production.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
import types
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def container_with_stub_app(monkeypatch):
    """Real container graph with broker I/O stubbed and a minimal bound runtime app module."""

    def _stub_broker(**_kwargs):
        return types.SimpleNamespace(connect=lambda: True, disconnect=lambda: None)

    monkeypatch.setattr("lumina_core.container.broker_factory", _stub_broker)

    from lumina_core.container import create_application_container

    container = create_application_container()
    stub = types.ModuleType("lumina_app_agents_integration_stub")
    stub.logger = container.logger
    stub.INSTRUMENT = str(getattr(container.config, "instrument", None) or "MES JUN26")
    stub.FAST_PATH_ONLY = False
    stub.world_model = {}
    stub.get_high_impact_news = lambda: {"events": [], "overall_sentiment": "neutral", "impact": "low"}
    container.engine.bind_app(stub)
    container.runtime_context.app = stub
    return container


def test_container_surfaces_agents_and_meta_orchestrator(container_with_stub_app) -> None:
    c = container_with_stub_app
    assert c.news_agent is not None
    assert c.emotional_twin_agent is not None
    assert c.self_evolution_meta_agent is not None
    assert c.meta_agent_orchestrator is not None
    assert c.regime_detector is not None
    assert c.swarm_manager is not None
    st = c.get_status()
    assert st["engine_initialized"] is True
    assert st["services_count"] >= 10


def test_news_agent_cycle_fails_safe(container_with_stub_app, monkeypatch) -> None:
    from lumina_agents.news_agent import NewsAgent

    def _no_xai(self, prompt: str) -> str:
        return ""

    monkeypatch.setattr(NewsAgent, "_call_xai", _no_xai)
    c = container_with_stub_app
    out = c.news_agent.run_news_cycle()
    assert isinstance(out, dict)
    assert "sentiment_signal" in out
    assert "dynamic_multiplier" in out


def test_tape_blackboard_publish(container_with_stub_app) -> None:
    c = container_with_stub_app
    c.market_data_service._publish_tape_signal(
        {
            "signal": "BUY",
            "direction": "BUY",
            "confidence": 0.81,
            "reason": "integration tape",
            "fast_path_trigger": False,
            "cumulative_delta_10": 100.0,
            "bid_ask_imbalance": 1.1,
        }
    )
    bb = c.blackboard
    assert bb is not None
    prop = bb.latest("agent.tape.proposal")
    assert prop is not None
    assert prop.payload.get("tape_signal") == "BUY"


def test_emotional_twin_run_cycle(container_with_stub_app) -> None:
    c = container_with_stub_app
    out = c.emotional_twin_agent.run_cycle()
    assert isinstance(out, dict)


def test_emotional_twin_nightly_train_noop_on_empty(container_with_stub_app) -> None:
    c = container_with_stub_app
    c.emotional_twin_agent.nightly_train([], [])


def test_regime_detector_on_synthetic_bars(container_with_stub_app) -> None:
    c = container_with_stub_app
    rng = pd.date_range("2026-01-01", periods=80, freq="1min")
    price = pd.Series(range(80), dtype=float) + 5000.0
    df = pd.DataFrame(
        {
            "timestamp": rng,
            "open": price,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price + 0.1,
            "volume": 1000,
        }
    )
    snap = c.regime_detector.detect(df, instrument=str(c.config.instrument))
    assert snap.label
    assert 0.0 <= float(snap.confidence) <= 1.0


def test_meta_orchestrator_nightly_reflection_dry_run(container_with_stub_app) -> None:
    c = container_with_stub_app
    orch = c.meta_agent_orchestrator
    assert orch is not None
    report = {
        "winrate": 0.52,
        "net_pnl": 150.0,
        "sharpe": 1.1,
        "mean_worker_sharpe": 1.1,
    }
    result = orch.run_nightly_reflection(nightly_report=report, dry_run=True)
    assert isinstance(result, dict)
    assert "reflection" in result
    assert "evolution" in result
    assert c.blackboard is not None
    assert c.blackboard.latest("meta.reflection") is not None


def test_swarm_manager_run_swarm_cycle(container_with_stub_app) -> None:
    c = container_with_stub_app
    out = c.swarm_manager.run_swarm_cycle()
    assert isinstance(out, dict)
    assert "global_regime" in out


@pytest.mark.integration
def test_streamlit_launcher_http_boot() -> None:
    if shutil.which("streamlit") is None:
        pytest.skip("streamlit not on PATH")
    port = 9876
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(REPO_ROOT / "lumina_launcher.py"),
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    url = f"http://127.0.0.1:{port}/"
    deadline = time.monotonic() + 45.0
    last_err: Exception | None = None
    try:
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=2.0) as resp:
                    body = resp.read(8000).decode("utf-8", errors="replace")
                assert "LUMINA" in body.upper() or "streamlit" in body.lower() or len(body) > 100
                return
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_err = exc
                if proc.poll() is not None:
                    out = (proc.stdout.read() if proc.stdout else "") or ""
                    pytest.fail(f"Streamlit exited early (code={proc.returncode}): {out[:2000]}\nlast_err={last_err}")
                time.sleep(0.5)
        pytest.fail(f"Streamlit did not become reachable: {last_err}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
