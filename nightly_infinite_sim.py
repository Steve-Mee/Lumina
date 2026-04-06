# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from types import ModuleType
from types import SimpleNamespace

from dotenv import load_dotenv

from lumina_core.engine import EngineConfig, MarketDataService, MemoryService, SelfEvolutionMetaAgent
from lumina_core.engine.lumina_engine import LuminaEngine
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

    dry_run_sim = os.getenv("LUMINA_DRY_RUN_SIM", "false").strip().lower() == "true"
    if dry_run_sim:
        report = {
            "timestamp": datetime.now().isoformat(),
            "status": "dry_run",
            "trades": 240,
            "wins": 131,
            "net_pnl": 842.5,
            "mean_pnl": 3.51,
            "sharpe": 0.84,
            "samples": [
                {"reward": 0.32, "regime": "TRENDING"},
                {"reward": -0.14, "regime": "RANGING"},
                {"reward": 0.41, "regime": "VOLATILE"},
            ],
            "report_path": "dry_run",
        }
    else:
        report = simulator.run_nightly()

    evo_cfg = load_evolution_config()
    evolution_container = SimpleNamespace(
        engine=engine,
        valuation_engine=getattr(engine, "valuation_engine", ValuationEngine()),
        risk_controller=getattr(engine, "risk_controller", None),
    )
    evolution_agent = SelfEvolutionMetaAgent.from_container(
        container=evolution_container,
        enabled=bool(evo_cfg.get("enabled", True)),
        approval_required=bool(evo_cfg.get("approval_required", True)),
        obs_service=obs,
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
