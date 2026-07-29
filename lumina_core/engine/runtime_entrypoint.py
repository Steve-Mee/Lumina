"""Lumina runtime entrypoint.

Routing:
  --smoke              One-shot HeadlessRuntime CI/smoke validation
  --headless           Continuous 24/7 HeadlessProductionOrchestrator

Recommended 24/7 production invocation::

    LUMINA_ENTRYPOINT_ARGS="--headless --mode real" python watchdog.py

Optional production config override via ``LUMINA_HEADLESS_PRODUCTION_JSON`` (JSON object).
Enable dual telemetry with ``LUMINA_LAUNCHER_TELEMETRY=1`` and ``monitoring.webhook`` in config.yaml.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Sequence

from dotenv import load_dotenv

from lumina_core.config_loader import ConfigLoader
from lumina_core.container import ApplicationContainer
from lumina_core.engine.runtime_first_boot import (
    FIRST_BOOT_EXIT_PAUSED,
    FIRST_BOOT_FLAG_PATH,
    FIRST_BOOT_LEGACY_FLAG_PATH,
    FIRST_BOOT_LEGACY_PROGRESS_PATH,
    FIRST_BOOT_POLICY_PATH,
    FIRST_BOOT_PROGRESS_PATH,
    ROOT_DIR,
    _first_boot_needed,
    _load_first_boot_config,
    _run_first_boot_training,
    _write_first_boot_progress,
)
from lumina_core.engine.runtime_mode_runners import (
    _bind_headless_runtime_app,
    _bind_runtime_module,
    _load_production_cfg_override,
    _run_headless_production,
    _run_headless_sim,
    _run_nightly,
    _run_real_runtime,
    _smoke_mode_requested,
    _start_live_runtime,
    _test_readiness_bypass_enabled,
)

# Re-exports retained for monkeypatch / external importers (birth_runner, ppo_callbacks, tests).
__all__ = [
    "ROOT_DIR",
    "FIRST_BOOT_FLAG_PATH",
    "FIRST_BOOT_LEGACY_FLAG_PATH",
    "FIRST_BOOT_POLICY_PATH",
    "FIRST_BOOT_PROGRESS_PATH",
    "FIRST_BOOT_LEGACY_PROGRESS_PATH",
    "FIRST_BOOT_EXIT_PAUSED",
    "ConfigLoader",
    "ApplicationContainer",
    "_write_first_boot_progress",
    "_load_first_boot_config",
    "_first_boot_needed",
    "_run_first_boot_training",
    "_bind_headless_runtime_app",
    "_bind_runtime_module",
    "_load_production_cfg_override",
    "_run_headless_production",
    "_run_headless_sim",
    "_run_nightly",
    "_run_real_runtime",
    "_smoke_mode_requested",
    "_start_live_runtime",
    "_test_readiness_bypass_enabled",
    "_normalize_runtime_mode",
    "_resolve_mode",
    "_build_parser",
    "_route_resolved_mode",
    "run_with_mode",
    "main",
]


def _normalize_runtime_mode(raw_mode: str | None) -> str:
    mode = str(raw_mode or "").strip().lower()
    aliases = {
        "paper": "sim",
        "sim": "sim",
        "simulation": "sim",
        "sim_real_guard": "real",
        "real": "real",
        "live": "real",
        "nightly": "nightly",
    }
    return aliases.get(mode, "real")


def _resolve_mode(cli_mode: str, sim_only: bool, real_safe: bool, mode_hint: str) -> str:
    if sim_only:
        return "sim"
    if real_safe:
        return "real"
    if cli_mode and cli_mode != "auto":
        return _normalize_runtime_mode(cli_mode)

    if mode_hint and mode_hint != "auto":
        return _normalize_runtime_mode(mode_hint)

    env_mode = os.getenv("LUMINA_MODE") or os.getenv("TRADE_MODE")
    if env_mode:
        return _normalize_runtime_mode(env_mode)

    return "real"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runtime_entrypoint",
        description="Central Lumina runtime launcher",
    )
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "sim", "real", "nightly", "paper", "sim_real_guard", "live"],
        help="Runtime mode (default: auto).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Continuous 24/7 production headless runtime (full supervisor stack).",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="One-shot HeadlessRuntime smoke/CI validation (replaces legacy --headless --duration).",
    )
    parser.add_argument("--sim-only", action="store_true", help="Force SIM runtime behavior.")
    parser.add_argument("--real-safe", action="store_true", help="Force REAL runtime with safety gates.")
    parser.add_argument("--duration", default="15m", help="Smoke simulated duration (e.g. 15m, 1h). Requires --smoke.")
    parser.add_argument("--broker", choices=["paper", "live"], default="paper", help="Headless broker backend.")
    parser.add_argument("--aggressive-sim", action="store_true", help="Enable aggressive SIM profile in headless mode.")
    parser.add_argument("--overnight-sim", action="store_true", help="Enable overnight SIM profile in headless mode.")
    parser.add_argument("--stability-check", action="store_true", help="Run SIM stability checker report.")
    parser.add_argument(
        "--run-human-loop",
        action="store_true",
        help="Start human-like analysis loop in REAL runtime path.",
    )
    parser.add_argument(
        "--test-bypass-readiness-gate",
        action="store_true",
        help="Test-only: bypass SIM readiness gate when LUMINA_TEST_MODE=true.",
    )
    parser.add_argument(
        "--parallel-realities",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Multi-reality stress-universa voor evolutie-SIM (1–50; overschrijft config en sessiebestand). "
            "Zie ook LUMINA_PARALLEL_REALITIES in .env."
        ),
    )
    parser.add_argument(
        "--set-ohlc-dna-stress",
        type=int,
        choices=[0, 1],
        default=None,
        help="DNA-evolutie OHLC-stress: 0=uit, 1=aan (LUMINA_OHLC_DNA_STRESS).",
    )
    parser.add_argument(
        "--set-neuro-ohlc-rollouts",
        type=int,
        choices=[0, 1],
        default=None,
        help="PPO meerdere OHLC-rollouts: 0=uit, 1=aan (LUMINA_NEURO_OHLC_ROLLOUTS; zwaar).",
    )
    return parser


def _route_resolved_mode(args: argparse.Namespace, resolved_mode: str) -> int:
    """Dispatch post-first-boot runtime by resolved mode / CLI flags."""
    if resolved_mode == "nightly":
        return _run_nightly()

    if _smoke_mode_requested(args):
        requested_mode = str(args.mode).strip().lower()
        headless_mode_label = "paper" if requested_mode == "paper" else resolved_mode
        if headless_mode_label == "real":
            headless_mode_label = "sim"
        return _run_headless_sim(args, mode_label=headless_mode_label)

    if bool(args.headless):
        return _run_headless_production(
            mode=resolved_mode,
            run_human_loop=bool(args.run_human_loop),
        )

    # SIM / Paper: full runtime (bootstrap + supervisor + swarm dashboard) — same stack as REAL.
    if resolved_mode == "sim":
        os.environ.setdefault("LUMINA_ENFORCE_ENV_RUNTIME_MODE", "true")
        return _run_real_runtime(run_human_loop=bool(args.run_human_loop))

    if bool(args.real_safe):
        os.environ.setdefault("LUMINA_REAL_SAFE", "true")

    os.environ.setdefault("LUMINA_MODE", "real")
    os.environ.setdefault("TRADE_MODE", "real")
    return _run_real_runtime(run_human_loop=bool(args.run_human_loop))


def run_with_mode(mode_hint: str, argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args, _ = parser.parse_known_args(list(argv or []))

    if getattr(args, "parallel_realities", None) is not None:
        from lumina_core.evolution.parallel_reality_config import apply_env_parallel_realities

        apply_env_parallel_realities(int(args.parallel_realities))

    if (
        getattr(args, "set_ohlc_dna_stress", None) is not None
        or getattr(args, "set_neuro_ohlc_rollouts", None) is not None
    ):
        from lumina_core.evolution.bot_stress_choices import apply_env_stress_flags

        apply_env_stress_flags(
            getattr(args, "set_ohlc_dna_stress", None),
            getattr(args, "set_neuro_ohlc_rollouts", None),
        )

    if bool(args.sim_only) and bool(args.real_safe):
        parser.error("--sim-only and --real-safe cannot be combined")

    resolved_mode = _resolve_mode(str(args.mode), bool(args.sim_only), bool(args.real_safe), mode_hint)

    should_check_first_boot = (
        resolved_mode in {"sim", "real"}
        and not bool(args.headless)
        and not _smoke_mode_requested(args)
        and not bool(args.stability_check)
    )
    first_boot_ran = False
    if should_check_first_boot:
        if _first_boot_needed():
            first_boot_rc = _run_first_boot_training()
            if first_boot_rc != 0:
                return first_boot_rc
            first_boot_ran = True
        else:
            logging.info("first_boot.check runtime gate open; normale runtime start zonder verplichte first-boot training.")
    if first_boot_ran:
        _write_first_boot_progress(
            "completed_waiting_user_action",
            "First-boot training is voltooid. Runtime stopt nu fail-safe; start bot handmatig voor trading.",
            phase="completed_waiting_user_action",
        )
        logging.info("first_boot.complete fail-safe stop active; runtime exits and waits for explicit user start")
        return 0

    return _route_resolved_mode(args, resolved_mode)


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv(ROOT_DIR / ".env")
    return run_with_mode("auto", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
