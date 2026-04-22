# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

from datetime import datetime
import inspect
import os
import time
from typing import Any, Dict

import numpy as np
import pandas as pd

try:
    import ray as _ray  # type: ignore[reportMissingImports]
except ImportError:  # pragma: no cover - optional dependency for minimal test envs
    _ray = None

from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.simulator_data_support import MIN_SIMULATOR_BARS, require_real_simulator_data_strict
from lumina_core.runtime_context import RuntimeContext
from lumina_core.engine.realistic_backtester_engine import RealisticBacktesterEngine
from lumina_core.engine.advanced_backtester_engine import AdvancedBacktesterEngine

# ``run_backtest_on_snapshot`` needs enough rows before the loop start index (60).
_MIN_BACKTEST_WINDOW = 120


def _simulate_chunk_impl(
    chunk_id: int,
    base_df: pd.DataFrame,
    num_trades: int,
    context: RuntimeContext,
    historical_only: bool = False,
    rng_seed: int = 0,
) -> list[Dict[str, Any]]:
    """Parallel chunk voor miljoenen trades."""
    simulator = RealisticBacktesterEngine(context)  # realistische slippage etc.
    results: list[Dict[str, Any]] = []
    rng = np.random.RandomState((int(chunk_id) * 100003 + int(rng_seed)) % (2**31))

    if historical_only:
        n_base = len(base_df)
        if n_base < _MIN_BACKTEST_WINDOW:
            return results

    for _ in range(num_trades):
        if historical_only:
            max_win = min(4000, n_base)
            min_win = min(_MIN_BACKTEST_WINDOW, max_win)
            if max_win < min_win:
                continue
            win = int(rng.randint(min_win, max_win + 1))
            start = int(rng.randint(0, max(1, n_base - win + 1)))
            slice_df = base_df.iloc[start : start + win].copy()
            if "timestamp" not in slice_df.columns:
                slice_df = slice_df.reset_index()
            current_regime = "HISTORICAL"
            res = simulator.run_backtest_on_snapshot(slice_df)
        else:
            synthetic = base_df.copy()

            regimes = ["TRENDING", "BREAKOUT", "VOLATILE", "RANGING", "NEUTRAL"]
            current_regime = str(np.random.choice(regimes))
            regime_seq = [current_regime]
            for _ in range(len(synthetic) - 1):
                if np.random.rand() < 0.15:
                    current_regime = str(np.random.choice(regimes))
                regime_seq.append(current_regime)
            synthetic["regime"] = regime_seq

            noise = np.random.normal(0, 0.0008, len(synthetic))
            synthetic["close"] += noise * synthetic["close"]
            synthetic["high"] = synthetic["close"] + abs(noise) * 1.4
            synthetic["low"] = synthetic["close"] - abs(noise) * 1.2

            if np.random.rand() < 0.12 and len(synthetic) > 400:
                gap_idx = int(np.random.randint(200, len(synthetic) - 200))
                gap_size = float(np.random.normal(0, 0.012) * synthetic["close"].iloc[gap_idx])
                synthetic.loc[gap_idx:, "open"] = synthetic.loc[gap_idx:, "open"] + gap_size
                synthetic.loc[gap_idx:, "close"] = synthetic.loc[gap_idx:, "close"] + gap_size

            res = simulator.run_backtest_on_snapshot(synthetic)
            current_regime = str(regime_seq[-1]) if regime_seq else "NEUTRAL"

        total_pnl = float(res.get("total_pnl", res.get("net_pnl", 0.0)))
        results.append(
            {
                "chunk_id": chunk_id,
                "sharpe": float(res.get("sharpe", 0.0)),
                "winrate": float(res.get("winrate", 0.0)),
                "maxdd": float(res.get("maxdd", 0.0)),
                "total_pnl": total_pnl,
                "trades": int(res.get("trades", 0)),
                "regime": current_regime,
            }
        )

    return results


RAY_AVAILABLE = _ray is not None
if RAY_AVAILABLE:
    SIMULATE_CHUNK_REMOTE: Any = _ray.remote(_simulate_chunk_impl)  # type: ignore[union-attr]
else:
    SIMULATE_CHUNK_REMOTE = None

# Plain callable for tests and callers that expect a local function.
simulate_chunk = _simulate_chunk_impl


class InfiniteSimulator:
    """
    1000+ jaar data simulatie - miljoenen trades per nacht.
    Parallel via Ray (GPU/CPU).
    """

    def __init__(self, context: RuntimeContext):
        self.context = context
        self.logger = context.logger
        self.advanced = AdvancedBacktesterEngine(context)
        self.realistic = RealisticBacktesterEngine(context)
        # Future-proof Ray behavior for zero-GPU init and silence known warning noise.
        os.environ.setdefault("RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO", "0")
        if RAY_AVAILABLE and _ray is not None and not _ray.is_initialized():  # type: ignore[union-attr]
            _ray.init(ignore_reinit_error=True, num_cpus=8)  # type: ignore[union-attr]

    def generate_synthetic_data(self, base_df: pd.DataFrame, years: int = 1000) -> pd.DataFrame:
        """Base real data + 1000 jaar synthetic uitbreiding."""
        synthetic = base_df.copy()
        # Herhaal en voeg variatie toe
        full = pd.concat([synthetic] * (years * 252 // len(synthetic) + 1), ignore_index=True)
        return full.iloc[: len(full) // 10]  # beperk voor snelheid, maar schaalbaar

    def run_nightly_simulation(self, num_trades_total: int = 1_000_000) -> pd.DataFrame:
        """Hoofdmethode - run dit 's nachts."""
        start_time = datetime.now()
        print(f"[{start_time.strftime('%H:%M:%S')}] 🌌 INFINITE SIMULATOR STARTED - {num_trades_total:,} trades")

        historical_only = require_real_simulator_data_strict()
        base_df = self._resolve_base_ohlc_df(historical_only=historical_only)
        if historical_only and (base_df is None or len(base_df) < _MIN_BACKTEST_WINDOW):
            self.logger.warning(
                "Infinite simulator: insufficient historical OHLC (%s rows); skipping parallel chunks.",
                0 if base_df is None else len(base_df),
            )
            return pd.DataFrame()

        rng_seed = int(time.time()) % 1_000_000
        chunk_size = max(1, num_trades_total // 32)
        if RAY_AVAILABLE and SIMULATE_CHUNK_REMOTE is not None:
            futures = [
                SIMULATE_CHUNK_REMOTE.remote(
                    i,
                    base_df,
                    chunk_size,
                    self.context,
                    historical_only,
                    rng_seed,
                )
                for i in range(32)
            ]
            all_results = _ray.get(futures)  # type: ignore[union-attr]
        else:
            self.logger.warning("Ray not installed or disabled; infinite simulator runs chunks sequentially.")
            all_results = [
                _simulate_chunk_impl(i, base_df, chunk_size, self.context, historical_only, rng_seed)
                for i in range(32)
            ]
        flat_results = [item for sublist in all_results for item in sublist]

        # Verwerk resultaten
        df_results = pd.DataFrame(flat_results)

        # Update vector DB met ervaringen
        for _, row in df_results.iterrows():
            self.context.store_experience_to_vector_db(
                context=(
                    f"Infinite sim trade - Regime {row['regime']} | Sharpe {row['sharpe']:.2f} | PnL {row['total_pnl']}"
                ),
                metadata={
                    "type": "infinite_simulation",
                    "sharpe": float(row["sharpe"]),
                    "maxdd": float(row["maxdd"]),
                    "winrate": float(row["winrate"]),
                    "date": datetime.now().isoformat(),
                },
            )

        # Bible + RL update
        avg_sharpe = float(df_results["sharpe"].mean()) if not df_results.empty else 0.0
        if avg_sharpe > 1.5:
            self.context.dna_rewrite_daemon()  # forceer bible update
            self._maybe_retrain_ppo(base_df)

        duration = (datetime.now() - start_time).total_seconds() / 60
        self.logger.info(
            f"INFINITE_SIM_COMPLETE,trades={len(flat_results)},avg_sharpe={avg_sharpe:.2f},duration_min={duration:.1f}"
        )

        print(f"✅ INFINITE SIM COMPLETE in {duration:.1f} min")
        if not df_results.empty:
            print(f"   Avg Sharpe          : {avg_sharpe:.2f}")
            print(f"   Worst MaxDD         : {df_results['maxdd'].max():.1f}%")
            print(f"   Best regime         : {df_results.groupby('regime')['sharpe'].mean().idxmax()}")
        return df_results

    def _resolve_base_ohlc_df(self, *, historical_only: bool) -> pd.DataFrame:
        if historical_only:
            mds = None
            if getattr(self.context, "container", None) is not None:
                mds = getattr(self.context.container, "market_data_service", None)
            if mds is None:
                mds = getattr(self.context.engine, "market_data_service", None)
            if mds is not None and hasattr(mds, "load_historical_ohlc_for_symbol"):
                neuro = ConfigLoader.section("evolution", "neuroevolution", default={}) or {}
                try:
                    days_back = max(1, int(neuro.get("fetch_days_back", 90) or 90))
                except (TypeError, ValueError):
                    days_back = 90
                try:
                    limit = max(MIN_SIMULATOR_BARS, int(neuro.get("fetch_limit", 20000) or 20000))
                except (TypeError, ValueError):
                    limit = 20000
                instrument = getattr(self.context.engine.config, "instrument", "MES")
                df = mds.load_historical_ohlc_for_symbol(
                    str(instrument),
                    days_back=days_back,
                    limit=limit,
                )
                if df is not None and len(df) >= _MIN_BACKTEST_WINDOW:
                    return df.copy()

        with self.context.live_data_lock:
            return self.context.ohlc_1min.tail(14400).copy().reset_index()

    def _maybe_retrain_ppo(self, base_df: pd.DataFrame | None) -> None:
        trainer = getattr(self.context.engine, "ppo_trainer", None)
        if trainer is None:
            return
        strict = require_real_simulator_data_strict()
        if not strict:
            if hasattr(trainer, "train"):
                try:
                    trainer.train(total_timesteps=100000)
                except Exception as exc:
                    self.logger.warning("PPO retrain (legacy timesteps-only) failed: %s", exc)
            return

        if base_df is None or len(base_df) < MIN_SIMULATOR_BARS:
            self.logger.warning("PPO retrain skipped: insufficient historical OHLC for strict mode.")
            return

        bars: list[dict[str, Any]] = base_df.to_dict("records")
        for row in bars:
            if "close" not in row and "last" in row:
                row["close"] = row["last"]

        try:
            if hasattr(trainer, "train_nightly_on_infinite_simulator"):
                trainer.train_nightly_on_infinite_simulator(bars, timesteps=100_000)
                return
            if hasattr(trainer, "train"):
                sig = inspect.signature(trainer.train)
                params = list(sig.parameters.keys())
                if params and params[0] == "simulator_data":
                    trainer.train(bars, total_timesteps=100_000)
                else:
                    self.logger.warning(
                        "PPO retrain skipped in strict mode: trainer lacks simulator_data train() API."
                    )
        except Exception as exc:
            self.logger.warning("PPO retrain on historical bars failed: %s", exc)
