# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

import gymnasium as gym
import numpy as np
import pandas as pd
import requests

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_core.runtime_context import RuntimeContext


class RLTradingEnvironment(gym.Env):
    """
    Gymnasium-compatible RL training environment (Meta-RL path).
    Observation = market state + DNA features.
    Gym ``reward`` = shaped training signal (not broker ``economic_pnl``).
    """

    def __init__(self, context: RuntimeContext):
        super().__init__()
        self.context = context
        self.fast_path = context.fast_path
        self.backtester = context.backtester
        self.valuation_engine = ValuationEngine()
        self.instrument = str(self.context.engine.config.instrument)
        self._dna_version = str(getattr(self.context.engine, "active_dna_version", "GENESIS") or "GENESIS")
        self._active_dna_payload: dict[str, Any] = {
            "hash": self._dna_version,
            "content": "",
            "fitness": 0.0,
            "mutation_rate": 0.0,
            "regime_focus": "neutral",
        }
        self._dna_embedding_dim = 10

        # Observation space (23 features): 9 market + 10 semantic DNA + 4 DNA summary features
        self.observation_space = gym.spaces.Box(low=-10, high=10, shape=(23,), dtype=np.float32)

        # PPO verwacht een enkelvoudige action space. We encoden:
        # [signal(0..2), qty_pct(0.1..2.0), stop_mult(0.5..2.0), target_mult(1.5..4.0)]
        self.action_space = gym.spaces.Box(
            low=np.array([0.0, 0.1, 0.5, 1.5], dtype=np.float32),
            high=np.array([2.0, 2.0, 2.0, 4.0], dtype=np.float32),
            shape=(4,),
            dtype=np.float32,
        )

        self.current_episode = 0
        self.equity_curve = [50000.0]
        self.pnl_history = []

    def set_dna_version(self, dna_version: str) -> None:
        self._dna_version = str(dna_version)
        self._active_dna_payload["hash"] = self._dna_version

    def set_full_dna_embedding(self, dna_payload: dict[str, Any]) -> None:
        """Inject full PolicyDNA payload for Meta-RL conditioning."""
        payload = dna_payload if isinstance(dna_payload, dict) else {}
        self._dna_version = str(payload.get("hash") or payload.get("lineage_hash") or self._dna_version or "GENESIS")
        self._active_dna_payload = {
            "hash": self._dna_version,
            "content": str(payload.get("content") or ""),
            "fitness": float(payload.get("fitness", payload.get("fitness_score", 0.0)) or 0.0),
            "mutation_rate": float(payload.get("mutation_rate", 0.0) or 0.0),
            "regime_focus": str(payload.get("regime_focus") or self._infer_regime_focus(payload) or "neutral"),
        }

    def _infer_regime_focus(self, payload: dict[str, Any]) -> str:
        content = str(payload.get("content") or "").lower()
        if "trend" in content:
            return "trending"
        if "range" in content:
            return "ranging"
        if "volatility" in content or "high_vol" in content:
            return "high_volatility"
        return "neutral"

    def _canonical_dna_text(self) -> str:
        return json.dumps(
            {
                "hash": self._active_dna_payload.get("hash", self._dna_version),
                "content": self._active_dna_payload.get("content", ""),
                "fitness": float(self._active_dna_payload.get("fitness", 0.0) or 0.0),
                "mutation_rate": float(self._active_dna_payload.get("mutation_rate", 0.0) or 0.0),
                "regime_focus": str(self._active_dna_payload.get("regime_focus", "neutral") or "neutral"),
            },
            sort_keys=True,
            ensure_ascii=True,
        )

    def _hash_embedding(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [((digest[idx] / 127.5) - 1.0) for idx in range(self._dna_embedding_dim)]

    def _provider_dna_embedding(self, text: str) -> list[float] | None:
        provider = str(os.getenv("LUMINA_DNA_EMBED_PROVIDER", "ollama")).strip().lower()
        model = str(os.getenv("LUMINA_DNA_EMBED_MODEL", "nomic-embed-text")).strip() or "nomic-embed-text"

        try:
            if provider == "vllm":
                endpoint = str(os.getenv("LUMINA_VLLM_HOST", "http://localhost:8000")).rstrip("/")
                response = requests.post(
                    f"{endpoint}/v1/embeddings",
                    json={"model": model, "input": text},
                    timeout=1.8,
                )
                response.raise_for_status()
                payload = response.json()
                raw = payload.get("data", [{}])[0].get("embedding", [])
            else:
                import ollama

                embed_fn = getattr(ollama, "embed", None)
                if callable(embed_fn):
                    payload = embed_fn(model=model, input=text)
                    raw = payload.get("embeddings", [[]])[0]
                else:
                    payload = ollama.embeddings(model=model, prompt=text)
                    raw = payload.get("embedding", [])

            if not isinstance(raw, list) or not raw:
                return None
            vector = [float(v) for v in raw[: self._dna_embedding_dim]]
            if len(vector) < self._dna_embedding_dim:
                vector.extend([0.0] * (self._dna_embedding_dim - len(vector)))
            max_abs = max(max(abs(v) for v in vector), 1e-9)
            return [max(-1.0, min(1.0, v / max_abs)) for v in vector]
        except Exception:
            logging.exception(
                "Unhandled broad exception fallback in lumina_core/engine/rl/rl_trading_environment.py:136"
            )
            return None

    def _dna_summary_features(self) -> list[float]:
        regime = str(self._active_dna_payload.get("regime_focus", "neutral") or "neutral").lower()
        return [
            max(-1.0, min(1.0, float(self._active_dna_payload.get("fitness", 0.0) or 0.0))),
            max(0.0, min(1.0, float(self._active_dna_payload.get("mutation_rate", 0.0) or 0.0))),
            1.0 if "trend" in regime else 0.0,
            1.0 if "vol" in regime else 0.0,
        ]

    def _dna_embedding(self) -> list[float]:
        """Semantic DNA embedding from Ollama/vLLM with deterministic hash fallback."""
        canonical = self._canonical_dna_text()
        provider_embedding = self._provider_dna_embedding(canonical)
        return provider_embedding if provider_embedding is not None else self._hash_embedding(canonical)

    def _get_observation(self) -> np.ndarray:
        """Volledige state als vector."""
        dream = self.context.get_current_dream_snapshot()
        price = self.context.live_quotes[-1]["last"] if self.context.live_quotes else 5000.0
        regime = self.context.detect_market_regime(self.context.ohlc_1min.tail(60))
        tape = getattr(self.context, "tape_delta", {"imbalance": 0.0})

        obs = np.array(
            [
                price / 5000.0,
                dream.get("confidence", 0.5),
                dream.get("confluence_score", 0.5),
                1.0 if regime == "TRENDING" else 0.0,
                1.0 if regime == "BREAKOUT" else 0.0,
                tape.get("imbalance", 0.0),
                self.context.account_equity / 50000.0,
                len(self.pnl_history) / 100.0,
                np.mean(self.pnl_history[-10:]) if self.pnl_history else 0.0,
                *self._dna_embedding(),
                *self._dna_summary_features(),
            ],
            dtype=np.float32,
        )
        return obs

    def step(self, action: np.ndarray) -> tuple:
        flat = np.asarray(action, dtype=np.float32).reshape(-1)
        if flat.shape[0] != 4:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="RL_ACTION_SHAPE_INVALID",
                message=f"Expected action vector length 4, got {flat.shape[0]}.",
            )
        signal_idx = int(np.clip(np.rint(flat[0]), 0, 2))
        qty_pct = float(np.clip(flat[1], 0.1, 2.0))
        stop_mult = float(np.clip(flat[2], 0.5, 2.0))
        target_mult = float(np.clip(flat[3], 1.5, 4.0))

        signal = ["HOLD", "BUY", "SELL"][signal_idx]

        # Voer trade uit via simulator
        price = self.context.live_quotes[-1]["last"] if self.context.live_quotes else 5000.0
        regime = self.context.detect_market_regime(self.context.ohlc_1min.tail(60))

        # Gebruik FastPath + RL action
        _fast = self.fast_path.run(self.context.ohlc_1min.tail(60), price, regime)
        rl_close_accounting_net_usd = 0.0
        training_reward = 0.0
        if signal != "HOLD":
            qty = int(self.context.calculate_adaptive_risk_and_qty(price, regime, 0) * qty_pct)
            pnl = self._simulate_single_trade(price, signal, qty, stop_mult, target_mult)

            self.pnl_history.append(pnl)
            self.equity_curve.append(self.equity_curve[-1] + pnl)

            rl_close_accounting_net_usd = float(pnl)
            training_reward = float(pnl - abs(pnl) * 0.1 + (pnl / 1000.0) * 5)
            reward = training_reward
        else:
            reward = 0.0

        done = len(self.pnl_history) > 200
        truncated = False

        info = {
            "rl_close_accounting_net_usd": rl_close_accounting_net_usd,
            "training_reward": training_reward,
        }
        return self._get_observation(), reward, done, truncated, info

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self.current_episode += 1
        self.equity_curve = [50000.0]
        self.pnl_history = []
        return self._get_observation(), {}

    def _simulate_single_trade(self, price, signal, qty, stop_mult, target_mult):
        _ = pd.DataFrame  # keep pandas import explicit for future feature work
        atr = self.context.ohlc_1min["high"].sub(self.context.ohlc_1min["low"]).mean() * 1.5

        side = 0
        if signal == "BUY":
            side = 1
            target_price = price + atr * target_mult
        elif signal == "SELL":
            side = -1
            target_price = price - atr * target_mult
        else:
            return 0.0

        slip_ticks = self.valuation_engine.slippage_ticks(
            volume=1.0,
            avg_volume=1.0,
            regime=str(self.context.detect_market_regime(self.context.ohlc_1min.tail(60))),
            slippage_scale=1.0,
        )
        entry_fill = self.valuation_engine.apply_entry_fill(
            symbol=self.instrument,
            price=float(price),
            side=side,
            slippage_ticks=slip_ticks,
        )
        exit_fill = self.valuation_engine.apply_exit_fill(
            symbol=self.instrument,
            price=float(target_price),
            side=side,
            slippage_ticks=slip_ticks,
        )

        gross = self.valuation_engine.pnl_dollars(
            symbol=self.instrument,
            entry_price=entry_fill,
            exit_price=exit_fill,
            side=side,
            quantity=int(qty),
        )
        fees = self.valuation_engine.commission_dollars(
            symbol=self.instrument,
            quantity=int(qty),
            sides=2,
        )
        return (gross - fees) * 0.6
