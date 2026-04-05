from __future__ import annotations

from datetime import datetime
import os
from typing import Any, Dict, cast

import numpy as np
import pandas as pd
import ray  # type: ignore[reportMissingImports]

from lumina_core.runtime_context import RuntimeContext
from lumina_core.engine.RealisticBacktesterEngine import RealisticBacktesterEngine
from lumina_core.engine.AdvancedBacktesterEngine import AdvancedBacktesterEngine


@ray.remote
def simulate_chunk(
    chunk_id: int,
    base_df: pd.DataFrame,
    num_trades: int,
    context: RuntimeContext,
) -> list[Dict[str, Any]]:
    """Parallel chunk voor miljoenen trades."""
    simulator = RealisticBacktesterEngine(context)  # realistische slippage etc.
    results: list[Dict[str, Any]] = []

    for _ in range(num_trades):
        # Synthetic data genereren met regime switching + fat tails
        synthetic = base_df.copy()

        # Regime switching (Markov chain)
        regimes = ["TRENDING", "BREAKOUT", "VOLATILE", "RANGING", "NEUTRAL"]
        current_regime = str(np.random.choice(regimes))
        regime_seq = [current_regime]
        for _ in range(len(synthetic) - 1):
            if np.random.rand() < 0.15:  # switch probability
                current_regime = str(np.random.choice(regimes))
            regime_seq.append(current_regime)
        synthetic["regime"] = regime_seq

        # Fat tails + volatility clustering
        noise = np.random.normal(0, 0.0008, len(synthetic))
        synthetic["close"] += noise * synthetic["close"]
        synthetic["high"] = synthetic["close"] + abs(noise) * 1.4
        synthetic["low"] = synthetic["close"] - abs(noise) * 1.2

        # Random gap events (nieuws shocks)
        if np.random.rand() < 0.12 and len(synthetic) > 400:
            gap_idx = int(np.random.randint(200, len(synthetic) - 200))
            gap_size = float(np.random.normal(0, 0.012) * synthetic["close"].iloc[gap_idx])
            synthetic.loc[gap_idx:, "open"] = synthetic.loc[gap_idx:, "open"] + gap_size
            synthetic.loc[gap_idx:, "close"] = synthetic.loc[gap_idx:, "close"] + gap_size

        # Run realistic backtest op dit synthetische stuk
        res = simulator.run_backtest_on_snapshot(synthetic)
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


SIMULATE_CHUNK_REMOTE = cast(Any, simulate_chunk)


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
        ray.init(ignore_reinit_error=True, num_cpus=8)

    def generate_synthetic_data(self, base_df: pd.DataFrame, years: int = 1000) -> pd.DataFrame:
        """Base real data + 1000 jaar synthetic uitbreiding."""
        synthetic = base_df.copy()
        # Herhaal en voeg variatie toe
        full = pd.concat([synthetic] * (years * 252 // len(synthetic) + 1), ignore_index=True)
        return full.iloc[: len(full) // 10]  # beperk voor snelheid, maar schaalbaar

    def run_nightly_simulation(self, num_trades_total: int = 1_000_000) -> pd.DataFrame:
        """Hoofdmethode - run dit 's nachts."""
        start_time = datetime.now()
        print(
            f"[{start_time.strftime('%H:%M:%S')}] 🌌 INFINITE SIMULATOR STARTED - {num_trades_total:,} trades"
        )

        with self.context.live_data_lock:
            base_df = self.context.ohlc_1min.tail(14400).copy().reset_index()

        # Splits in parallel chunks
        chunk_size = num_trades_total // 32
        futures = []
        for i in range(32):
            future = SIMULATE_CHUNK_REMOTE.remote(i, base_df, chunk_size, self.context)
            futures.append(future)

        all_results = ray.get(futures)
        flat_results = [item for sublist in all_results for item in sublist]

        # Verwerk resultaten
        df_results = pd.DataFrame(flat_results)

        # Update vector DB met ervaringen
        for _, row in df_results.iterrows():
            self.context.store_experience_to_vector_db(
                context=(
                    f"Infinite sim trade - Regime {row['regime']} | "
                    f"Sharpe {row['sharpe']:.2f} | PnL {row['total_pnl']}"
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
            if getattr(self.context, "ppo_trainer", None) is not None:
                self.context.ppo_trainer.train(total_timesteps=100000)

        duration = (datetime.now() - start_time).total_seconds() / 60
        self.logger.info(
            f"INFINITE_SIM_COMPLETE,trades={len(flat_results)},avg_sharpe={avg_sharpe:.2f},duration_min={duration:.1f}"
        )

        print(f"✅ INFINITE SIM COMPLETE in {duration:.1f} min")
        if not df_results.empty:
            print(f"   Avg Sharpe          : {avg_sharpe:.2f}")
            print(f"   Worst MaxDD         : {df_results['maxdd'].max():.1f}%")
            print(
                f"   Best regime         : {df_results.groupby('regime')['sharpe'].mean().idxmax()}"
            )
        return df_results
