#!/usr/bin/env python3
"""Headless Birth Phase v2 cloud shadow runner.

Calls the same engine the app uses (``BirthPhaseEngineV2.run_birth_phase``).
Does not start Tauri, Streamlit, NinjaTrader, or a live broker.

Exit codes:
  0   birth_exit_ok (``is_birth_exit_sufficient``)
  2   stage_stalled / constitution abort / honest fail
  3   infra / data / engine wiring failure
  124 timeout (partial artifacts still written)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = REPO_ROOT / "reports" / "birth_cloud_run" / "workspace"
DEFAULT_REPORTS = REPO_ROOT / "reports" / "birth_cloud_run"
DEFAULT_TIMEOUT_SEC = 90 * 60
EXIT_OK = 0
EXIT_FAIL = 2
EXIT_INFRA = 3
EXIT_TIMEOUT = 124


def _detect_gpu() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _default_target_trades() -> int:
    return 25_000 if _detect_gpu() else 8_000


def _prepare_workspace(workspace: Path, *, repo_root: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "state").mkdir(parents=True, exist_ok=True)
    src = repo_root / "config.yaml"
    dest = workspace / "config.yaml"
    if not dest.is_file():
        shutil.copy2(src, dest)
    _overlay_workspace_config(dest)
    catalog_src = repo_root / "lumina_model_catalog.json"
    catalog_dest = workspace / "lumina_model_catalog.json"
    if catalog_src.is_file() and not catalog_dest.is_file():
        shutil.copy2(catalog_src, catalog_dest)
    return dest


def _overlay_workspace_config(path: Path) -> None:
    """SIM overlay: NQ primary, faster checkpoints. Does not touch stage/cert floors."""
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise RuntimeError("workspace config.yaml is not a mapping")
    raw["mode"] = "sim"
    trading = dict(raw.get("trading") or {})
    trading["instrument"] = "NQ SEP26"
    raw["trading"] = trading
    first_boot = dict(raw.get("first_boot") or {})
    first_boot["prefer_real_data_only"] = True
    first_boot["allow_minimal_synthetic_fallback"] = False
    first_boot["max_real_days"] = 90
    raw["first_boot"] = first_boot
    birth = dict(raw.get("birth_v2") or {})
    birth["prefer_real_data_only"] = True
    birth["max_real_days"] = 90
    cur = dict(birth.get("curriculum") or {})
    # Interval only — not a pass floor. Makes crash/resume observable in-cloud.
    cur["checkpoint_interval_sec"] = min(int(cur.get("checkpoint_interval_sec") or 600), 20)
    birth["curriculum"] = cur
    raw["birth_v2"] = birth
    broker = dict(raw.get("broker") or {})
    nt = dict(broker.get("ninjatrader") or {})
    # Keep ninjatrader.enabled so sim+live-backend matrix stays valid; never connect.
    nt["enabled"] = True
    broker["ninjatrader"] = nt
    broker["live_provider"] = "ninjatrader"
    raw["broker"] = broker
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _ensure_fixture(workspace: Path, reports_dir: Path, *, force_regen: bool = False) -> dict[str, Any]:
    from lumina_core.birth.synthetic_cloud_fixture import (
        CloudFixtureSpec,
        persist_cloud_fixture,
        write_fixture_sidecar,
    )
    from lumina_core.birth.tick_cache_persist import certified_tick_cache_present

    sidecar = reports_dir / "01_fixture_manifest.json"
    if certified_tick_cache_present(workspace) and sidecar.is_file() and not force_regen:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    spec = CloudFixtureSpec()
    result = persist_cloud_fixture(workspace, spec=spec)
    write_fixture_sidecar(sidecar, result.fixture_manifest)
    return dict(result.fixture_manifest)


def _load_fixture_ticks(workspace: Path) -> list[dict[str, Any]]:
    from lumina_core.birth.tick_cache_persist import load_ticks_cache

    return load_ticks_cache(workspace)


def _construct_engine(
    workspace: Path,
    *,
    stop_event: threading.Event,
    ticks: list[dict[str, Any]],
    instrument: str,
) -> Any:
    from lumina_core.birth.engine import BirthPhaseEngineV2
    from lumina_core.birth.synthetic_cloud_fixture import FixtureMarketDataService
    from lumina_core.container import ApplicationContainer
    from lumina_core.engine.runtime_mode_runners import _bind_headless_runtime_app

    os.environ["LUMINA_CONFIG"] = str((workspace / "config.yaml").resolve())
    os.environ["VOICE_ENABLED"] = "false"
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    os.environ.setdefault("LUMINA_LOG_LEVEL", "INFO")
    # Isolated cwd so container state/ logs stay in the shadow workspace.
    os.chdir(workspace)
    try:
        from lumina_core.engine.engine_config_helpers import clear_yaml_config_cache

        clear_yaml_config_cache()
    except Exception:
        pass

    container = ApplicationContainer()
    _bind_headless_runtime_app(container)
    # Never container.start() — that connects the broker.
    fixture_md = FixtureMarketDataService(ticks, instrument=instrument)
    engine = BirthPhaseEngineV2(
        runtime=container.engine,
        ppo_trainer=container.ppo_trainer,
        market_data_service=fixture_md,
        config={"first_boot": {"prefer_real_data_only": True, "max_real_days": 90}},
        workspace_root=workspace,
        stop_event=stop_event,
    )
    return engine


def _map_exit(result: dict[str, Any] | None, *, timed_out: bool, workspace: Path) -> int:
    from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

    if timed_out:
        return EXIT_TIMEOUT
    if is_birth_exit_sufficient(workspace):
        return EXIT_OK
    status = str((result or {}).get("status") or "").strip().lower()
    if status in {"history_unavailable", "error"}:
        return EXIT_INFRA
    if status in {"stage_stalled", "stage_failed", "certificate_failed", "aborted", "constitution_abort"}:
        return EXIT_FAIL
    if status in {"paused"}:
        return EXIT_TIMEOUT
    return EXIT_FAIL


def _dump_exit_snapshot(workspace: Path, reports_dir: Path, result: dict[str, Any] | None) -> None:
    from lumina_core.maturity.birth_exit import evaluate_birth_exit, is_birth_exit_sufficient

    decision = evaluate_birth_exit(workspace)
    snap = {
        "is_birth_exit_sufficient": bool(is_birth_exit_sufficient(workspace)),
        "decision": decision.to_dict(),
        "engine_result": result,
    }
    (reports_dir / "exit_snapshot.json").write_text(
        json.dumps(snap, indent=2, default=str) + "\n", encoding="utf-8"
    )


def run_birth(
    *,
    workspace: Path,
    reports_dir: Path,
    force: bool,
    timeout_sec: int,
    target_trades: int,
    ppo_update_timesteps: int,
) -> int:
    from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

    stop_event = threading.Event()
    timed_out = {"v": False}

    def _on_timeout() -> None:
        timed_out["v"] = True
        stop_event.set()

    timer = threading.Timer(max(1, int(timeout_sec)), _on_timeout)
    timer.daemon = True
    timer.start()
    result: dict[str, Any] | None = None
    try:
        fixture = _ensure_fixture(workspace, reports_dir)
        ticks = _load_fixture_ticks(workspace)
        if not ticks:
            print("INFRA: fixture ticks cache empty", file=sys.stderr)
            return EXIT_INFRA
        print(
            f"birth.cloud.fixture ticks={len(ticks):,} days={fixture.get('days')} "
            f"source={fixture.get('source')} holdout_regimes={fixture.get('holdout_regimes')}",
            flush=True,
        )
        engine = _construct_engine(
            workspace,
            stop_event=stop_event,
            ticks=ticks,
            instrument=str(fixture.get("symbol") or "NQ SEP26"),
        )
        print("birth.cloud.engine_constructed class=BirthPhaseEngineV2", flush=True)
        if force:
            # Stall abort writes first_boot_pause_requested; --force is a clean plant.
            pause_flag = workspace / "state" / "first_boot_pause_requested"
            try:
                pause_flag.unlink(missing_ok=True)
            except OSError:
                pass
        result = engine.run_birth_phase(
            target_trades=int(target_trades),
            max_real_days=90,
            prefer_real_data_only=True,
            ppo_update_timesteps=int(ppo_update_timesteps),
            force=bool(force),
            practice_mode=False,
            reuse_data_manifest=True,
        )
        print(f"birth.cloud.engine_result={json.dumps(result, default=str)[:4000]}", flush=True)
    except Exception:
        traceback.print_exc()
        _dump_exit_snapshot(workspace, reports_dir, result)
        return EXIT_INFRA
    finally:
        timer.cancel()
        _dump_exit_snapshot(workspace, reports_dir, result)

    code = _map_exit(result, timed_out=bool(timed_out["v"]), workspace=workspace)
    print(
        f"birth.cloud.exit={code} birth_exit_ok={is_birth_exit_sufficient(workspace)} "
        f"timed_out={timed_out['v']}",
        flush=True,
    )
    return code


def _checkpoint_stage_trades(workspace: Path) -> tuple[str, int]:
    ckpt = workspace / "state" / "lumina_birth_checkpoint.json"
    if not ckpt.is_file():
        return "", 0
    try:
        payload = json.loads(ckpt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "", 0
    stage = str(payload.get("curriculum_stage") or "")
    metrics = payload.get("stage_metrics") if isinstance(payload.get("stage_metrics"), dict) else {}
    trades = int(metrics.get("stage_trades") or 0)
    return stage, trades


def run_fault_inject(
    *,
    workspace: Path,
    reports_dir: Path,
    kill_after_seconds: int,
    resume_timeout_sec: int,
    target_trades: int,
    ppo_update_timesteps: int,
    python_exe: str,
) -> int:
    """Start a child Birth, kill after a checkpoint, resume with force=False."""
    child_cmd = [
        python_exe,
        str(Path(__file__).resolve()),
        "--workspace",
        str(workspace),
        "--reports-dir",
        str(reports_dir),
        "--timeout-sec",
        str(max(kill_after_seconds + 30, 120)),
        "--target-trades",
        str(target_trades),
        "--ppo-update-timesteps",
        str(ppo_update_timesteps),
        "--force",
    ]
    print(f"birth.cloud.fault_inject.spawn cmd={child_cmd}", flush=True)
    proc = subprocess.Popen(child_cmd, cwd=str(REPO_ROOT))
    deadline = time.time() + max(5, int(kill_after_seconds))
    saw_ckpt = False
    stage_before = ""
    trades_before = 0
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                print(f"birth.cloud.fault_inject.child_exited_early code={proc.returncode}", flush=True)
                break
            stage, trades = _checkpoint_stage_trades(workspace)
            if stage and trades > 0:
                saw_ckpt = True
                stage_before, trades_before = stage, trades
                time.sleep(2.0)
                break
            time.sleep(1.0)
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()

    stage_at_kill, trades_at_kill = _checkpoint_stage_trades(workspace)
    if saw_ckpt:
        stage_before = stage_before or stage_at_kill
        trades_before = trades_before or trades_at_kill
    evidence = {
        "saw_checkpoint_before_kill": saw_ckpt,
        "stage_before": stage_before or stage_at_kill,
        "stage_trades_before": trades_before or trades_at_kill,
        "child_returncode": proc.returncode,
    }
    print(f"birth.cloud.fault_inject.killed {json.dumps(evidence)}", flush=True)

    resume_code = run_birth(
        workspace=workspace,
        reports_dir=reports_dir,
        force=False,
        timeout_sec=resume_timeout_sec,
        target_trades=target_trades,
        ppo_update_timesteps=ppo_update_timesteps,
    )
    stage_after, trades_after = _checkpoint_stage_trades(workspace)
    rewind = bool(stage_before) and stage_after == "stage1_trend" and stage_before != "stage1_trend"
    chunk = 250
    preserved = (not rewind) and (
        trades_after >= max(0, (trades_before or trades_at_kill) - chunk)
        or (trades_before or trades_at_kill) == 0
    )
    evidence.update(
        {
            "stage_after": stage_after,
            "stage_trades_after": trades_after,
            "rewound_to_s1": rewind,
            "stage_trades_preserved": preserved,
            "resume_exit": resume_code,
        }
    )
    (reports_dir / "run2_resume_evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(f"birth.cloud.fault_inject.resume {json.dumps(evidence)}", flush=True)
    if rewind or not preserved:
        return EXIT_FAIL
    return resume_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Headless Birth Phase v2 cloud shadow runner")
    p.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    p.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    p.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
    p.add_argument("--target-trades", type=int, default=0)
    p.add_argument("--ppo-update-timesteps", type=int, default=1_000)
    p.add_argument("--force", action="store_true", help="Clean plant (ignore checkpoint)")
    p.add_argument("--resume", action="store_true", help="force=False resume from checkpoint")
    p.add_argument("--write-fixture-only", action="store_true")
    p.add_argument("--regen-fixture", action="store_true")
    p.add_argument("--kill-after-seconds", type=int, default=0)
    p.add_argument("--resume-timeout-sec", type=int, default=300)
    p.add_argument("--fault-inject", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = args.workspace.resolve()
    reports_dir = args.reports_dir.resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    if not str(workspace).startswith(str(reports_dir)):
        # Isolated workspace is required; default lives under reports/.
        pass
    os.environ["VOICE_ENABLED"] = "false"
    sys.path.insert(0, str(REPO_ROOT))
    _prepare_workspace(workspace, repo_root=REPO_ROOT)
    target = int(args.target_trades) if int(args.target_trades) > 0 else _default_target_trades()
    target = max(2_000, target)
    if args.write_fixture_only:
        man = _ensure_fixture(workspace, reports_dir, force_regen=bool(args.regen_fixture))
        print(json.dumps(man, indent=2), flush=True)
        return 0
    if args.fault_inject or int(args.kill_after_seconds) > 0:
        kill_after = int(args.kill_after_seconds) or 90
        return run_fault_inject(
            workspace=workspace,
            reports_dir=reports_dir,
            kill_after_seconds=kill_after,
            resume_timeout_sec=int(args.resume_timeout_sec),
            target_trades=target,
            ppo_update_timesteps=max(1_000, int(args.ppo_update_timesteps)),
            python_exe=sys.executable,
        )
    force = bool(args.force) and not bool(args.resume)
    return run_birth(
        workspace=workspace,
        reports_dir=reports_dir,
        force=force if (args.force or args.resume) else True,
        timeout_sec=int(args.timeout_sec),
        target_trades=target,
        ppo_update_timesteps=max(1_000, int(args.ppo_update_timesteps)),
    )


if __name__ == "__main__":
    raise SystemExit(main())
