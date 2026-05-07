from __future__ import annotations
import logging

import argparse
import json
import os
import subprocess
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from lumina_core.bootstrap import bootstrap_runtime
from lumina_core.config_loader import ConfigLoader
from lumina_core.first_boot_ui import (
    FIRST_BOOT_DEFAULT_MAX_REAL_DAYS,
    FIRST_BOOT_DEFAULT_TRADES,
    estimate_first_boot_real_days,
    normalize_first_boot_training_trades,
)
from lumina_core.container import ApplicationContainer, create_application_container
from lumina_core.evolution.simulator_data_support import require_real_simulator_data_strict
from lumina_core.risk.session_guard import SessionGuard
from lumina_core.engine.sim_stability_checker import format_stability_report, generate_stability_report
from lumina_core.runtime.headless_runtime import HeadlessRuntime, parse_duration_minutes


ROOT_DIR = Path(__file__).resolve().parents[2]
FIRST_BOOT_FLAG_PATH = ROOT_DIR / "state" / "first_boot_completed.flag"
FIRST_BOOT_POLICY_PATH = ROOT_DIR / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
FIRST_BOOT_PROGRESS_PATH = ROOT_DIR / "state" / "first_boot_progress.json"


def _write_first_boot_progress(stage: str, message: str, **extra: object) -> None:
    prev: dict[str, object] = {}
    if FIRST_BOOT_PROGRESS_PATH.exists():
        try:
            prev = json.loads(FIRST_BOOT_PROGRESS_PATH.read_text(encoding="utf-8"))
            if not isinstance(prev, dict):
                prev = {}
        except Exception:
            prev = {}
    payload: dict[str, object] = dict(prev)
    payload["timestamp"] = datetime.now().isoformat()
    payload["stage"] = str(stage).strip().lower()
    payload["message"] = str(message)
    payload.update(extra)
    try:
        FIRST_BOOT_PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIRST_BOOT_PROGRESS_PATH.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    except Exception:
        logging.exception("first_boot.progress_write_failed")


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
        help="SIM only: run one-shot HeadlessRuntime (CI/smoke). Default SIM uses full bootstrap like REAL.",
    )
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


def _test_readiness_bypass_enabled(args: argparse.Namespace) -> bool:
    if not bool(getattr(args, "test_bypass_readiness_gate", False)):
        return False
    return str(os.getenv("LUMINA_TEST_MODE", "false")).strip().lower() in {"1", "true", "yes", "on"}


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


def _run_real_runtime(*, run_human_loop: bool = False) -> int:
    container = create_application_container()
    runtime_module = sys.modules.get("__main__")
    if runtime_module is not None:
        _bind_runtime_module(container, runtime_module)

    print(f"LUMINA runtime started (Mode: {container.config.trade_mode.upper()})")
    print(f"Swarm active on symbols: {', '.join(container.swarm_symbols)}")

    from lumina_core.logging_utils import flush_logger_handlers

    container.logger.info(
        f"RUNTIME_PRE_BOOTSTRAP,bound_app={bool(runtime_module is not None)},"
        f"trade_mode={getattr(container.config, 'trade_mode', '')},"
        f"broker_backend={getattr(container.config, 'broker_backend', '')}"
    )
    flush_logger_handlers(container.logger)

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
        # Historical OHLC for headless requires MarketDataService on the container; broker=paper
        # previously skipped container creation, which broke paper+sim when neuro strict mode is on.
        should_try_container = require_real_simulator_data_strict() or (
            str(args.broker).lower() == "live" and normalized_label != "paper"
        )
        if should_try_container:
            try:
                container = create_application_container()
                _bind_headless_runtime_app(container)
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


def _load_first_boot_config() -> dict[str, int | bool]:
    raw = ConfigLoader.section("first_boot", default={}) or {}
    cfg = raw if isinstance(raw, dict) else {}
    training_trades = normalize_first_boot_training_trades(cfg.get("training_trades", FIRST_BOOT_DEFAULT_TRADES))
    prefer_real_data_only = bool(cfg.get("prefer_real_data_only", True))
    max_real_days = int(cfg.get("max_real_days", FIRST_BOOT_DEFAULT_MAX_REAL_DAYS) or FIRST_BOOT_DEFAULT_MAX_REAL_DAYS)
    allow_minimal_synth = bool(cfg.get("allow_minimal_synthetic_fallback", False))
    force_training = bool(cfg.get("force_training", True))
    return {
        "training_trades": training_trades,
        "prefer_real_data_only": prefer_real_data_only,
        "max_real_days": max(30, min(3_650, max_real_days)),
        "allow_minimal_synthetic_fallback": allow_minimal_synth,
        "force_training": force_training,
    }


def _first_boot_needed() -> bool:
    cfg = _load_first_boot_config()
    force_training = bool(cfg.get("force_training", True))
    missing_flag = not FIRST_BOOT_FLAG_PATH.exists()
    missing_policy = not FIRST_BOOT_POLICY_PATH.exists()
    missing_artifacts = missing_flag or missing_policy
    logging.info(
        "first_boot.check force_training=%s missing_flag=%s missing_policy=%s",
        force_training,
        missing_flag,
        missing_policy,
    )
    if missing_artifacts and not force_training:
        logging.warning(
            "First boot artifacts ontbreken, maar first_boot.force_training=false; runtime gaat door zonder verplichte initiële training."
        )
        return False
    return missing_artifacts and force_training


def _defer_first_boot_for_closed_calendar() -> bool:
    """Skip mandatory first-boot training outside CME session when calendar enforcement is on.

    Mirrors nightly SIM behaviour: when the session calendar says closed, the stack should stay
    idle instead of starting a long CPU/network-heavy first-boot run.
    """
    try:
        raw = ConfigLoader.section("session", default={}) or {}
        if not isinstance(raw, dict):
            return False
        if not bool(raw.get("enforce_calendar", True)):
            return False
        guard = SessionGuard(calendar_name="CME")
        return not guard.is_trading_session()
    except Exception:
        logging.exception("first_boot.calendar_defer_check_failed")
        return False


def _run_first_boot_training() -> int:
    cfg = _load_first_boot_config()
    target = int(cfg["training_trades"])
    prefer_real = bool(cfg["prefer_real_data_only"])
    max_days = int(cfg["max_real_days"])
    allow_synth = bool(cfg["allow_minimal_synthetic_fallback"])
    estimated_days = estimate_first_boot_real_days(target)

    start_message = (
        "Eerste keer starten gedetecteerd. Lumina voert initiële training uit. "
        "Trading is tijdelijk geblokkeerd..."
    )
    logging.info("First boot detected - blocking trading until training complete")
    _write_first_boot_progress("detected", start_message, target_trades=target, max_real_days=max_days)
    print(start_message, flush=True)
    print(
        f"Laden van ongeveer {min(max_days, estimated_days)} dagen echte historische data "
        f"(max_real_days={max_days}, target_trades={target})...",
        flush=True,
    )
    _write_first_boot_progress(
        "loading_data",
        "Laden van historische data voor first-boot training (CrossTrade / NT-historie).",
        target_trades=target,
        estimated_real_days=estimated_days,
        max_real_days=max_days,
        progress_pct=18,
        phase="loading_history",
    )

    container = ApplicationContainer()
    _bind_headless_runtime_app(container)
    _write_first_boot_progress(
        "training_running",
        "First-boot pipeline gestart: data laden → parallel SIM → PPO.",
        target_trades=target,
        estimated_real_days=estimated_days,
        max_real_days=max_days,
        progress_pct=26,
        phase="pipeline_boot",
    )
    report = container.infinite_simulator.run_first_boot_training(
        target_trades=target,
        prefer_real_data_only=prefer_real,
        max_real_days=max_days,
        allow_minimal_synthetic_fallback=allow_synth,
    )
    status = str(report.get("status", "error"))
    trades = int(report.get("trades", 0) or 0)
    if status.startswith("ok") and trades > 0:
        FIRST_BOOT_FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        FIRST_BOOT_FLAG_PATH.write_text(datetime.now().isoformat(), encoding="utf-8")
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
        _write_first_boot_progress("completed", done_message, status=status, trades=trades)
        logging.info("First boot training finished - starting normal runtime mode")
        return 0
    print(
        f"First boot training is niet geslaagd (status={status}, trades={trades}). Runtime wordt fail-closed gestopt.",
        flush=True,
    )
    _write_first_boot_progress(
        "failed",
        "First boot training is niet geslaagd en runtime is fail-closed gestopt.",
        status=status,
        trades=trades,
    )
    return 1


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
        and not bool(args.stability_check)
    )
    if should_check_first_boot:
        if _first_boot_needed():
            if _defer_first_boot_for_closed_calendar():
                logging.info(
                    "first_boot deferred: geen actieve CME-handelssessie (enforce_calendar); "
                    "initiële training start niet tot RTH of na het uitschakelen van deze check."
                )
                _write_first_boot_progress(
                    "deferred_calendar",
                    "First-boot training uitgesteld: kalender staat op gesloten sessie. "
                    "Start tijdens reguliere handelsuren of zet session.enforce_calendar op false.",
                )
            else:
                first_boot_rc = _run_first_boot_training()
                if first_boot_rc != 0:
                    return first_boot_rc
        else:
            logging.info("first_boot.check runtime gate open; normale runtime start zonder verplichte first-boot training.")

    if resolved_mode == "nightly":
        return _run_nightly()

    # SIM / Paper: full runtime (bootstrap + supervisor + swarm dashboard) — same stack as REAL.
    # Risk caps come from config.yaml `sim:` vs `real:` via trade_mode in .env (paper/sim/sim_real_guard).
    # Use `--headless` only for CI/smoke one-shot HeadlessRuntime (no live supervisor loop).
    if resolved_mode == "sim":
        if bool(args.headless):
            requested_mode = str(args.mode).strip().lower()
            headless_mode_label = "paper" if requested_mode == "paper" else "sim"
            return _run_headless_sim(args, mode_label=headless_mode_label)
        os.environ.setdefault("LUMINA_ENFORCE_ENV_RUNTIME_MODE", "true")
        return _run_real_runtime(run_human_loop=bool(args.run_human_loop))

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
