"""Phase 3 perfection plan gate: Guardian + broad pytest + smokes."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    print("RUN:", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT, env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)})
    print("EXIT", r.returncode)
    return r.returncode


def main() -> int:
    tests = [
        "tests/engine/test_rl_bias_applier.py",
        "tests/engine/test_supervisor_phase_state_machine.py",
        "tests/engine/test_supervisor_phase_remediation_integration.py",
        "tests/engine/test_price_dupe_resolver.py",
        "tests/engine/test_paper_simulator.py",
        "tests/engine/test_eod_force_close_service.py",
        "tests/engine/test_real_close_detector.py",
        "tests/engine/test_live_position_manager.py",
        "tests/engine/test_pre_dream_daemon.py",
        "tests/engine/test_pre_dream_news_cycle.py",
        "tests/engine/test_pre_dream_vision_cycle.py",
        "tests/engine/test_pre_dream_consensus_preamble.py",
        "tests/engine/test_pre_dream_market_tick.py",
        "tests/engine/test_paper_trade_executor.py",
        "tests/test_runtime_workers.py",
        "tests/engine/test_voice_listener_daemon.py",
        "tests/engine/test_trader_league_webhook.py",
        "tests/engine/test_runtime_monitoring_service.py",
        "tests/engine/test_emotional_twin_worker.py",
        "tests/engine/test_state_persist_daemon.py",
        "tests/engine/test_runtime_workers_god_surfaces.py",
        "tests/monitoring/test_adaptive_intelligence_tracker.py",
        "tests/test_agent_blackboard.py",
        "tests/engine/test_policy_engine_lineage.py",
        "tests/engine/test_order_gatekeeper_typed_history.py",
        "tests/audit/test_d4_birth_prereq.py",
    ]
    rc = run([sys.executable, "-m", "pytest", "-q", "--tb=line", *tests])
    if rc:
        return rc
    rc = run([sys.executable, str(ROOT / "scripts" / "phase2_sub10_12_crossverify_smoke.py")])
    if rc:
        return rc
    rc = run([sys.executable, str(ROOT / "scripts" / "phase3_track_c_gate_verify.py")])
    if rc:
        return rc
    print("PHASE3_GATE_VERIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
