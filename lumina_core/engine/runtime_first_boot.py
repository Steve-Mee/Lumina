"""First-boot training path extracted from runtime_entrypoint (behavior-preserving).

Symbols that tests monkeypatch on ``runtime_entrypoint`` are resolved via the
façade module at call time so patching remains effective.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from lumina_core.first_boot_ui import (
    FIRST_BOOT_DEFAULT_MAX_REAL_DAYS,
    FIRST_BOOT_DEFAULT_TRADES,
    estimate_first_boot_real_days,
    normalize_first_boot_training_trades,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
FIRST_BOOT_FLAG_PATH = ROOT_DIR / "state" / "lumina_birth_completed.flag"
FIRST_BOOT_LEGACY_FLAG_PATH = ROOT_DIR / "state" / "first_boot_completed.flag"
FIRST_BOOT_POLICY_PATH = ROOT_DIR / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
FIRST_BOOT_PROGRESS_PATH = ROOT_DIR / "state" / "lumina_birth_progress.json"
FIRST_BOOT_LEGACY_PROGRESS_PATH = ROOT_DIR / "state" / "first_boot_progress.json"
FIRST_BOOT_EXIT_PAUSED = 2

_FACADE_MODULE = "lumina_core.engine.runtime_entrypoint"


def _ep() -> Any:
    """Resolve the public façade module (monkeypatch target) when loaded."""
    mod = sys.modules.get(_FACADE_MODULE)
    if mod is not None:
        return mod
    from lumina_core.engine import runtime_entrypoint as ep

    return ep


def _write_first_boot_progress(stage: str, message: str, **extra: object) -> None:
    from lumina_core.birth.stage_scorecard import enrich_progress_scorecard

    ep = _ep()
    progress_path: Path = ep.FIRST_BOOT_PROGRESS_PATH
    prev: dict[str, object] = {}
    # Canonical lumina_birth only (legacy first_boot read for compat elsewhere)
    if progress_path.exists():
        try:
            prev = json.loads(progress_path.read_text(encoding="utf-8"))
            if not isinstance(prev, dict):
                prev = {}
        except Exception:
            prev = {}
    else:
        prev = {}
    payload: dict[str, object] = dict(prev)
    payload["timestamp"] = datetime.now().isoformat()
    payload["stage"] = str(stage).strip().lower()
    payload["message"] = str(message)
    payload.update(extra)
    enriched = enrich_progress_scorecard({k: v for k, v in payload.items()})
    payload.update(enriched)
    try:
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=True)
        progress_path.write_text(encoded, encoding="utf-8")
        # Legacy dual write removed for radical simplicity
    except Exception:
        logging.exception("first_boot.progress_write_failed")


def _load_first_boot_config() -> dict[str, int | bool]:
    ep = _ep()
    raw = ep.ConfigLoader.section("first_boot", default={}) or {}
    cfg = raw if isinstance(raw, dict) else {}
    training_trades = normalize_first_boot_training_trades(cfg.get("training_trades", FIRST_BOOT_DEFAULT_TRADES))
    prefer_real_data_only = bool(cfg.get("prefer_real_data_only", True))
    max_real_days = int(cfg.get("max_real_days", FIRST_BOOT_DEFAULT_MAX_REAL_DAYS) or FIRST_BOOT_DEFAULT_MAX_REAL_DAYS)
    allow_minimal_synth = bool(cfg.get("allow_minimal_synthetic_fallback", False))
    force_training = bool(cfg.get("force_training", True))
    birth_phase = bool(cfg.get("birth_phase", True))
    return {
        "training_trades": training_trades,
        "prefer_real_data_only": prefer_real_data_only,
        "max_real_days": max(30, min(3_650, max_real_days)),
        "allow_minimal_synthetic_fallback": allow_minimal_synth,
        "force_training": force_training,
        "birth_phase": birth_phase,
    }


def _first_boot_needed() -> bool:
    ep = _ep()
    missing_flag = not (ep.FIRST_BOOT_FLAG_PATH.exists() or ep.FIRST_BOOT_LEGACY_FLAG_PATH.exists())
    missing_policy = not ep.FIRST_BOOT_POLICY_PATH.exists()
    missing_artifacts = missing_flag or missing_policy
    cfg = ep._load_first_boot_config()
    force_training = bool(cfg.get("force_training", True))
    logging.info(
        "first_boot.check mandatory=true force_training_legacy=%s missing_flag=%s missing_policy=%s",
        force_training,
        missing_flag,
        missing_policy,
    )
    if missing_artifacts and not force_training:
        logging.warning(
            "first_boot.force_training=false is legacy en wordt genegeerd: initiële training blijft verplicht zolang artifacts ontbreken."
        )
    return missing_artifacts


def _run_first_boot_training() -> int:
    # BIRTH ENGINE 2026-05-17
    ep = _ep()
    cfg = ep._load_first_boot_config()
    target = int(cfg["training_trades"])
    prefer_real = bool(cfg["prefer_real_data_only"])
    max_days = int(cfg["max_real_days"])
    birth_phase_enabled = bool(cfg.get("birth_phase", True))
    estimated_days = estimate_first_boot_real_days(target)

    start_message = (
        "Eerste keer starten gedetecteerd. Lumina voert initiële training uit. "
        "Trading is tijdelijk geblokkeerd..."
    )
    logging.info("First boot detected - blocking trading until training complete")
    ep._write_first_boot_progress("detected", start_message, target_trades=target, max_real_days=max_days)
    print(start_message, flush=True)
    print(
        f"Laden van ongeveer {min(max_days, estimated_days)} dagen echte historische data "
        f"(max_real_days={max_days}, target_trades={target})...",
        flush=True,
    )
    ep._write_first_boot_progress(
        "loading_data",
        "Laden van historische data voor first-boot training (CrossTrade / NT-historie).",
        target_trades=target,
        estimated_real_days=estimated_days,
        max_real_days=max_days,
        progress_pct=18,
        phase="loading_history",
    )

    container = ep.ApplicationContainer()
    ep._bind_headless_runtime_app(container)
    ep._write_first_boot_progress(
        "training_running",
        "First-boot pipeline gestart: data laden → parallel SIM → PPO.",
        target_trades=target,
        estimated_real_days=estimated_days,
        max_real_days=max_days,
        progress_pct=26,
        phase="pipeline_boot",
    )
    if not birth_phase_enabled:
        logging.warning("first_boot.birth_phase=false is ignored; LuminaBirthEngine is mandatory for first boot.")
    from lumina_core.birth.engine import BirthPhaseEngineV2 as LuminaBirthEngine

    engine = LuminaBirthEngine(
        runtime=container.engine,
        ppo_trainer=container.ppo_trainer,
        market_data_service=container.market_data_service,
        config={"first_boot": cfg},
        workspace_root=ep.ROOT_DIR,
    )
    birth_result = engine.run_birth_phase(
        target_trades=target,
        max_real_days=max_days,
        prefer_real_data_only=prefer_real,
    )
    birth_status = str(birth_result.get("status", "error")).strip().lower()
    if birth_status == "completed":
        mapped_status = "ok_birth_phase"
    elif birth_status == "paused":
        mapped_status = "paused"
    else:
        mapped_status = "birth_failed"
    report = {
        "status": mapped_status,
        "trades": int(birth_result.get("total_trades", 0) or 0),
        "synthetic_ticks": 0,
        "policy_path": str(birth_result.get("policy_path") or ep.FIRST_BOOT_POLICY_PATH),
    }
    status = str(report.get("status", "error"))
    trades = int(report.get("trades", 0) or 0)
    requested_norm = normalize_first_boot_training_trades(target)
    volume_met = trades >= requested_norm
    policy_ready = ep.FIRST_BOOT_POLICY_PATH.exists()

    if status == "paused":
        pause_msg = (
            f"First-boot training gepauzeerd op {trades:,}/{requested_norm:,} trades. "
            "Runtime blijft geblokkeerd totdat training wordt hervat en voltooid."
        )
        print(pause_msg, flush=True)
        ep._write_first_boot_progress(
            "paused",
            pause_msg,
            status=status,
            trades=trades,
            requested_trades=requested_norm,
            progress_pct=min(99.0, (100.0 * float(trades) / float(max(1, requested_norm)))),
        )
        return int(ep.FIRST_BOOT_EXIT_PAUSED)

    # Must reach the configured (snapped) trade volume — not only "ok" + some trades.
    # Otherwise ok_capped_real_only (~real-data cap) incorrectly completed first boot at ~67k vs 500k.
    if status.startswith("ok") and trades > 0 and volume_met and policy_ready:
        ep.FIRST_BOOT_FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ep.FIRST_BOOT_FLAG_PATH.write_text(datetime.now().isoformat(), encoding="utf-8")
        ep.FIRST_BOOT_LEGACY_FLAG_PATH.write_text(datetime.now().isoformat(), encoding="utf-8")
        synthetic_ticks = int(report.get("synthetic_ticks", 0) or 0)
        if synthetic_ticks > 0:
            done_message = (
                f"Eerste training voltooid met {trades} trades op basis van echte data "
                f"met minimale synthetische aanvulling ({synthetic_ticks} ticks). Policy opgeslagen."
            )
        else:
            done_message = f"Eerste training voltooid met {trades} trades op basis van echte data. Policy opgeslagen."
        print(
            done_message,
            flush=True,
        )
        ep._write_first_boot_progress(
            "completed",
            done_message,
            status=status,
            trades=trades,
            requested_trades=requested_norm,
            phase="completed",
        )
        logging.info("First boot training finished - starting normal runtime mode")
        return 0

    if status.startswith("ok") and trades > 0 and volume_met and not policy_ready:
        msg = (
            "First-boot SIM-volume is gehaald, maar PPO policy ontbreekt nog. "
            "Runtime blijft fail-closed; hervat training totdat policy is opgeslagen."
        )
        print(msg, flush=True)
        ep._write_first_boot_progress(
            "failed",
            msg,
            status="ppo_policy_missing",
            trades=trades,
            requested_trades=requested_norm,
            phase="ppo_training_failed",
        )
        logging.error("first_boot.policy_missing_after_volume status=%s trades=%s", status, trades)
        return 1

    if status.startswith("ok") and trades > 0 and not volume_met:
        msg = (
            f"First-boot pipeline stopte na {trades:,} trades; geconfigureerd zijn minimaal {requested_norm:,} trades "
            "nodig voordat live/paper-runtime mag starten. "
            "Runtime blijft fail-closed; hervat first-boot training totdat het doel volledig gehaald is."
        )
        print(msg, flush=True)
        ep._write_first_boot_progress(
            "failed_incomplete_volume",
            msg,
            status=status,
            trades=trades,
            requested_trades=requested_norm,
            progress_pct=min(99.0, (100.0 * float(trades) / float(max(1, requested_norm)))),
        )
        logging.warning(
            "first_boot.incomplete_volume trades=%s requested=%s status=%s",
            trades,
            requested_norm,
            status,
        )
        return 1

    print(
        f"First boot training is niet geslaagd (status={status}, trades={trades}). Runtime wordt fail-closed gestopt.",
        flush=True,
    )
    ep._write_first_boot_progress(
        "failed",
        "First boot training is niet geslaagd en runtime is fail-closed gestopt.",
        status=status,
        trades=trades,
        requested_trades=requested_norm,
    )
    return 1
