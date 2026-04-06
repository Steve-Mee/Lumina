# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import json
import os
import subprocess
from types import ModuleType

from dotenv import load_dotenv

from lumina_core.engine import EngineConfig, MarketDataService, MemoryService
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.infinite_simulator import InfiniteSimulator
from lumina_core.logging_utils import build_logger
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

    engine = LuminaEngine(config=config)
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

    report = simulator.run_nightly()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
