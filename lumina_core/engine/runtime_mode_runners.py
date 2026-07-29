"""Mode runners extracted from runtime_entrypoint (behavior-preserving).

Headless / REAL / nightly paths. Façade monkeypatches are resolved via
``runtime_entrypoint`` at call time where tests require it.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import types
from datetime import datetime
from typing import Any

from lumina_core.bootstrap import bootstrap_runtime
from lumina_core.container import ApplicationContainer, create_application_container
from lumina_core.evolution.simulator_data_support import require_real_simulator_data_strict
from lumina_core.risk.session_guard import SessionGuard
from lumina_core.engine.sim_stability_checker import format_stability_report, generate_stability_report
from lumina_core.runtime.headless_runtime import HeadlessRuntime, parse_duration_minutes
from lumina_core.runtime.headless_production import HeadlessProductionOrchestrator
from lumina_core.runtime.production_config import load_production_section

_FACADE_MODULE = "lumina_core.engine.runtime_entrypoint"


def _ep() -> Any:
    mod = sys.modules.get(_FACADE_MODULE)
    if mod is not None:
        return mod
    from lumina_core.engine import runtime_entrypoint as ep

    return ep


def _test_readiness_bypass_enabled(args: argparse.Namespace) -> bool:
    if not bool(getattr(args, "test_bypass_readiness_gate", False)):
        return False
    return str(os.getenv("LUMINA_TEST_MODE", "false")).strip().lower() in {"1", "true", "yes", "on"}


def _smoke_mode_requested(args: argparse.Namespace) -> bool:
    """Return True when one-shot smoke path should run."""
    if bool(getattr(args, "smoke", False)):
        return True
    # Deprecation shim: --headless --duration without --smoke → smoke for one release cycle.
    if bool(getattr(args, "headless", False)) and not bool(getattr(args, "smoke", False)):
        duration = str(getattr(args, "duration", "15m") or "15m").strip()
        if duration and duration != "15m":
            logging.warning(
                "DEPRECATED: --headless --duration without --smoke runs smoke path. "
                "Use --smoke for CI validation or --headless alone for 24/7 production."
            )
            return True
    return bool(getattr(args, "stability_check", False)) and not bool(getattr(args, "headless", False))


def _load_production_cfg_override() -> dict | None:
    raw = str(os.getenv("LUMINA_HEADLESS_PRODUCTION_JSON", "") or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        logging.warning("Invalid LUMINA_HEADLESS_PRODUCTION_JSON; ignoring override")
        return None


def _run_headless_production(*, mode: str, run_human_loop: bool = False) -> int:
    """Continuous 24/7 production headless runtime."""
    normalized = str(mode or "sim").strip().lower()
    if normalized == "paper":
        normalized = "sim"
    override = _load_production_cfg_override()
    base_cfg = load_production_section()
    prod_cfg = {**base_cfg, **override} if override else None
    logging.info(
        "runtime_entrypoint: routing --headless to HeadlessProductionOrchestrator mode=%s",
        normalized,
    )
    orchestrator = HeadlessProductionOrchestrator(
        mode=normalized,
        run_human_loop=run_human_loop,
        prod_cfg=prod_cfg,
    )
    return int(orchestrator.run())


def _bind_runtime_module(container: ApplicationContainer, runtime_module) -> None:
    container.bind_runtime_module(runtime_module)


def _bind_headless_runtime_app(container: ApplicationContainer) -> None:
    """Headless / first-boot historical fetch: MarketDataIngestService._app() requires a bound module.

    Crosstrade bar requests use ``CROSSTRADE_TOKEN`` and ``INSTRUMENT`` from the runtime app; without
    these, ``load_historical_ohlc_extended`` raises when resolving the app.
    """
    stub = types.ModuleType("lumina_headless_runtime_app")
    cfg = getattr(container, "config", None)
    stub.logger = getattr(container, "logger", logging.getLogger("lumina.stub_runtime"))
    if cfg is None:
        inst = str(os.getenv("LUMINA_INSTRUMENT", "") or "MES").strip() or "MES"
        stub.INSTRUMENT = inst
        stub.CROSSTRADE_TOKEN = str(os.getenv("CROSSTRADE_TOKEN", ""))
        stub.CROSSTRADE_ACCOUNT = str(os.getenv("CROSSTRADE_ACCOUNT", ""))
        stub.SWARM_SYMBOLS = [inst]
    else:
        inst = str(getattr(cfg, "instrument", None) or "MES")
        stub.INSTRUMENT = inst
        stub.CROSSTRADE_TOKEN = str(os.getenv("CROSSTRADE_TOKEN", "") or getattr(cfg, "crosstrade_token", "") or "")
        stub.CROSSTRADE_ACCOUNT = str(
            os.getenv("CROSSTRADE_ACCOUNT", "") or getattr(cfg, "crosstrade_account", "") or ""
        )
        swarm = getattr(cfg, "swarm_symbols", None)
        if swarm:
            stub.SWARM_SYMBOLS = [str(s).strip() for s in swarm]
        else:
            stub.SWARM_SYMBOLS = [inst]
    stub.FAST_PATH_ONLY = False
    container.engine.bind_app(stub)
    container.runtime_context.app = stub


def _start_live_runtime(container: ApplicationContainer, *, run_human_loop: bool = False) -> int:
    """Bootstrap long-running runtime services and optional config hot-reload watcher."""
    from lumina_core.logging_utils import flush_logger_handlers

    container.logger.info(
        f"RUNTIME_PRE_BOOTSTRAP,bound_app={bool(getattr(container, 'runtime_context', None) is not None)},"
        f"trade_mode={getattr(container.config, 'trade_mode', '')},"
        f"broker_backend={getattr(container.config, 'broker_backend', '')}"
    )
    flush_logger_handlers(container.logger)

    bootstrap_runtime(container)

    if run_human_loop or bool(container.config.use_human_main_loop):
        print("Human-like main loop starting...")
        import threading

        threading.Thread(target=container.analysis_service.run_main_loop, daemon=True).start()

    container.start_config_hot_reload()
    container.operations_service.run_forever_loop()
    return 0


def _run_real_runtime(*, run_human_loop: bool = False) -> int:
    ep = _ep()
    container = create_application_container()
    runtime_module = sys.modules.get("__main__")
    if runtime_module is not None:
        ep._bind_runtime_module(container, runtime_module)

    print(f"LUMINA runtime started (Mode: {container.config.trade_mode.upper()})")
    print(f"Swarm active on symbols: {', '.join(container.swarm_symbols)}")

    return ep._start_live_runtime(container, run_human_loop=run_human_loop)


def _run_headless_sim(args: argparse.Namespace, *, mode_label: str = "sim") -> int:
    logging.info(
        "runtime_entrypoint: routing --smoke to HeadlessRuntime mode=%s",
        mode_label,
    )
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
    ep = _ep()

    try:
        os.environ["LUMINA_MODE"] = normalized_label
        os.environ["TRADE_MODE"] = normalized_label
        os.environ["LUMINA_ENFORCE_ENV_RUNTIME_MODE"] = "true"
        os.environ["BROKER_BACKEND"] = str(args.broker).strip().lower()

        # ConfigLoader requires trade_mode=sim with broker_backend=live; headless can still use
        # --broker paper for validation/stub paths while the container loads historical OHLC.
        _container_broker_override = (
            require_real_simulator_data_strict()
            and normalized_label == "sim"
            and str(args.broker).strip().lower() == "paper"
        )
        if _container_broker_override:
            os.environ["BROKER_BACKEND"] = "live"
            os.environ.setdefault("CROSSTRADE_TOKEN", "headless-sim-stub")

        os.environ["LUMINA_AGGRESSIVE_SIM"] = "true" if bool(args.aggressive_sim) else "false"
        os.environ["LUMINA_SIM_OVERNIGHT"] = "true" if bool(args.overnight_sim) else "false"
        os.environ["LUMINA_STABILITY_CHECK"] = "true" if bool(args.stability_check) else "false"
        os.environ["LUMINA_TEST_BYPASS_READINESS_GATE"] = (
            "true" if ep._test_readiness_bypass_enabled(args) and normalized_label == "sim" else "false"
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
        # Historical OHLC for headless requires MarketDataService on the container; broker=paper
        # previously skipped container creation, which broke paper+sim when neuro strict mode is on.
        should_try_container = require_real_simulator_data_strict() or (
            str(args.broker).lower() == "live" and normalized_label != "paper"
        )
        if should_try_container:
            try:
                container = create_application_container()
                ep._bind_headless_runtime_app(container)
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/engine/runtime_entrypoint.py:233")
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
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/runtime_entrypoint.py:304")
        print(str(report))
    return 0
