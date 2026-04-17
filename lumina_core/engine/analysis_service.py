from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

import pandas as pd

from .fast_path_engine import FastPathEngine
from .errors import format_error_code
from .lumina_engine import LuminaEngine
from lumina_core.logging_utils import log_event


@dataclass(slots=True)
class HumanAnalysisService:
    """Event-driven analysis loop extracted from legacy runtime globals."""

    engine: LuminaEngine
    last_5min_candle: Any = None
    cache_lock: threading.RLock = field(default_factory=threading.RLock)
    cache_ttl_seconds: int = 300
    last_deep_analysis: dict[str, Any] = field(
        default_factory=lambda: {
            "timestamp": None,
            "price": 0.0,
            "regime": "NEUTRAL",
            "pa_hash": "",
            "consensus": None,
            "meta": None,
            "ai_fibs": {},
            "vision_summary": "",
            "chart_base64": None,
            "swing_high": 0.0,
            "swing_low": 0.0,
        }
    )
    fast_path_engine: FastPathEngine | None = None
    ppo_trainer: Any | None = None

    def __post_init__(self) -> None:
        if self.fast_path_engine is None:
            self.fast_path_engine = FastPathEngine(engine=self.engine)
        if self.ppo_trainer is None:
            try:
                from lumina_core.ppo_trainer import PPOTrainer

                self.ppo_trainer = PPOTrainer(engine=self.engine)
            except Exception:
                self.ppo_trainer = None

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to a runtime app")
        return self.engine.app

    def _cost_tracker(self) -> dict[str, Any]:
        return self.engine.cost_tracker

    def is_cache_valid(self, current_price: float, current_regime: str, pa_summary: str) -> bool:
        with self.cache_lock:
            ts = self.last_deep_analysis["timestamp"]
            if ts is None:
                return False
            time_diff = (datetime.now() - ts).total_seconds()
            last_price = float(self.last_deep_analysis["price"])
            price_change = abs(current_price - last_price) / last_price if last_price > 0 else 1.0
            pa_hash = str(hash(pa_summary))[:12]
            return (
                time_diff < self.cache_ttl_seconds
                and price_change < float(self.engine.config.event_threshold)
                and current_regime == self.last_deep_analysis["regime"]
                and pa_hash == self.last_deep_analysis["pa_hash"]
            )

    def deep_analysis(self, price: float, regime: str, mtf_data: str, pa_summary: str) -> None:
        app = self._app()
        with self.engine.live_data_lock:
            if len(self.engine.ohlc_1min) < 80:
                app.logger.warning("DEEP_ANALYSIS_SKIPPED,reason=insufficient_data")
                return
            df_snapshot = self.engine.ohlc_1min.copy()

        fast_result = self.engine.fast_path.run(df_snapshot, price, regime)
        swarm_manager = getattr(self.engine, "swarm", None)
        if swarm_manager is not None and hasattr(swarm_manager, "run_swarm_cycle"):
            try:
                swarm_info = swarm_manager.run_swarm_cycle()
                if isinstance(swarm_info, dict):
                    fast_result["swarm_regime"] = swarm_info.get("global_regime", "NEUTRAL")
                    fast_result["swarm_info"] = swarm_info
            except Exception as exc:
                app.logger.debug(f"Fast-path swarm context skipped: {exc}")
        if not fast_result["used_llm"]:
            return  # Fast path heeft al beslist

        recent = df_snapshot.iloc[-60:]
        swing_low = float(recent["low"].min())
        swing_high = float(recent["high"].max())
        diff = swing_high - swing_low
        fib_levels: dict[str, float] = {}
        for r in [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]:
            fib_levels[str(r)] = round(swing_high - diff * r, 2)

        tracker = self._cost_tracker()
        cost_before = float(tracker.get("today", 0.0))

        consensus = app.run_async_safely(
            app.multi_agent_consensus(
                price,
                mtf_data,
                pa_summary,
                app.detect_market_structure(df_snapshot),
                fib_levels,
            )
        )
        past_experiences = app.retrieve_relevant_experiences(f"Prijs {price:.2f} | Regime {regime}")
        meta = app.run_async_safely(app.meta_reasoning_and_counterfactuals(consensus, price, pa_summary, past_experiences))
        world_model = app.update_world_model(df_snapshot, regime, pa_summary)

        signal = consensus.get("signal", "HOLD")
        confidence = float(consensus.get("confidence", 0.0))
        stop = 0.0
        target = 0.0
        if signal == "BUY":
            stop = float(fib_levels.get("0.786", price * 0.997))
            if stop >= price:
                stop = price * 0.997
            target = price + (price - stop) * 2
        elif signal == "SELL":
            stop = float(fib_levels.get("0.236", price * 1.003))
            if stop <= price:
                stop = price * 1.003
            target = price - (stop - price) * 2

        reason_text = f"{consensus.get('reason', '')} | Meta: {meta.get('meta_reasoning', '')[:80]}"
        self.engine.set_current_dream_fields(
            {
                "reason": reason_text,
                "signal": signal,
                "confidence": confidence,
                "confluence_score": confidence,
                "chosen_strategy": "event_driven",
                "stop": round(stop, 2) if stop else 0.0,
                "target": round(target, 2) if target else 0.0,
                "fib_levels": fib_levels,
                "swing_high": round(swing_high, 2),
                "swing_low": round(swing_low, 2),
            }
        )

        vision_obj: dict[str, Any] = {}
        chart_base64 = app.generate_multi_tf_chart()
        if chart_base64:
            vision_prompt = (
                f"Analyseer deze chart voor {self.engine.config.instrument}. "
                f"Prijs={price:.2f}, Regime={regime}. Geef compact trading-advies."
            )
            try:
                local_engine = getattr(app, "local_inference_engine", None)
                if local_engine is not None and hasattr(local_engine, "vision_infer"):
                    vision_obj = local_engine.vision_infer(chart_base64, vision_prompt)
                else:
                    vision_obj = app.infer_json(
                        {
                            "model": self.engine.config.vision_model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "Je bent een professionele chart-analist. Geef ALLEEN JSON met keys: summary (string), ai_fibs (dict met fib-ratio->prijs).",
                                },
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": vision_prompt},
                                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart_base64}"}},
                                    ],
                                },
                            ],
                            "max_tokens": 220,
                            "temperature": 0.2,
                        },
                        timeout=20,
                        context="vision_analysis",
                    ) or {}

                ai_fibs = vision_obj.get("ai_fibs", {}) if isinstance(vision_obj, dict) else {}
                if isinstance(ai_fibs, dict) and ai_fibs:
                    self.engine.AI_DRAWN_FIBS = ai_fibs
                self.engine.set_current_dream_fields(
                    {
                        "reason": f"{reason_text} | Vision: {str((vision_obj or {}).get('summary', ''))[:80]}",
                    }
                )
            except Exception as exc:
                code = format_error_code("ANALYSIS_VISION", exc, fallback="DEEP_ANALYSIS_FAILED")
                app.logger.error(f"Vision deep_analysis error [{code}]: {exc}")

        app.logger.info(
            f"DEEP_ANALYSIS,signal={consensus.get('signal','HOLD')},conf={float(consensus.get('confidence', 0.0)):.2f},regime={regime},vix={world_model['macro']['vix']:.1f}"
        )

        if float(tracker.get("today", 0.0)) <= cost_before:
            tracker["today"] = float(tracker.get("today", 0.0)) + 0.08

        # EmotionalTwin correctie op deep-analysis result.
        twin = getattr(self.engine, "emotional_twin_agent", None)
        if twin is not None and hasattr(twin, "apply_correction"):
            corrected = twin.apply_correction(self.engine.get_current_dream_snapshot())
            self.engine.set_current_dream_fields(corrected)

        swarm_manager = getattr(self.engine, "swarm", None)
        if swarm_manager is not None and hasattr(swarm_manager, "run_swarm_cycle"):
            try:
                swarm_info = swarm_manager.run_swarm_cycle()
                self.engine.set_current_dream_fields(
                    {
                        "swarm_regime": swarm_info.get("global_regime", "NEUTRAL"),
                        "swarm_info": swarm_info,
                    }
                )
            except Exception as exc:
                app.logger.debug(f"Deep-analysis swarm context skipped: {exc}")

        with self.cache_lock:
            self.last_deep_analysis.update(
                {
                    "timestamp": datetime.now(),
                    "price": price,
                    "regime": regime,
                    "pa_hash": str(hash(pa_summary))[:12],
                    "consensus": consensus,
                    "meta": meta,
                    "ai_fibs": self.engine.AI_DRAWN_FIBS,
                    "vision_summary": vision_obj.get("summary", ""),
                    "chart_base64": chart_base64,
                    "swing_high": swing_high,
                    "swing_low": swing_low,
                }
            )

    def run_main_loop(self) -> None:
        app = self._app()
        while True:
            try:
                with self.engine.live_data_lock:
                    if len(self.engine.ohlc_1min) < 10:
                        time.sleep(5)
                        continue
                    df = self.engine.ohlc_1min.copy()
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df.set_index("timestamp", inplace=True)
                    five_min = (
                        df.resample("5min")
                        .agg({
                            "open": "first",
                            "high": "max",
                            "low": "min",
                            "close": "last",
                            "volume": "sum",
                        })
                        .dropna()
                    )
                    if len(five_min) == 0:
                        time.sleep(5)
                        continue
                    current_5min_ts = five_min.index[-1]
                    current_price = float(five_min["close"].iloc[-1])
                    previous_price = float(five_min["close"].iloc[-2]) if len(five_min) > 1 else current_price
                    regime = app.detect_market_regime(self.engine.ohlc_1min)

                if self.last_5min_candle is None or current_5min_ts != self.last_5min_candle:
                    self.last_5min_candle = current_5min_ts
                    log_event(app.logger, "analysis.new_candle", ts=datetime.now().strftime("%H:%M:%S"))

                    if bool(getattr(self.engine, "rl_policy_enabled", False)) and getattr(self.engine, "rl_policy_model", None) is not None:
                        try:
                            from lumina_core.rl_environment import RLTradingEnvironment

                            raw_records = self.engine.ohlc_1min.tail(2500).to_dict("records")
                            records = cast(list[dict[str, Any]], raw_records)
                            env = RLTradingEnvironment(self.engine, records)
                            obs, _ = env.reset()
                            trainer = self.ppo_trainer
                            if trainer is not None:
                                rl_action = trainer.infer_live_action(obs)
                                applied = self.engine.apply_rl_live_decision(rl_action, current_price=current_price, regime=regime)
                                if applied:
                                    log_event(
                                        app.logger,
                                        "analysis.fast_path",
                                        source="rl_policy",
                                        signal=str(rl_action.get("signal", "HOLD")),
                                        confidence=round(float(rl_action.get("confidence", 0.0)), 2),
                                    )
                                    continue
                        except Exception as exc:
                            code = format_error_code("ANALYSIS_RL", exc, fallback="LIVE_DECISION_FAILED")
                            app.logger.error(f"RL live decision error [{code}]: {exc}")

                    fast_result = self.engine.fast_path.run(self.engine.ohlc_1min, current_price, regime)
                    if not fast_result["used_llm"]:
                            # Hard Risk Controller — VERY FIRST check before applying fast-path signal
                            _fp_signal = fast_result.get("signal", "HOLD")
                            if _fp_signal in {"BUY", "SELL"}:
                                _risk_ctrl = getattr(self.engine, "risk_controller", None)
                                if _risk_ctrl is not None:
                                    _fp_stop = float(fast_result.get("stop", current_price * 0.99 if _fp_signal == "BUY" else current_price * 1.01))
                                    _fp_risk = abs(current_price - _fp_stop)
                                    _rc_ok, _rc_reason = _risk_ctrl.check_can_trade(
                                        str(self.engine.config.instrument), str(regime), float(_fp_risk)
                                    )
                                    if not _rc_ok:
                                        app.logger.warning(f"HardRiskController blocked fast-path signal: {_rc_reason}")
                                        fast_result = dict(fast_result)
                                        fast_result["signal"] = "HOLD"
                            self.engine.set_current_dream_fields(
                                {
                                    "signal": fast_result["signal"],
                                    "confidence": fast_result["confidence"],
                                    "stop": fast_result["stop"],
                                    "target": fast_result["target"],
                                    "reason": fast_result["reason"],
                                    "confluence_score": fast_result["confidence"],
                                    "chosen_strategy": fast_result["chosen_strategy"],
                                }
                            )
                            log_event(
                                app.logger,
                                "analysis.fast_path",
                                source="fast_path_engine",
                                signal=str(fast_result["signal"]),
                                confidence=round(float(fast_result["confidence"]), 2),
                                latency_ms=float(fast_result["latency_ms"]),
                            )
                            continue
                    else:
                        log_event(app.logger, "analysis.llm_takeover", reason="fast_path_low_confidence")
                    mtf_data = app.get_mtf_snapshots()
                    pa_summary = app.generate_price_action_summary()

                    if self.is_cache_valid(current_price, regime, pa_summary):
                        log_event(app.logger, "analysis.cache_hit", regime=str(regime))
                        tracker = self._cost_tracker()
                        tracker["cached_analyses"] = int(tracker.get("cached_analyses", 0)) + 1
                        with self.cache_lock:
                            cached = dict(self.last_deep_analysis)
                            consensus = cached.get("consensus") or {"signal": "HOLD", "confidence": 0.0, "reason": "cache-empty"}
                            meta = cached.get("meta") or {}
                            self.engine.set_current_dream_fields(
                                {
                                    "signal": consensus.get("signal", "HOLD"),
                                    "confidence": float(consensus.get("confidence", 0.0)),
                                    "stop": float(meta.get("stop", 0) or 0),
                                    "target": float(meta.get("target", 0) or 0),
                                    "reason": str(consensus.get("reason", "")) + " | CACHED",
                                    "confluence_score": float(consensus.get("confidence", 0.0)),
                                    "fib_levels": cached.get("ai_fibs", {}),
                                    "swing_high": float(cached.get("swing_high", 0.0)),
                                    "swing_low": float(cached.get("swing_low", 0.0)),
                                    "chosen_strategy": "cached_fast_path",
                                }
                            )
                        continue

                    if app.is_significant_event(current_price, previous_price, regime):
                        app.logger.info(f"Significant event detected at {current_price} → deep analysis triggered")
                        self.deep_analysis(current_price, regime, mtf_data, pa_summary)
                    else:
                        tape_signal = dict(getattr(self.engine.market_data, "last_tape_signal", {}) or {})
                        if bool(tape_signal.get("fast_path_trigger", False)):
                            app.logger.info(
                                f"Tape momentum trigger detected ({tape_signal.get('reason', '')}) → deep analysis"
                            )
                            self.deep_analysis(current_price, regime, mtf_data, pa_summary)
                        else:
                            app.logger.debug(f"Light scan at {current_price} – no deep analysis needed")

                if int(datetime.now().second) == 0:
                    tracker = self._cost_tracker()
                    app.logger.info(
                        f"Cost report | Today: ${float(tracker.get('today', 0.0)):.2f} | "
                        f"Cached analyses: {int(tracker.get('cached_analyses', 0))} | "
                        f"Reasoning tokens: {int(tracker.get('reasoning_tokens', 0))}"
                    )
                time.sleep(5)
            except Exception as exc:
                code = format_error_code("ANALYSIS_LOOP", exc, fallback="MAIN_LOOP_FAILED")
                app.logger.error(f"Main loop error [{code}]: {exc}")
                time.sleep(10)


AnalysisService = HumanAnalysisService
