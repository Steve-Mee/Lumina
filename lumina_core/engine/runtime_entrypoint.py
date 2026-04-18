from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from lumina_core.bootstrap import bootstrap_runtime
from lumina_core.container import ApplicationContainer, create_application_container
from lumina_core.engine.session_guard import SessionGuard
from lumina_core.engine.sim_stability_checker import format_stability_report, generate_stability_report
from lumina_core.runtime.headless_runtime import HeadlessRuntime, parse_duration_minutes


ROOT_DIR = Path(__file__).resolve().parents[2]


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
    parser.add_argument("--headless", action="store_true", help="Run non-UI headless runtime path.")
    parser.add_argument("--sim-only", action="store_true", help="Force SIM runtime behavior.")
    parser.add_argument("--real-safe", action="store_true", help="Force REAL runtime with safety gates.")
    parser.add_argument("--duration", default="15m", help="Headless simulated duration (e.g. 15m, 1h).")
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
    return parser


def _test_readiness_bypass_enabled(args: argparse.Namespace) -> bool:
    if not bool(getattr(args, "test_bypass_readiness_gate", False)):
        return False
    return str(os.getenv("LUMINA_TEST_MODE", "false")).strip().lower() in {"1", "true", "yes", "on"}


def _bind_runtime_module(container: ApplicationContainer, runtime_module) -> None:
    container.engine.bind_app(runtime_module)
    container.runtime_context.app = runtime_module


def _run_real_runtime(*, run_human_loop: bool = False) -> int:
    container = create_application_container()
    runtime_module = sys.modules.get("__main__")
    if runtime_module is not None:
        _bind_runtime_module(container, runtime_module)

    print(f"LUMINA runtime started (Mode: {container.config.trade_mode.upper()})")
    print(f"Swarm active on symbols: {', '.join(container.swarm_symbols)}")

    bootstrap_runtime(container)

    if run_human_loop or bool(container.config.use_human_main_loop):
        print("Human-like main loop starting...")
        import threading

        threading.Thread(target=container.analysis_service.run_main_loop, daemon=True).start()

    container.operations_service.run_forever_loop()
    return 0


def _run_headless_sim(args: argparse.Namespace, *, mode_label: str = "sim") -> int:
    normalized_label = (
        "sim" if str(mode_label).strip().lower() not in {"paper", "sim"} else str(mode_label).strip().lower()
    )
    managed_keys = [
        "LUMINA_MODE",
        "TRADE_MODE",
        "LUMINA_ENFORCE_ENV_RUNTIME_MODE",
        "BROKER_BACKEND",
        "LUMINA_AGGRESSIVE_SIM",
        "LUMINA_SIM_OVERNIGHT",
        "LUMINA_STABILITY_CHECK",
        "VOICE_ENABLED",
        "LUMINA_JWT_SECRET_KEY",
        "CROSSTRADE_TOKEN",
        "LUMINA_TEST_BYPASS_READINESS_GATE",
    ]
    previous_env = {key: os.environ.get(key) for key in managed_keys}

    try:
        os.environ["LUMINA_MODE"] = normalized_label
        os.environ["TRADE_MODE"] = normalized_label
        os.environ["LUMINA_ENFORCE_ENV_RUNTIME_MODE"] = "true"
        os.environ["BROKER_BACKEND"] = str(args.broker).strip().lower()

        os.environ["LUMINA_AGGRESSIVE_SIM"] = "true" if bool(args.aggressive_sim) else "false"
        os.environ["LUMINA_SIM_OVERNIGHT"] = "true" if bool(args.overnight_sim) else "false"
        os.environ["LUMINA_STABILITY_CHECK"] = "true" if bool(args.stability_check) else "false"
        os.environ["LUMINA_TEST_BYPASS_READINESS_GATE"] = (
            "true" if _test_readiness_bypass_enabled(args) and normalized_label == "sim" else "false"
        )

        os.environ.setdefault("VOICE_ENABLED", "False")
        os.environ.setdefault("LUMINA_JWT_SECRET_KEY", "headless-validation-jwt-secret")
        if str(args.broker).lower() == "live":
            os.environ.setdefault("CROSSTRADE_TOKEN", "headless-validation-stub")

        if bool(args.stability_check) and not bool(args.headless):
            report = generate_stability_report(limit=0)
            print(format_stability_report(report, color=True), flush=True)
            return 0

        duration_minutes = parse_duration_minutes(str(args.duration))

        container: ApplicationContainer | None = None
        should_try_container = str(args.broker).lower() == "live" and normalized_label != "paper"
        if should_try_container:
            try:
                container = create_application_container()
            except Exception:
                container = None

        runtime = HeadlessRuntime(container=container)
        runtime.run(
            duration_minutes=duration_minutes,
            mode=normalized_label,
            broker_mode=str(args.broker),
            aggressive_sim=bool(args.aggressive_sim),
            overnight_sim=bool(args.overnight_sim),
            stability_check=bool(args.stability_check),
        )
        return 0
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_nightly() -> int:
    os.environ.setdefault("LUMINA_MODE", "sim")
    os.environ.setdefault("TRADE_MODE", "sim")
    os.environ["BROKER_BACKEND"] = "live"
    os.environ.setdefault("CROSSTRADE_TOKEN", "nightly-sim-stub")

    # Nightly orchestration does not require an active broker session.
    container = ApplicationContainer()
    logger = container.logger

    run_chaos_suite = os.getenv("RUN_CHAOS_SUITE", "false").strip().lower() == "true"
    if run_chaos_suite:
        chaos_cmd = [
            sys.executable,
            "-m",
            "pytest",
            "tests/chaos_engineering.py",
            "-m",
            "chaos_ci_nightly or chaos_ci_smoke",
            "-q",
            "--tb=short",
        ]
        logger.info("Running chaos suite before nightly simulation")
        result = subprocess.run(chaos_cmd, check=False, capture_output=True, text=True)
        if result.stdout:
            logger.info(result.stdout.strip())
        if result.stderr:
            logger.warning(result.stderr.strip())
        if result.returncode != 0:
            logger.error("Chaos suite failed with exit code %s", result.returncode)
            return int(result.returncode)

    enforce_calendar = bool(getattr(container.config, "session", {}).get("enforce_calendar", True))
    session_guard = SessionGuard(calendar_name="CME")
    dry_run_sim = os.getenv("LUMINA_DRY_RUN_SIM", "false").strip().lower() == "true"
    calendar_blocked = enforce_calendar and (not session_guard.is_trading_session())

    if dry_run_sim or calendar_blocked:
        report = {
            "timestamp": datetime.now().isoformat(),
            "status": "calendar_blocked" if calendar_blocked else "dry_run",
            "trades": 0 if calendar_blocked else 240,
            "wins": 0 if calendar_blocked else 131,
            "net_pnl": 0.0 if calendar_blocked else 842.5,
        }
    else:
        report = container.infinite_simulator.run_nightly()

    try:
        print(json.dumps(report, indent=2))
    except Exception:
        print(str(report))
    return 0


def run_with_mode(mode_hint: str, argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args, _ = parser.parse_known_args(list(argv or []))

    if bool(args.sim_only) and bool(args.real_safe):
        parser.error("--sim-only and --real-safe cannot be combined")

    resolved_mode = _resolve_mode(str(args.mode), bool(args.sim_only), bool(args.real_safe), mode_hint)

    if resolved_mode == "nightly":
        return _run_nightly()

    if resolved_mode == "sim":
        if not args.headless:
            args.headless = True
        requested_mode = str(args.mode).strip().lower()
        headless_mode_label = "paper" if requested_mode == "paper" else "sim"
        return _run_headless_sim(args, mode_label=headless_mode_label)

    if bool(args.real_safe):
        os.environ.setdefault("LUMINA_REAL_SAFE", "true")

    os.environ.setdefault("LUMINA_MODE", "real")
    os.environ.setdefault("TRADE_MODE", "real")
    return _run_real_runtime(run_human_loop=bool(args.run_human_loop))


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv(ROOT_DIR / ".env")
    return run_with_mode("auto", argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
