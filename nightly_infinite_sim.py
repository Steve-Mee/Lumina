# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from types import ModuleType
from types import SimpleNamespace

from dotenv import load_dotenv

from lumina_core.engine import EngineConfig, MarketDataService, MemoryService, SelfEvolutionMetaAgent
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.session_guard import SessionGuard
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_core.engine.self_evolution_meta_agent import load_evolution_config
from lumina_core.infinite_simulator import InfiniteSimulator
from lumina_core.logging_utils import build_logger
from lumina_core.monitoring import ObservabilityService
from lumina_core.ppo_trainer import PPOTrainer
from lumina_core.runtime_context import RuntimeContext


def _build_collection():
    try:
        import chromadb  # type: ignore

        client = chromadb.PersistentClient(path="lumina_vector_db")
        return client.get_or_create_collection("lumina_memories")
    except Exception:
        return None


def main() -> int:
    load_dotenv()

    config = EngineConfig()
    logger = build_logger("nightly_sim", log_level=os.getenv("LUMINA_LOG_LEVEL", "INFO"), file_path="logs/lumina_full_log.csv")
    app = ModuleType("nightly_infinite_sim_app")
    setattr(app, "logger", logger)
    setattr(app, "collection", _build_collection())

    # ── Start observability (no-op when monitoring.enabled = false) ────────────
    try:
        import yaml as _yaml
        with open(os.getenv("LUMINA_CONFIG", "config.yaml"), "r", encoding="utf-8") as _fh:
            _full_cfg = _yaml.safe_load(_fh) or {}
    except Exception:
        _full_cfg = {}
    obs = ObservabilityService.from_config(_full_cfg)
    obs.start()

    engine = LuminaEngine(config=config)
    engine.observability_service = obs
    runtime = RuntimeContext(engine=engine, app=app)

    market_data_service = MarketDataService(engine=engine)
    memory_service = MemoryService(engine=engine)
    ppo_trainer = PPOTrainer(engine=engine)

    setattr(app, "store_experience_to_vector_db", memory_service.store_experience_to_vector_db)
    setattr(app, "evolve_bible", engine.evolve_bible)
    setattr(app, "detect_market_regime", engine.detect_market_regime)

    simulator = InfiniteSimulator(
        runtime=runtime,
        market_data_service=market_data_service,
        ppo_trainer=ppo_trainer,
        workers=max(2, (os.cpu_count() or 4) - 1),
        target_trades_per_night=1_000_000,
    )

    if os.getenv("RUN_CHAOS_SUITE", "false").strip().lower() == "true":
        chaos_cmd = [
            "python",
            "-m",
            "pytest",
            "tests/chaos_engineering.py",
            "-m",
            "chaos_ci_nightly or chaos_ci_smoke",
            "-q",
            "--tb=short",
        ]
        logger.info("Running chaos suite before nightly simulation")
        result = subprocess.run(chaos_cmd, capture_output=True, text=True)
        if result.stdout:
            logger.info(result.stdout.strip())
        if result.stderr:
            logger.warning(result.stderr.strip())
        if result.returncode != 0:
            logger.error(f"Chaos suite failed with exit code {result.returncode}")
            return result.returncode

    session_cfg = getattr(config, "session", {}) if isinstance(getattr(config, "session", {}), dict) else {}
    enforce_calendar = bool(session_cfg.get("enforce_calendar", True))
    session_guard = SessionGuard(calendar_name="CME")

    market_open = session_guard.is_market_open()
    trading_session = session_guard.is_trading_session()
    rollover = session_guard.is_rollover_window()
    nxt_open = session_guard.next_open()
    nxt_close = session_guard.next_close()

    logger.info(
        "SessionGuard: open=%s trading=%s rollover=%s next_open=%s next_close=%s",
        market_open,
        trading_session,
        rollover,
        nxt_open.isoformat() if nxt_open else "n/a",
        nxt_close.isoformat() if nxt_close else "n/a",
    )

    dry_run_sim = os.getenv("LUMINA_DRY_RUN_SIM", "false").strip().lower() == "true"
    calendar_blocked = enforce_calendar and (not trading_session)

    if dry_run_sim or calendar_blocked:
        report = {
            "timestamp": datetime.now().isoformat(),
            "status": "calendar_blocked" if calendar_blocked else "dry_run",
            "trades": 0 if calendar_blocked else 240,
            "wins": 0 if calendar_blocked else 131,
            "net_pnl": 0.0 if calendar_blocked else 842.5,
            "mean_pnl": 0.0 if calendar_blocked else 3.51,
            "sharpe": 0.0 if calendar_blocked else 0.84,
            "samples": [
                {"reward": 0.32, "regime": "TRENDING"},
                {"reward": -0.14, "regime": "RANGING"},
                {"reward": 0.41, "regime": "VOLATILE"},
            ],
            "session_guard": {
                "now_utc": datetime.now(timezone.utc).isoformat(),
                "market_open": market_open,
                "trading_session": trading_session,
                "rollover_window": rollover,
                "next_open": nxt_open.isoformat() if nxt_open else None,
                "next_close": nxt_close.isoformat() if nxt_close else None,
            },
            "report_path": "dry_run",
        }
    else:
        report = simulator.run_nightly()

    # SIM learning boost: run extra aggressive pass on recent 24h + 7d windows.
    mode = str(os.getenv("LUMINA_MODE", "sim")).strip().lower()
    if mode == "sim":
        logger.warning("=== AGGRESSIVE SIM LEARNING BOOST – UNLIMITED BUDGET ===")
        logger.info("Building aggressive windows from historical ticks: last 24h + 7d")

        ticks_24h = simulator._load_real_historical_ticks(days_back=1, limit=200000)
        ticks_7d = simulator._load_real_historical_ticks(days_back=7, limit=600000)

        if not ticks_24h:
            ticks_24h = simulator._generate_synthetic_ticks(
                n_ticks=120000,
                seed=int(datetime.now(timezone.utc).timestamp()) % 1_000_000,
                start_price=5000.0,
            )
        if not ticks_7d:
            ticks_7d = simulator._generate_synthetic_ticks(
                n_ticks=420000,
                seed=(int(datetime.now(timezone.utc).timestamp()) + 1337) % 1_000_000,
                start_price=5000.0,
            )

        aggressive_target = max(120000, int(os.getenv("LUMINA_SIM_LEARNING_BOOST_TRADES", "120000")))
        aggressive_ticks = ticks_24h + ticks_7d
        boost_core = simulator._run_parallel_simulation(aggressive_ticks, aggressive_target)

        boost_report = {
            "trades": int(boost_core.get("trades", 0) or 0),
            "wins": int(boost_core.get("wins", 0) or 0),
            "net_pnl": float(boost_core.get("net_pnl", 0.0) or 0.0),
            "mean_pnl": float(boost_core.get("mean_pnl", 0.0) or 0.0),
            "sharpe": float(boost_core.get("mean_worker_sharpe", 0.0) or 0.0),
            "samples": (boost_core.get("sample_experiences", []) if isinstance(boost_core.get("sample_experiences"), list) else [])[:400],
            "boost": {
                "enabled": True,
                "window_24h": True,
                "window_7d": True,
                "aggressive_trades_target": aggressive_target,
                "aggressive_ticks_24h": len(ticks_24h),
                "aggressive_ticks_7d": len(ticks_7d),
                "executor": boost_core.get("executor", "unknown"),
            },
        }
        report["sim_learning_boost"] = boost_report
        report["trades"] = int(report.get("trades", 0) or 0) + int(boost_report["trades"])
        report["wins"] = int(report.get("wins", 0) or 0) + int(boost_report["wins"])
        report["net_pnl"] = float(report.get("net_pnl", 0.0) or 0.0) + float(boost_report["net_pnl"])
        report["sharpe"] = max(float(report.get("sharpe", 0.0) or 0.0), float(boost_report["sharpe"]))

    evo_cfg = load_evolution_config()
    evolution_container = SimpleNamespace(
        engine=engine,
        valuation_engine=getattr(engine, "valuation_engine", ValuationEngine()),
        risk_controller=getattr(engine, "risk_controller", None),
        ppo_trainer=ppo_trainer,
        rl_environment=getattr(engine, "rl_env", None),
    )
    sim_mode = str(evo_cfg.get("mode", os.getenv("LUMINA_MODE", "sim"))).strip().lower() == "sim"
    evolution_agent = SelfEvolutionMetaAgent.from_container(
        container=evolution_container,
        enabled=bool(evo_cfg.get("enabled", True)),
        approval_required=False if sim_mode else bool(evo_cfg.get("approval_required", True)),
        mode=str(evo_cfg.get("mode", os.getenv("LUMINA_MODE", "sim"))),
        aggressive_evolution=True if sim_mode else bool(evo_cfg.get("aggressive_evolution", False)),
        max_mutation_depth="radical" if sim_mode else str(evo_cfg.get("max_mutation_depth", "conservative")),
        obs_service=obs,
        fine_tuning_cfg=evo_cfg.get("fine_tuning", {}),
    )
    evolution_result = evolution_agent.run_nightly_evolution(
        nightly_report=report,
        dry_run=dry_run_sim,
    )
    report["evolution"] = evolution_result

    # ── Record evolution proposal to observability metrics ─────────────────────
    try:
        proposal = evolution_result.get("proposal", {})
        best = evolution_result.get("best_candidate") or {}
        obs.record_evolution_proposal(
            status=str(evolution_result.get("status", "unknown")),
            confidence=float(proposal.get("confidence", 0.0)),
            best_candidate=str(best.get("name", None)) if best else None,
        )
        net_pnl = float(report.get("net_pnl", 0.0) or 0.0)
        obs.record_pnl(daily=net_pnl)
    except Exception:
        pass

    obs.stop()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
