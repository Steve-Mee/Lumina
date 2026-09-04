"""G2/G3: BirthPhaseEngineV2 on the genesis tape + birth-exit exam."""

from __future__ import annotations

import json
import os
import shutil
import threading
import traceback
from pathlib import Path
from typing import Any

from lumina_core.birth.fitness_vector import FITNESS_VECTOR_NAME, load_fitness_vector, receipt_checksum
from lumina_core.birth.genesis_cloud_const import (
    BIRTH_INCOMPLETE,
    NEWBORN_META_NAME,
    NEWBORN_ZIP_NAME,
    OLD_ENGINE_ZIP_NAME,
    STAGE_RECEIPT_FILES,
)
from lumina_core.birth.genesis_cloud_protocol import GenesisProtocolError
from lumina_core.birth.genesis_cloud_workspace import file_sha256
from lumina_core.birth.progress import read_birth_progress
from lumina_core.birth.stage_pass_receipt_types import parse_stage_pass_receipts, receipt_for_stage
from lumina_core.birth.synthetic_cloud_fixture import FixtureMarketDataService
from lumina_core.birth.tick_cache_persist import load_ticks_cache
from lumina_core.maturity.birth_exit import evaluate_birth_exit, is_birth_exit_sufficient


def construct_genesis_engine(
    work: Path,
    *,
    ticks: list[dict[str, Any]],
    instrument: str,
    stop_event: threading.Event,
) -> Any:
    from lumina_core.birth.engine import BirthPhaseEngineV2
    from lumina_core.container import ApplicationContainer
    from lumina_core.engine.runtime_mode_runners import _bind_headless_runtime_app

    os.environ["LUMINA_CONFIG"] = str((work / "config.yaml").resolve())
    os.environ["VOICE_ENABLED"] = "false"
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    try:
        from lumina_core.engine.engine_config_helpers import clear_yaml_config_cache

        clear_yaml_config_cache()
    except Exception:
        pass
    container = ApplicationContainer()
    _bind_headless_runtime_app(container)
    # Never container.start() — that is broker connect.
    fixture_md = FixtureMarketDataService(ticks, instrument=instrument)
    return BirthPhaseEngineV2(
        runtime=container.engine,
        ppo_trainer=container.ppo_trainer,
        market_data_service=fixture_md,
        config={"first_boot": {"prefer_real_data_only": True, "max_real_days": 90}},
        workspace_root=work,
        stop_event=stop_event,
    )


def run_genesis_birth(
    work: Path,
    art: Path,
    *,
    timeout_sec: int,
    target_trades: int,
    instrument: str,
) -> dict[str, Any]:
    ticks = load_ticks_cache(work)
    if len(ticks) < 1000:
        return {"status": "history_unavailable", "error": "ticks cache empty", "timed_out": False}
    stop_event = threading.Event()
    timed_out = {"v": False}

    def _on_timeout() -> None:
        timed_out["v"] = True
        stop_event.set()

    timer = threading.Timer(max(1, int(timeout_sec)), _on_timeout)
    timer.daemon = True
    timer.start()
    result: dict[str, Any] | None = None
    error = ""
    previous = Path.cwd()
    try:
        os.chdir(work)
        engine = construct_genesis_engine(work, ticks=ticks, instrument=instrument, stop_event=stop_event)
        pause_flag = work / "state" / "first_boot_pause_requested"
        try:
            pause_flag.unlink(missing_ok=True)
        except OSError:
            pass
        result = engine.run_birth_phase(
            force=True,
            practice_mode=False,
            reuse_data_manifest=True,
            prefer_real_data_only=True,
            reuse_existing_policy=False,
            max_real_days=90,
            target_trades=int(target_trades),
            ppo_update_timesteps=1_000,
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        result = {"status": "error", "error": error}
    finally:
        timer.cancel()
        try:
            os.chdir(previous)
        except OSError:
            pass
    status = str((result or {}).get("status") or "")
    exited = bool(is_birth_exit_sufficient(work))
    if timed_out["v"] and not exited:
        status = BIRTH_INCOMPLETE
    payload = {
        "status": status or BIRTH_INCOMPLETE,
        "engine_result": result,
        "error": error,
        "timed_out": bool(timed_out["v"]),
        "birth_exited": exited,
        "checkpoint": _checkpoint_snapshot(work),
        "progress": _progress_snapshot(work),
    }
    (art / "g2_birth_engine_result.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    export_birth_artifacts(work, art)
    return payload


def _checkpoint_snapshot(work: Path) -> dict[str, Any]:
    ckpt = work / "state" / "lumina_birth_checkpoint.json"
    if not ckpt.is_file():
        return {}
    try:
        raw = json.loads(ckpt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    metrics = raw.get("stage_metrics") if isinstance(raw.get("stage_metrics"), dict) else {}
    return {
        "curriculum_stage": raw.get("curriculum_stage"),
        "stages_passed": raw.get("stages_passed"),
        "stage_trades": metrics.get("stage_trades"),
        "path": str(ckpt),
    }


def _progress_snapshot(work: Path) -> dict[str, Any]:
    progress = read_birth_progress(work)
    receipts = parse_stage_pass_receipts(progress.get("stage_pass_receipts"))
    return {
        "phase": progress.get("phase") or progress.get("status"),
        "receipt_stages": [str(getattr(r, "stage", "")) for r in receipts],
        "receipt_count": len(receipts),
    }


def export_birth_artifacts(work: Path, art: Path) -> None:
    progress = read_birth_progress(work)
    receipts = parse_stage_pass_receipts(progress.get("stage_pass_receipts"))
    if not receipts:
        ckpt = work / "state" / "lumina_birth_checkpoint.json"
        if ckpt.is_file():
            try:
                raw = json.loads(ckpt.read_text(encoding="utf-8"))
                receipts = parse_stage_pass_receipts((raw or {}).get("stage_pass_receipts"))
            except (OSError, json.JSONDecodeError, TypeError):
                receipts = []
    for stage, name in STAGE_RECEIPT_FILES:
        rec = receipt_for_stage(receipts, stage)
        if rec is None:
            continue
        (art / name).write_text(json.dumps(rec.to_dict(), indent=2) + "\n", encoding="utf-8")
    vec_src = work / "state" / FITNESS_VECTOR_NAME
    if vec_src.is_file():
        shutil.copy2(vec_src, art / FITNESS_VECTOR_NAME)
    close_src = work / "state" / "s5_close_ledger.jsonl"
    if close_src.is_file():
        shutil.copy2(close_src, art / "s5_close_ledger.jsonl")
    copy_newborn_zip(work, art)


def copy_newborn_zip(work: Path, art: Path) -> Path | None:
    dest = art / NEWBORN_ZIP_NAME
    found: Path | None = None
    for path in work.rglob(OLD_ENGINE_ZIP_NAME):
        posix = path.as_posix()
        if "birth_cloud_run" in posix and "genesis_cloud_run" not in posix:
            raise GenesisProtocolError(f"engine wrote old-tree pi_star: {posix}")
        found = path
        break
    if found is None:
        return None
    dest_posix = dest.resolve().as_posix()
    if dest_posix.endswith("/reports/birth_cloud_run/artifacts/" + OLD_ENGINE_ZIP_NAME):
        raise GenesisProtocolError("refused overwrite of old birth_exit_pi_star.zip")
    shutil.copy2(found, dest)
    meta_src = found.with_name("birth_exit_pi_star.json")
    sidecar = art / NEWBORN_META_NAME
    payload = {
        "schema": "genesis_birth_exit_pi_star_v1",
        "path": str(dest),
        "sha256": file_sha256(dest),
        "bytes": int(dest.stat().st_size),
        "source": "genesis_s5_pass_pre_polish" if dest.is_file() else "missing",
        "copied_from": str(found),
        "evolution_proof": False,
        "REAL": "no",
    }
    if meta_src.is_file():
        try:
            payload["engine_meta"] = json.loads(meta_src.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    sidecar.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return dest


def genesis_birth_exit_exam(work: Path, art: Path) -> dict[str, Any]:
    decision = evaluate_birth_exit(work)
    vector = load_fitness_vector(work)
    s5_path = art / "s5_receipt.json"
    s5_raw = json.loads(s5_path.read_text(encoding="utf-8")) if s5_path.is_file() else None
    checksum_ok = False
    expected = ""
    got = ""
    if vector is not None and isinstance(s5_raw, dict):
        expected = receipt_checksum(s5_raw)
        got = str(vector.s5_receipt_checksum)
        checksum_ok = got == expected
    zip_path = art / NEWBORN_ZIP_NAME
    zip_sha = file_sha256(zip_path) if zip_path.is_file() else ""
    exam = {
        "exited": bool(decision.exited),
        "missing": list(decision.missing),
        "proofs": list(decision.proofs),
        "fitness_checksum_ok": checksum_ok,
        "fitness_checksum": got,
        "s5_checksum": expected,
        "newborn_zip_sha256": zip_sha,
        "real_data_pct": 0.0,
        "decision": decision.to_dict(),
    }
    (art / "g3_birth_exit_exam.json").write_text(json.dumps(exam, indent=2, default=str) + "\n")
    return exam


__all__ = [
    "construct_genesis_engine",
    "copy_newborn_zip",
    "export_birth_artifacts",
    "genesis_birth_exit_exam",
    "run_genesis_birth",
]
