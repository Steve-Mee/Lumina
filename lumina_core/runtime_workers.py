import asyncio
import threading
import time
import traceback
from datetime import datetime, timezone

import requests

from lumina_core.runtime_context import RuntimeContext
from lumina_core.engine.agent_contracts import apply_agent_policy_gateway
from lumina_core.engine.broker_bridge import Order
from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.engine.mode_capabilities import resolve_mode_capabilities
from lumina_core.engine.rl_guardrails import RLGuardrailLayer
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_core.logging_utils import log_runtime_trace, runtime_trace_enabled
from lumina_core.order_gatekeeper import session_guard_allows_trading
from lumina_core.runtime_trade_gates import apply_hard_risk_controller_to_signal

TRADER_LEAGUE_WEBHOOK_URL = "http://localhost:8000/webhook/trade"
_RL_GUARDRAIL = RLGuardrailLayer()


def _push_trader_league_trade(
    app: RuntimeContext,
    *,
    mode: str,
    symbol: str,
    signal: str | None,
    entry_price: float,
    exit_price: float,
    qty: int,
    pnl_dollars: float,
    reflection: dict | None = None,
    chart_base64: str | None = None,
    broker_fill_id: str | None = None,
    commission: float | None = None,
    slippage_points: float | None = None,
    fill_latency_ms: float | None = None,
    reconciliation_status: str | None = None,
) -> None:
    reflection_payload = dict(reflection or {})
    if any(
        value is not None
        for value in (broker_fill_id, commission, slippage_points, fill_latency_ms, reconciliation_status)
    ):
        reflection_payload.setdefault("reconciliation", {})
        reflection_payload["reconciliation"].update(
            {
                "broker_fill_id": broker_fill_id,
                "commission": commission,
                "slippage_points": slippage_points,
                "fill_latency_ms": fill_latency_ms,
                "status": reconciliation_status,
            }
        )
    payload = {
        "participant": str(getattr(getattr(app, "config", None), "participant_id", None) or "LUMINA_Steve"),
        "mode": mode,
        "symbol": symbol,
        "signal": signal,
        "entry": entry_price,
        "exit": exit_price,
        "qty": qty,
        "pnl": pnl_dollars,
        "broker_fill_id": broker_fill_id,
        "commission": commission,
        "slippage_points": slippage_points,
        "fill_latency_ms": fill_latency_ms,
        "reconciliation_status": reconciliation_status,
        "reflection": reflection_payload,
        "chart_base64": chart_base64,
    }
    try:
        response = requests.post(TRADER_LEAGUE_WEBHOOK_URL, json=payload, timeout=5)
        response.raise_for_status()
        log_structured(
            LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="INFO_PRINT_LEGACY",
                message="📡 Trade gepusht naar Trader League",
                context={"mode": mode},
            )
        )
    except Exception as exc:
        err = LuminaError(
            severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
            code="RUNTIME_WEBHOOK_001",
            message=str(exc),
            context={"traceback": traceback.format_exc(), "mode": mode},
        )
        log_structured(err)
        app.logger.warning(f"League webhook failed: {exc}")


def _enforce_real_eod_force_close(app: RuntimeContext, price: float) -> bool:
    """Force-close broker positions during EOD window for modes with real-like guard enforcement."""
    mode = str(getattr(app.engine.config, "trade_mode", "paper")).strip().lower()
    capabilities = resolve_mode_capabilities(mode)
    if not capabilities.eod_force_close_enabled:
        return False

    risk_ctrl = getattr(app.engine, "risk_controller", None)
    if risk_ctrl is None or not hasattr(risk_ctrl, "should_force_close_eod"):
        return False

    should_close, reason = risk_ctrl.should_force_close_eod()
    if not should_close:
        return False

    obs = getattr(app.engine, "observability_service", None)
    if obs is not None and hasattr(obs, "record_mode_eod_force_close"):
        try:
            obs.record_mode_eod_force_close(mode=mode)
        except Exception as _exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="RUNTIME_OBS_002",
                message=str(_exc),
                context={"traceback": traceback.format_exc(), "mode": mode},
            )
            log_structured(err)

    app.logger.warning("EOD FORCE-CLOSE active [mode=%s]: %s", mode, reason)
    log_structured(
        LuminaError(
            severity=ErrorSeverity.RECOVERABLE_LEARNING,
            code="INFO_PRINT_LEGACY",
            message=f"⚠️ EOD FORCE-CLOSE active [{mode.upper()}]: {reason}",
            context={"mode": mode},
        )
    )

    container = getattr(app, "container", None)
    broker = getattr(container, "broker", None) if container is not None else None
    if broker is None:
        app.logger.error("EOD FORCE-CLOSE [mode=%s]: broker unavailable", mode)
        return True

    try:
        positions = broker.get_positions() if hasattr(broker, "get_positions") else []
    except Exception as exc:
        err = LuminaError(
            severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
            code="RUNTIME_BROKER_003",
            message=str(exc),
            context={"traceback": traceback.format_exc(), "mode": mode},
        )
        log_structured(err)
        app.logger.error(f"EOD FORCE-CLOSE [mode={mode}]: get_positions failed: {exc}")
        return True

    flattened_any = False
    for pos in positions:
        qty = int(getattr(pos, "quantity", 0) or 0)
        if qty == 0:
            continue
        symbol = str(getattr(pos, "symbol", getattr(app, "INSTRUMENT", app.engine.config.instrument)))
        close_side = "SELL" if qty > 0 else "BUY"
        try:
            result = broker.submit_order(
                Order(
                    symbol=symbol,
                    side=close_side,
                    quantity=abs(qty),
                    order_type="MARKET",
                    stop_loss=0.0,
                    take_profit=0.0,
                    metadata={"reason": "eod_force_close", "mode": mode},
                )
            )
            if bool(getattr(result, "accepted", False)):
                flattened_any = True
                app.logger.warning("EOD FORCE-CLOSE executed [mode=%s]: %s %s", mode, close_side, symbol)
            else:
                app.logger.error(
                    "EOD FORCE-CLOSE rejected [mode=%s]: %s %s (%s)",
                    mode,
                    close_side,
                    symbol,
                    getattr(result, "message", "unknown"),
                )
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="RUNTIME_BROKER_004",
                message=str(exc),
                context={"traceback": traceback.format_exc(), "mode": mode, "symbol": symbol},
            )
            log_structured(err)
            app.logger.error(f"EOD FORCE-CLOSE [mode={mode}] order error for {symbol}: {exc}")

    if flattened_any:
        app.engine.live_position_qty = 0
        app.engine.last_entry_price = float(price)
        app.engine.live_trade_signal = "HOLD"

    return True


def pre_dream_daemon(app: RuntimeContext) -> None:
    last_news_update_ts = 0.0
    cached_news_data = {"events": [], "overall_sentiment": "neutral", "impact": "medium"}

    while True:
        try:
            with app.live_data_lock:
                price = (
                    app.live_quotes[-1]["last"]
                    if app.live_quotes
                    else (app.ohlc_1min["close"].iloc[-1] if len(app.ohlc_1min) > 0 else 0.0)
                )
                df = app.ohlc_1min.copy()

            regime = app.detect_market_regime(df)
            app.regime_history.append({"ts": datetime.now().isoformat(), "regime": regime})
            structure = app.detect_market_structure(df)

            rl_action: dict[str, float] | None = None
            rl_signal = "HOLD"
            try:
                if (
                    getattr(app.engine, "rl_env", None) is not None
                    and getattr(app.engine, "ppo_trainer", None) is not None
                ):
                    obs = app.engine.rl_env._get_observation()
                    rl_action = app.engine.ppo_trainer.predict_action(obs)
                    rl_signal_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
                    rl_signal = rl_signal_map.get(int(rl_action.get("signal", 0)), "HOLD")
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RUNTIME_RL_005",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                app.logger.debug(f"Pre-dream RL bias unavailable: {exc}")

            fast_result = app.engine.fast_path.run(df, price, regime)
            if rl_signal in {"BUY", "SELL"} and not fast_result.get("used_llm", False):
                # RL-bias forceert evaluatie in de LLM-laag, zelfs als fast-path anders direct zou beslissen.
                fast_result["used_llm"] = True
                fast_result["pass_to_llm"] = True
            if not fast_result["used_llm"]:
                continue  # Fast path heeft al beslist

            recent_winrate = (
                float(app.np.mean(app.np.array(app.pnl_history[-15:]) > 0)) if len(app.pnl_history) > 10 else 0.5
            )
            min_conf = app.calculate_dynamic_confluence(regime, recent_winrate)

            mtf_data = app.get_mtf_snapshots()
            _, _, fib_levels = app.detect_swing_and_fibs()
            pa_summary = app.generate_price_action_summary()

            chart_base64 = app.generate_multi_tf_chart()
            if not chart_base64:
                time.sleep(12)
                continue

            if chart_base64:
                app.update_live_chart(chart_base64, status_msg="AI Decision & Chart updated")

            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message="🤖 Multi-agent consensus started...",
                    context={},
                )
            )
            consensus = asyncio.run(app.multi_agent_consensus(price, mtf_data, pa_summary, structure, fib_levels))

            rl_context = (
                f"RL signal {rl_signal} | qty {float(rl_action.get('qty_pct', 1.0)):.2f} | "
                f"stop x{float(rl_action.get('stop_mult', 1.0)):.2f} | "
                f"target x{float(rl_action.get('target_mult', 1.0)):.2f}"
                if isinstance(rl_action, dict)
                else "RL signal HOLD | qty 1.00 | stop x1.00 | target x1.00"
            )

            query = f"Prijs {price:.2f} | Regime {regime} | {rl_context} | {pa_summary[:100]}"
            past_experiences = app.retrieve_relevant_experiences(query, n_results=4)

            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message="🧠 Meta-reasoning and counterfactuals started...",
                    context={},
                )
            )
            meta = asyncio.run(app.meta_reasoning_and_counterfactuals(consensus, price, pa_summary, past_experiences))

            app.world_model = app.update_world_model(df, regime, pa_summary)
            blackboard = getattr(app, "blackboard", None)

            news_agent = getattr(app, "news_agent", None)
            if news_agent is not None and hasattr(news_agent, "run_news_cycle"):
                try:
                    news_cycle = news_agent.run_news_cycle()
                    if isinstance(news_cycle, dict):
                        dynamic = news_cycle.get("dynamic_multipliers")
                        if isinstance(dynamic, dict) and dynamic:
                            app.engine.config.news_impact_multipliers = {str(k): float(v) for k, v in dynamic.items()}

                        cycle_news_data = news_cycle.get("news_data")
                        if isinstance(cycle_news_data, dict):
                            cached_news_data = cycle_news_data

                        avoid = bool(news_cycle.get("news_avoidance_window", False))
                        hold_until_ts = float(news_cycle.get("news_avoidance_hold_until_ts", 0.0) or 0.0)
                        if avoid and hold_until_ts > 0.0:
                            current_hold = float(app.get_current_dream_snapshot().get("hold_until_ts", 0.0) or 0.0)
                            news_updates = {
                                "hold_until_ts": max(current_hold, hold_until_ts),
                                "why_no_trade": str(news_cycle.get("news_avoidance_reason", "news_avoidance_window")),
                                "signal": "HOLD",
                            }
                            if blackboard is not None and hasattr(blackboard, "add_proposal"):
                                blackboard.add_proposal(
                                    topic="agent.news.proposal",
                                    producer="runtime_workers.pre_dream_daemon",
                                    payload=news_updates,
                                    confidence=float(news_cycle.get("confidence", 0.8) or 0.8),
                                )
                            else:
                                app.set_current_dream_fields(news_updates)

                        sentiment_signal = str(
                            news_cycle.get("sentiment_signal", cached_news_data.get("overall_sentiment", "neutral"))
                        )
                        sentiment_score = float(news_cycle.get("sentiment_score", 0.0) or 0.0)
                        dynamic_multiplier = float(news_cycle.get("dynamic_multiplier", 1.0) or 1.0)
                        world_model_news = {
                            "last_update": news_cycle.get("last_update"),
                            "overall_sentiment": sentiment_signal,
                            "sentiment_score": sentiment_score,
                            "impact": cached_news_data.get("impact", "medium"),
                            "events_count": len(cached_news_data.get("events", []))
                            if isinstance(cached_news_data.get("events", []), list)
                            else 0,
                            "multiplier": dynamic_multiplier,
                            "news_avoidance_window": avoid,
                        }
                        if isinstance(app.world_model, dict):
                            app.world_model["news"] = world_model_news
                            app.world_model.setdefault("macro", {})
                            app.world_model["macro"]["news_sentiment"] = sentiment_signal
                            app.world_model["macro"]["news_sentiment_score"] = sentiment_score
                            app.world_model["macro"]["news_multiplier"] = dynamic_multiplier
                except Exception as exc:
                    err = LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="RUNTIME_NEWS_006",
                        message=str(exc),
                        context={"traceback": traceback.format_exc()},
                    )
                    log_structured(err)
                    app.logger.error(f"NewsAgent cycle error: {exc}")
            elif news_agent is not None and hasattr(news_agent, "run_cycle"):
                try:
                    news_cycle = news_agent.run_cycle()
                    if isinstance(news_cycle, dict):
                        cycle_news_data = news_cycle.get("news_data")
                        if isinstance(cycle_news_data, dict):
                            cached_news_data = cycle_news_data
                except Exception as exc:
                    err = LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="RUNTIME_NEWS_007",
                        message=str(exc),
                        context={"traceback": traceback.format_exc()},
                    )
                    log_structured(err)
                    app.logger.error(f"NewsAgent cycle error: {exc}")
            else:
                if time.time() - last_news_update_ts >= 60:
                    cached_news_data = app.get_high_impact_news()
                    last_news_update_ts = time.time()

            news_data = cached_news_data
            news_impact = app.resolve_news_multiplier(news_data, app.engine.config.news_impact_multipliers, default=1.0)
            if blackboard is not None and hasattr(blackboard, "add_proposal"):
                blackboard.add_proposal(
                    topic="agent.news.proposal",
                    producer="runtime_workers.pre_dream_daemon",
                    payload={"news_impact": float(news_impact)},
                    confidence=0.75,
                )
            else:
                app.set_current_dream_value("news_impact", news_impact)

            macro_news_sentiment = "neutral"
            macro_news_score = 0.0
            macro_news_multiplier = float(news_impact)
            if isinstance(app.world_model, dict):
                macro = app.world_model.get("macro", {})
                if isinstance(macro, dict):
                    macro_news_sentiment = str(macro.get("news_sentiment", macro_news_sentiment))
                    macro_news_score = float(macro.get("news_sentiment_score", macro_news_score) or 0.0)
                    macro_news_multiplier = float(
                        macro.get("news_multiplier", macro_news_multiplier) or macro_news_multiplier
                    )

            avoid_active = bool(float(app.get_current_dream_snapshot().get("hold_until_ts", 0.0) or 0.0) > time.time())

            vision_content = [
                {
                    "type": "text",
                    "text": f"""Multi-Agent Consensus: {consensus["signal"]} (conf {consensus["confidence"]:.2f})
RL Policy Bias: {rl_context}
Relevante ervaringen: {past_experiences}
Meta-reasoning: {meta.get("meta_reasoning", "")}
Counter-factuals: {meta.get("counterfactuals", [])}
World Model (Macro + Micro): 
Macro -> VIX {app.world_model["macro"]["vix"]:.1f}, DXY {app.world_model["macro"]["dxy"]:.1f}, 10y {app.world_model["macro"]["ten_year_yield"]:.2f}
Micro -> Regime {app.world_model["micro"]["regime"]}, Orderflow {app.world_model["micro"]["orderflow_bias"]}
News Sentiment: {macro_news_sentiment} (score {macro_news_score:.2f}, impact {news_data["impact"]})
News Multiplier: {macro_news_multiplier:.2f} | Avoidance Active: {str(avoid_active)}
Use this full world model as the basis for your decision.
Use RL Policy Bias as directional prior, not as absolute rule.
Return JSON only with: signal, confidence, stop, target, reason, why_no_trade, confluence_score, chosen_strategy, fib_levels_drawn, narrative_reasoning""",
                },
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart_base64}"}},
            ]

            payload = {
                "model": app.engine.config.vision_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are visually trained. Use all layers, including the dynamic world model.",
                    },
                    {"role": "user", "content": vision_content},
                ],
                "max_tokens": 1300,
            }

            dream_json = None
            infer_json_fn = getattr(app, "infer_json", None)
            if callable(infer_json_fn):
                dream_json = infer_json_fn(payload, timeout=50, context="pre_dream_vision")
            if dream_json is None:
                continue

            if isinstance(dream_json, dict):
                if avoid_active:
                    dream_json["signal"] = "HOLD"
                    dream_json["why_no_trade"] = "News avoidance window active"

                # EmotionalTwin correctie op vision output vóór DreamState update.
                twin = getattr(app.engine, "emotional_twin", None)
                if twin is not None and hasattr(twin, "apply_correction"):
                    dream_json = twin.apply_correction(dream_json)

                blackboard = getattr(app, "blackboard", None)
                aggregate_confidence = float(max(min(dream_json.get("confluence_score", 0.0) or 0.0, 1.0), 0.0))
                if blackboard is not None and hasattr(blackboard, "publish_sync"):
                    blackboard.publish_sync(
                        topic="execution.aggregate",
                        producer="runtime_workers.pre_dream_daemon",
                        payload=dict(dream_json),
                        confidence=aggregate_confidence,
                    )
                else:
                    app.set_current_dream_fields(dream_json)
                app.set_current_dream_value(
                    "confluence_score", max(min_conf, consensus["confidence"], meta.get("meta_score", 0.5))
                )
                dream_snapshot = app.get_current_dream_snapshot()

                raw_fibs = dream_json.get("fib_levels_drawn", {})
                app.AI_DRAWN_FIBS = raw_fibs if isinstance(raw_fibs, dict) else {}
                narrative_reasoning = dream_json.get("narrative_reasoning", "")

                app.speak(narrative_reasoning)
                app.store_experience_to_vector_db(
                    context=f"World Model Update + Dream: {narrative_reasoning[:150]}",
                    metadata={"type": "world_model_dream", "date": datetime.now().isoformat()},
                )

                _mode_val = getattr(getattr(app, "engine", None), "config", None)
                _mode_val = getattr(_mode_val, "trade_mode", "paper") if _mode_val else "paper"
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="INFO_PRINT_LEGACY",
                        message=(
                            f"🌍 v36 WORLD MODEL + META DREAM: "
                            f"{dream_snapshot.get('chosen_strategy')} → {dream_snapshot.get('signal')} "
                            f"(conf={dream_snapshot.get('confluence_score', 0):.2f})"
                        ),
                        context={"mode": _mode_val},
                    )
                )

        except Exception as e:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="RUNTIME_VISION_008",
                message=str(e),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            app.logger.error(f"VISION_CYCLE_CRASH: {e}", exc_info=True)

        time.sleep(12)


def voice_listener_thread(app: RuntimeContext) -> None:
    if not app.VOICE_INPUT_ENABLED or not app.voice_recognizer:
        return

    log_structured(
        LuminaError(
            severity=ErrorSeverity.RECOVERABLE_LEARNING,
            code="INFO_PRINT_LEGACY",
            message="🎤 Voice input active - say 'Lumina' + command or feedback",
            context={},
        )
    )

    while True:
        try:
            with app.sr.Microphone() as source:
                app.voice_recognizer.adjust_for_ambient_noise(source, duration=0.8)
                audio = app.voice_recognizer.listen(source, timeout=10, phrase_time_limit=8)

            text = app.voice_recognizer.recognize_google(audio, language="nl-NL")
            text_lower = text.lower().strip()

            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message=f"\ud83c\udfa4 YOU: {text}",
                    context={},
                )
            )

            if app.engine.config.voice_wake_word in text_lower:
                command = text_lower.split(app.engine.config.voice_wake_word, 1)[1].strip()
                dream_snapshot = app.get_current_dream_snapshot()

                if any(x in command for x in ["status", "hoe gaat het", "wat is de stand"]):
                    app.speak(
                        f"Current equity is {app.account_equity:,.0f} dollars. Open PnL is {app.open_pnl:,.0f}. "
                        f"We are running in {app.engine.config.trade_mode.upper()} mode."
                    )
                elif any(x in command for x in ["ga long", "koop", "long"]):
                    app.set_current_dream_fields({"signal": "BUY", "confluence_score": 0.95})
                    app.speak("Okay, I am forcing a long position. Do you want immediate execution?")
                    log_structured(
                        LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_LEARNING,
                            code="INFO_PRINT_LEGACY",
                            message="👤 MANUAL OVERRIDE → BUY",
                            context={},
                        )
                    )
                elif any(x in command for x in ["ga short", "verkoop", "short"]):
                    app.set_current_dream_fields({"signal": "SELL", "confluence_score": 0.95})
                    app.speak("Okay, I am forcing a short position. Please confirm.")
                    log_structured(
                        LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_LEARNING,
                            code="INFO_PRINT_LEGACY",
                            message="👤 MANUAL OVERRIDE → SELL",
                            context={},
                        )
                    )
                elif any(x in command for x in ["hold", "stop", "niet traden"]):
                    app.set_current_dream_value("signal", "HOLD")
                    app.speak("Understood, switching to HOLD mode.")
                elif any(x in command for x in ["stop alles", "emergency stop", "stop de bot", "shutdown"]):
                    app.emergency_stop()
                elif any(x in command for x in ["wat is je dream", "dream", "wat denk je"]):
                    app.speak(
                        f"My current dream is {dream_snapshot.get('chosen_strategy', 'unknown')} with signal "
                        f"{dream_snapshot.get('signal')} en confidence {dream_snapshot.get('confluence_score', 0):.2f}."
                    )
                elif "feedback" in command:
                    if any(x in command for x in ["laatste", "vorige", "laatst"]):
                        trade_data = app.trade_log[-1] if app.trade_log else {"signal": dream_snapshot.get("signal")}
                    else:
                        trade_data = {"signal": dream_snapshot.get("signal")}

                    reason = command.split("omdat", 1)[1].strip() if "omdat" in command else command
                    app.process_user_feedback(reason, trade_data)
                    app.speak("Thanks for the feedback. I will update my Bible.")
                elif any(x in command for x in ["goed", "goed trade", "goede trade", "was goed"]):
                    app.process_user_feedback("Dit was een goede trade", {"signal": dream_snapshot.get("signal")})
                    app.speak("Thanks for the positive feedback. I will adapt my strategy.")
                elif any(x in command for x in ["slecht", "slechte trade", "was slecht", "niet goed"]):
                    reason = (
                        command.split("omdat", 1)[1].strip() if "omdat" in command else "no specific reason provided"
                    )
                    app.process_user_feedback(
                        f"Dit was een slechte trade omdat {reason}", {"signal": dream_snapshot.get("signal")}
                    )
                    app.speak("Thanks for the feedback. I will improve this.")
                elif any(x in command for x in ["verbeter", "pas aan", "update"]):
                    app.process_user_feedback(command)
                    app.speak("Understood. I will update my Bible right away.")
                else:
                    app.speak(
                        "I heard you, but I do not fully understand the command. "
                        "Try: status, ga long, ga short, hold, dream, or feedback."
                    )
            elif len(text_lower) > 3:
                app.speak("I am still listening. Say 'Lumina' followed by your command.")

        except app.sr.UnknownValueError:
            pass
        except app.sr.RequestError as e:
            app.logger.error(f"Voice recognition error: {e}")
        except OSError as e:
            # No audio input device available - log once and exit voice thread cleanly.
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message="🎤 Voice input disabled: no microphone detected.",
                    context={"detail": str(e)},
                )
            )
            app.logger.warning(f"Voice input unavailable (no microphone): {e}")
            return
        except Exception as e:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="RUNTIME_VOICE_009",
                message=str(e),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            app.logger.error(f"Voice thread error: {e}")

        time.sleep(0.4)


def _old_supervisor_loop(app: RuntimeContext) -> None:
    try:
        _old_supervisor_loop_inner(app)
    except Exception as exc:
        err = LuminaError(
            severity=ErrorSeverity.FATAL_UNRECOVERABLE,
            code="SUPERVISOR_LOOP_CRASH",
            message=str(exc),
            context={"traceback": traceback.format_exc()},
        )
        log_structured(err)
        app.logger.error(f"supervisor_loop CRASHED: {exc}\n{traceback.format_exc()}")
        raise


def _old_supervisor_loop_inner(app: RuntimeContext) -> None:
    last_oracle = time.time()
    # Initialize last_validation to now so run_3year_validation() is never triggered
    # on the first iteration (the monthly_validation_daemon thread handles it).
    if getattr(app.engine, "last_validation", None) is None:
        app.engine.last_validation = datetime.now()
    last_save = time.time()
    last_balance_fetch = time.time()
    last_status_print = 0.0
    last_infinite_sim_status = 0.0
    twin_thread: threading.Thread | None = None
    swarm_last_cycle = 0.0
    swarm_last_cycle_minute: tuple[int, int, int, int, int] | None = None
    swarm_last_dashboard = 0.0
    valuation_engine = ValuationEngine()

    def _emotional_twin_worker() -> None:
        while True:
            try:
                twin = getattr(app, "emotional_twin_agent", None)
                if twin is not None and hasattr(twin, "run_cycle"):
                    twin.run_cycle()
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RUNTIME_TWIN_010",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                app.logger.error(f"EmotionalTwin cycle error: {exc}")
            time.sleep(60)

    if getattr(app, "emotional_twin_agent", None) is not None:
        twin_thread = threading.Thread(target=_emotional_twin_worker, name="emotional-twin-worker", daemon=True)
        twin_thread.start()

    _supervisor_loop_started = False
    while True:
        if not _supervisor_loop_started:
            app.logger.info("SUPERVISOR_LOOP_ENTER,status=first_iteration")
            _supervisor_loop_started = True
        with app.live_data_lock:
            price = (
                app.live_quotes[-1]["last"]
                if app.live_quotes
                else (app.ohlc_1min["close"].iloc[-1] if len(app.ohlc_1min) else 0.0)
            )

        now = datetime.now()

        # Optional monthly validator cycle (~every 30 days).
        validator = getattr(app.engine, "validator", None)
        last_validation = getattr(app.engine, "last_validation", None)
        if validator is not None and hasattr(validator, "run_3year_validation"):
            should_run_validation = last_validation is None or (now - last_validation).days >= 30
            if should_run_validation:
                try:
                    validator.run_3year_validation()
                    app.engine.last_validation = now
                except Exception as exc:
                    err = LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="RUNTIME_VALIDATOR_011",
                        message=str(exc),
                        context={"traceback": traceback.format_exc()},
                    )
                    log_structured(err)
                    app.logger.error(f"Periodic validator run failed: {exc}")

        if time.time() - last_balance_fetch > 10:
            _ops = getattr(getattr(app, "container", None), "operations_service", None)
            if _ops is not None:
                _ops.fetch_account_balance()
            last_balance_fetch = time.time()

        if app.engine.config.trade_mode == "real":
            current_realized_pnl = float(app.realized_pnl_today or 0.0)
            previous_realized_pnl = float(app.engine.last_realized_pnl_snapshot or 0.0)
            tracked_live_qty = int(app.engine.live_position_qty or 0)
            close_detected = (
                tracked_live_qty != 0
                and abs(float(app.open_pnl or 0.0)) < 0.01
                and abs(current_realized_pnl - previous_realized_pnl) > 0.0
            )
            if close_detected:
                realized_delta = current_realized_pnl - previous_realized_pnl
                reconciler = getattr(app, "trade_reconciler", None)
                if reconciler is not None and hasattr(reconciler, "mark_closing"):
                    try:
                        reconciler.mark_closing(
                            symbol=str(getattr(app, "INSTRUMENT", app.engine.config.instrument)),
                            signal=str(app.engine.live_trade_signal or "HOLD"),
                            entry_price=float(app.engine.last_entry_price or price),
                            detected_exit_price=float(price),
                            quantity=int(abs(tracked_live_qty)),
                            expected_pnl=float(realized_delta),
                            reflection={
                                "source": "real_close_detect",
                                "detected_realized_delta": float(realized_delta),
                            },
                            chart_base64=None,
                        )
                    except Exception as exc:
                        err = LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                            code="RUNTIME_RECONCILE_018",
                            message=str(exc),
                            context={"traceback": traceback.format_exc(), "mode": app.engine.config.trade_mode},
                        )
                        log_structured(err)
                        app.logger.error(f"TradeReconciler mark_closing error: {exc}")
                        _push_trader_league_trade(
                            app,
                            mode=app.engine.config.trade_mode,
                            symbol=str(getattr(app, "INSTRUMENT", app.engine.config.instrument)),
                            signal=str(app.engine.live_trade_signal or "HOLD"),
                            entry_price=float(app.engine.last_entry_price or price),
                            exit_price=float(price),
                            qty=int(abs(tracked_live_qty)),
                            pnl_dollars=float(realized_delta),
                            reflection={"reconciliation": {"status": "fallback_direct_push"}},
                            chart_base64=None,
                        )
                else:
                    _push_trader_league_trade(
                        app,
                        mode=app.engine.config.trade_mode,
                        symbol=str(getattr(app, "INSTRUMENT", app.engine.config.instrument)),
                        signal=str(app.engine.live_trade_signal or "HOLD"),
                        entry_price=float(app.engine.last_entry_price or price),
                        exit_price=float(price),
                        qty=int(abs(tracked_live_qty)),
                        pnl_dollars=float(realized_delta),
                        reflection={"reconciliation": {"status": "fallback_direct_push"}},
                        chart_base64=None,
                    )
                app.engine.live_position_qty = 0
                app.engine.last_entry_price = 0.0
                app.engine.live_trade_signal = "HOLD"
            app.engine.last_realized_pnl_snapshot = current_realized_pnl

        if app.engine.config.trade_mode == "real" and app.account_equity < app.account_balance * (
            1 - app.engine.config.drawdown_kill_percent / 100
        ):
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                    code="RUNTIME_DRAWDOWN_KILL",
                    message=f"🚨 REAL DRAWDOWN KILL ({app.engine.config.drawdown_kill_percent}%) - STOPPING",
                    context={"mode": "real"},
                )
            )
            app.save_state()
            raise SystemExit("Drawdown kill - real money")

        eod_force_hold = _enforce_real_eod_force_close(app, float(price))

        dream_snapshot = app.get_current_dream_snapshot()
        # Directe emotionele correctie op actieve dream vóór execution.
        twin = getattr(app.engine, "emotional_twin", None)
        if twin is not None and hasattr(twin, "apply_correction"):
            dream_snapshot = twin.apply_correction(dream_snapshot)
            app.set_current_dream_fields(dream_snapshot)
        swarm_manager = getattr(app, "swarm_manager", None) or getattr(app.engine, "swarm", None)
        current_swarm_minute = (now.year, now.month, now.day, now.hour, now.minute)
        should_run_swarm = (
            swarm_manager is not None and int(now.minute) % 5 == 0 and swarm_last_cycle_minute != current_swarm_minute
        )
        if should_run_swarm:
            try:
                swarm_info = swarm_manager.run_swarm_cycle()
                swarm_manager.apply_to_primary_dream()
                if isinstance(swarm_info, dict):
                    app.set_current_dream_fields(
                        {
                            "swarm_regime": swarm_info.get("global_regime", "NEUTRAL"),
                            "swarm_allocation": swarm_info.get("allocation", {}),
                        }
                    )
                dream_snapshot = app.get_current_dream_snapshot()
                swarm_last_cycle = time.time()
                swarm_last_cycle_minute = current_swarm_minute
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                    code="RUNTIME_SWARM_013",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                app.logger.error(f"Swarm cycle error: {exc}")

        hold_until_ts = float(dream_snapshot.get("hold_until_ts", 0.0) or 0.0)
        min_confluence = float(
            dream_snapshot.get("min_confluence_override", app.engine.config.min_confluence)
            or app.engine.config.min_confluence
        )
        qty_multiplier = float(dream_snapshot.get("position_size_multiplier", 1.0) or 1.0)
        stop_widen_multiplier = float(dream_snapshot.get("stop_widen_multiplier", 1.0) or 1.0)
        signal = dream_snapshot.get("signal", "HOLD")
        if eod_force_hold:
            signal = "HOLD"
            dream_snapshot["signal"] = "HOLD"
            dream_snapshot["why_no_trade"] = "REAL EOD force-close/no-new-trades window active"

        # RL bias: policy stuurt voorkeur, bestaande flow beslist uiteindelijk.
        rl_action = None
        baseline_signal = str(signal)
        try:
            if getattr(app.engine, "rl_env", None) is not None and getattr(app.engine, "ppo_trainer", None) is not None:
                obs = app.engine.rl_env._get_observation()
                rl_action = app.engine.ppo_trainer.predict_action(obs)

                shadow_state = getattr(app.engine, "rl_shadow_state", {})
                guarded_action, shadow_state = _RL_GUARDRAIL.apply(
                    rl_action=dict(rl_action or {}),
                    baseline_signal=baseline_signal,
                    regime=str(dream_snapshot.get("regime", "NEUTRAL")),
                    shadow_state=shadow_state if isinstance(shadow_state, dict) else {},
                )
                app.engine.rl_shadow_state = shadow_state
                rl_action = guarded_action

                rl_signal_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
                rl_signal = rl_signal_map.get(int(rl_action.get("signal", 0)), "HOLD")
                if rl_signal in {"BUY", "SELL"} and signal == "HOLD":
                    signal = rl_signal
                    dream_snapshot["signal"] = signal

                if rl_action.get("qty_pct") is not None:
                    qty_multiplier *= max(0.1, float(rl_action.get("qty_pct", 1.0)))
                if rl_action.get("stop_mult") is not None:
                    stop_widen_multiplier *= max(0.5, float(rl_action.get("stop_mult", 1.0)))
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="RUNTIME_RL_012",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)

        if signal == "HOLD":
            arb_signal = str(dream_snapshot.get("swarm_arb_signal", "HOLD")).upper()
            if arb_signal in {"BUY", "SELL"}:
                signal = arb_signal

        if not app.is_market_open():
            signal = "HOLD"
        if hold_until_ts > time.time():
            signal = "HOLD"

        # ── Hard Risk Controller ─ VERY FIRST execution gate (fail-closed) ────
        _risk_ctrl = getattr(app.engine, "risk_controller", None)
        _cfg = getattr(app.engine, "config", None)
        _inst = getattr(_cfg, "instrument", None) if _cfg is not None else None
        _instrument = str(getattr(app, "INSTRUMENT", None) or _inst or "MES")
        signal, _risk_ok, _risk_reason = apply_hard_risk_controller_to_signal(
            signal=str(signal),
            price=float(price),
            dream_snapshot=dream_snapshot,
            instrument=_instrument,
            risk_controller=_risk_ctrl,
            logger=app.logger,
        )

        session_allowed = True
        session_allowed, _session_reason = session_guard_allows_trading(app.engine)

        risk_allowed = bool(signal == "HOLD")
        if signal in ["BUY", "SELL"]:
            risk_allowed = bool(_risk_ok) if "_risk_ok" in locals() else False

        # ── Agent policy gateway ─ central mode/session/risk/confluence enforcement ────
        gate_result = apply_agent_policy_gateway(
            signal=str(signal),
            confluence_score=float(dream_snapshot.get("confluence_score", 0.0) or 0.0),
            min_confluence=float(min_confluence),
            hold_until_ts=float(hold_until_ts),
            mode=str(getattr(app.engine.config, "trade_mode", "paper")).strip().lower(),
            session_allowed=bool(session_allowed),
            risk_allowed=bool(risk_allowed),
            lineage={
                "model_identifier": str(dream_snapshot.get("chosen_strategy", "runtime-supervisor")),
                "prompt_version": "runtime-supervisor-v1",
                "prompt_hash": "runtime-supervisor",
                "policy_version": "agent-policy-gateway-v1",
                "provider_route": [
                    str(getattr(app.engine, "local_engine", None).active_provider)
                    if getattr(app.engine, "local_engine", None) is not None
                    else "unknown-provider"
                ],
                "calibration_factor": 1.0,
            },
        )
        signal = str(gate_result.get("signal", signal))

        if runtime_trace_enabled():
            _now_ts = time.time()
            _hut = float(hold_until_ts or 0.0)
            _hold_rem = max(0.0, _hut - _now_ts) if _hut > 0.0 else 0.0
            _hold_iso = ""
            if _hut > 0.0:
                try:
                    _hold_iso = datetime.fromtimestamp(_hut, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                except (OSError, ValueError, OverflowError):
                    _hold_iso = "invalid_timestamp"
            log_runtime_trace(
                app.logger,
                "supervisor.policy_gateway",
                trade_mode=str(getattr(app.engine.config, "trade_mode", "")),
                price=round(float(price), 4),
                signal=str(signal),
                conf=round(float(dream_snapshot.get("confluence_score", 0) or 0), 4),
                min_conf=round(float(min_confluence), 4),
                gateway_reason=str(gate_result.get("reason", "")),
                gateway_approved=str(bool(gate_result.get("approved", False))),
                session_allowed=str(bool(session_allowed)),
                risk_allowed=str(bool(risk_allowed)),
                sim_qty=int(getattr(app, "sim_position_qty", 0) or 0),
                regime=str(dream_snapshot.get("regime", "") or ""),
                market_open=str(bool(app.is_market_open())),
                hold_until_ts=round(_hut, 3),
                hold_until_utc=_hold_iso,
                hold_sec_remaining=round(_hold_rem, 1),
                hold_window_active=str(bool(_hut > _now_ts)),
            )

        if signal in ["BUY", "SELL"] and dream_snapshot.get("confluence_score", 0) > min_confluence:
            regime = dream_snapshot.get("regime", "NEUTRAL")
            stop_price = float(dream_snapshot.get("stop", price * 0.99 if signal == "BUY" else price * 1.01))
            widened_dist = abs(price - stop_price) * max(1.0, stop_widen_multiplier)
            stop_price = price - widened_dist if signal == "BUY" else price + widened_dist
            qty = app.calculate_adaptive_risk_and_qty(
                price,
                regime,
                stop_price,
                confidence=float(dream_snapshot.get("confluence_score", 0.0) or 0.0),
            )
            if qty <= 0:
                app.logger.warning(
                    "REAL_POSITION_FLOOR_HOLD,reason=insufficient_risk_budget,"
                    f"signal={signal},regime={regime}"
                )
                signal = "HOLD"
                qty = 0
                continue
            qty = max(1, int(qty * max(0.1, qty_multiplier)))
            side = 1 if signal == "BUY" else -1

            if runtime_trace_enabled():
                log_runtime_trace(
                    app.logger,
                    "supervisor.execution_armed",
                    trade_mode=str(app.engine.config.trade_mode),
                    signal=str(signal),
                    qty=int(qty),
                    stop=round(float(stop_price), 4),
                    conf=round(float(dream_snapshot.get("confluence_score", 0) or 0), 4),
                )

            if app.engine.config.trade_mode == "paper":
                if app.sim_position_qty == 0:
                    container = getattr(app, "container", None)
                    broker = getattr(container, "broker", None) if container is not None else None
                    submit_ok = True
                    if broker is not None:
                        submit_result = broker.submit_order(
                            Order(
                                symbol=str(getattr(app, "INSTRUMENT", app.engine.config.instrument)),
                                side=str(signal).upper(),
                                quantity=int(qty),
                                order_type="MARKET",
                                stop_loss=float(dream_snapshot.get("stop", 0.0) or 0.0),
                                take_profit=float(dream_snapshot.get("target", 0.0) or 0.0),
                                metadata={"regime": str(regime)},
                            )
                        )
                        submit_ok = bool(getattr(submit_result, "accepted", False))

                    if submit_ok:
                        app.sim_position_qty = qty if signal == "BUY" else -qty
                        est_slip_ticks = valuation_engine.slippage_ticks(
                            volume=1.0,
                            avg_volume=1.0,
                            regime=str(regime),
                            slippage_scale=1.0,
                        )
                        app.sim_entry_price = valuation_engine.apply_entry_fill(
                            symbol=str(getattr(app, "INSTRUMENT", app.engine.config.instrument)),
                            price=float(price),
                            side=side,
                            slippage_ticks=est_slip_ticks,
                        )
                        log_structured(
                            LuminaError(
                                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                                code="INFO_PRINT_LEGACY",
                                message=f"📍 PAPER {signal} {qty}x @ {app.sim_entry_price:.2f} (adaptive risk)",
                                context={"mode": "paper", "signal": signal, "qty": qty},
                            )
                        )
                    else:
                        app.logger.warning("Paper broker rejected simulated order")
            else:
                if app.place_order(signal, qty):
                    log_structured(
                        LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_LEARNING,
                            code="INFO_PRINT_LEGACY",
                            message=f"✅ {app.engine.config.trade_mode.upper()} {signal} {qty}x @ {price:.2f} (regime-adapted)",
                            context={"mode": app.engine.config.trade_mode, "signal": signal, "qty": qty},
                        )
                    )

        if app.engine.config.trade_mode == "paper":
            if app.sim_position_qty != 0:
                app.open_pnl = valuation_engine.pnl_dollars(
                    symbol=str(getattr(app, "INSTRUMENT", app.engine.config.instrument)),
                    entry_price=float(app.sim_entry_price),
                    exit_price=float(price),
                    side=1 if app.sim_position_qty > 0 else -1,
                    quantity=abs(int(app.sim_position_qty)),
                )
            else:
                app.open_pnl = 0.0
        else:
            app.open_pnl = app.account_equity - app.account_balance

        if app.sim_position_qty != 0:
            stop = dream_snapshot.get("stop", 0)
            target = dream_snapshot.get("target", 0)
            hit_stop = (app.sim_position_qty > 0 and price <= stop) or (app.sim_position_qty < 0 and price >= stop)
            hit_target = (app.sim_position_qty > 0 and price >= target) or (
                app.sim_position_qty < 0 and price <= target
            )

            if hit_stop or hit_target:
                pnl_dollars = valuation_engine.pnl_dollars(
                    symbol=str(getattr(app, "INSTRUMENT", app.engine.config.instrument)),
                    entry_price=float(app.sim_entry_price),
                    exit_price=float(price),
                    side=1 if app.sim_position_qty > 0 else -1,
                    quantity=abs(int(app.sim_position_qty)),
                )
                app.pnl_history.append(pnl_dollars)
                app.equity_curve.append(app.equity_curve[-1] + pnl_dollars)
                if app.equity_curve[-1] > app.sim_peak:
                    app.sim_peak = app.equity_curve[-1]

                app.trade_log.append(
                    {
                        "ts": now.isoformat(),
                        "signal": dream_snapshot.get("signal"),
                        "entry": app.sim_entry_price,
                        "exit": price,
                        "qty": app.sim_position_qty,
                        "pnl": pnl_dollars,
                        "confluence": dream_snapshot.get("confluence_score", 0),
                    }
                )

                app.reflect_on_trade(pnl_dollars, app.sim_entry_price, price, abs(app.sim_position_qty))

                regime = dream_snapshot.get("regime", "NEUTRAL")
                app.update_performance_log(
                    {
                        "signal": dream_snapshot.get("signal"),
                        "chosen_strategy": dream_snapshot.get("chosen_strategy"),
                        "regime": regime,
                        "confluence": dream_snapshot.get("confluence_score", 0),
                        "pnl": pnl_dollars,
                        "drawdown": (app.sim_peak - app.equity_curve[-1]) / app.sim_peak if app.sim_peak else 0,
                    }
                )

                publish_fn = getattr(app, "publish_traderleague_trade_close", None)
                if callable(publish_fn):
                    try:
                        latest_reflection = ""
                        if getattr(app, "trade_reflection_history", None):
                            latest_reflection = str(app.trade_reflection_history[-1].get("reflection", ""))
                        publish_fn(
                            symbol=str(getattr(app, "INSTRUMENT", getattr(app.engine.config, "instrument", "MES"))),
                            entry_price=float(app.sim_entry_price),
                            exit_price=float(price),
                            quantity=int(abs(app.sim_position_qty)),
                            pnl=float(pnl_dollars),
                            reflection=latest_reflection,
                            chart_snapshot_url=str(getattr(app, "current_live_chart_file", "") or ""),
                        )
                    except Exception as exc:
                        err = LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                            code="RUNTIME_LEAGUE_014",
                            message=str(exc),
                            context={"traceback": traceback.format_exc()},
                        )
                        log_structured(err)
                        app.logger.error(f"TraderLeague publish error: {exc}")

                if swarm_manager is not None and hasattr(swarm_manager, "register_trade_result"):
                    try:
                        symbol = getattr(app, "INSTRUMENT", app.engine.config.instrument)
                        swarm_manager.register_trade_result(symbol, pnl_dollars)
                    except Exception as exc:
                        err = LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                            code="RUNTIME_SWARM_015",
                            message=str(exc),
                            context={"traceback": traceback.format_exc()},
                        )
                        log_structured(err)
                        app.logger.error(f"Swarm trade register error: {exc}")

                if app.engine.config.trade_mode == "paper":
                    reflection_payload = {}
                    chart_payload = None
                    _push_trader_league_trade(
                        app,
                        mode=app.engine.config.trade_mode,
                        symbol=str(getattr(app, "INSTRUMENT", app.engine.config.instrument)),
                        signal=str(dream_snapshot.get("signal")),
                        entry_price=float(app.sim_entry_price),
                        exit_price=float(price),
                        qty=int(abs(app.sim_position_qty)),
                        pnl_dollars=float(pnl_dollars),
                        reflection=reflection_payload,
                        chart_base64=chart_payload,
                    )

                app.sim_position_qty = 0
                app.sim_entry_price = 0.0
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="INFO_PRINT_LEGACY",
                        message=f"🎯 TRADE CLOSED → {'WIN' if pnl_dollars > 0 else 'LOSS'} ${pnl_dollars:.0f}",
                        context={"pnl": pnl_dollars, "mode": app.engine.config.trade_mode},
                    )
                )

                # Immediate post-trade reflection via RealisticBacktesterEngine
                try:
                    with app.live_data_lock:
                        bt_snapshot = app.ohlc_1min.tail(500).copy()
                    if len(bt_snapshot) >= 60:
                        bt_result = app.engine.backtester.run_backtest_on_snapshot(bt_snapshot)
                        app.log_thought(
                            {"type": "trade_reflection_backtest", "pnl": pnl_dollars, "backtest": bt_result}
                        )
                        log_structured(
                            LuminaError(
                                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                                code="INFO_PRINT_LEGACY",
                                message=(
                                    f"🔬 POST-TRADE BACKTEST → "
                                    f"Sharpe {bt_result['sharpe']:.2f} | WR {bt_result['winrate']:.1%} | "
                                    f"MaxDD {bt_result['maxdd']:.1f}% | AvgPnL ${bt_result['avg_pnl']:.1f}"
                                ),
                                context={"pnl": pnl_dollars, "backtest": bt_result},
                            )
                        )
                except Exception as exc:
                    err = LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="RUNTIME_BACKTEST_016",
                        message=str(exc),
                        context={"traceback": traceback.format_exc()},
                    )
                    log_structured(err)
                    app.logger.error(f"Post-trade backtest error: {exc}")

        if swarm_manager is not None and time.time() - swarm_last_dashboard >= 60:
            try:
                dashboard_path = swarm_manager.generate_dashboard_plot()
                if dashboard_path:
                    app.set_current_dream_value("swarm_dashboard_path", dashboard_path)
                swarm_last_dashboard = time.time()
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RUNTIME_SWARM_017",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                app.logger.error(f"Swarm dashboard error: {exc}")

        mode_text = {"paper": "PAPER (internal sim)", "sim": "SIM (real orders on demo)", "real": "REAL MONEY"}.get(
            app.engine.config.trade_mode, app.engine.config.trade_mode.upper()
        )
        if time.time() - last_status_print >= app.engine.config.status_print_interval_sec:
            rl_bias = ""
            if isinstance(rl_action, dict):
                rl_bias = f" | RL {int(rl_action.get('signal', 0))}:{float(rl_action.get('qty_pct', 1.0)):.2f}"
            app.logger.info(
                f"Status [{mode_text}] | Equity ${app.account_equity:,.0f} | "
                f"Open PnL ${app.open_pnl:,.0f} | Realized ${app.realized_pnl_today:,.0f} | "
                f"Conf {dream_snapshot.get('confluence_score', 0):.2f}{rl_bias}"
            )
            last_status_print = time.time()

        # Optionele live-monitoring: elke 30 minuten simulatorstatus loggen.
        if time.time() - last_infinite_sim_status >= 1800:
            if hasattr(app.engine, "infinite_simulator") and app.engine.infinite_simulator is not None:
                app.logger.info("INFINITE_SIM_MONITOR,status=ready")
            last_infinite_sim_status = time.time()

        if time.time() - last_oracle > 60 and len(app.pnl_history) > 5:
            returns = app.np.array(app.pnl_history[-50:])
            sharpe = (app.np.mean(returns) / (app.np.std(returns) + 1e-8)) * app.np.sqrt(252) if len(returns) > 1 else 0
            winrate = app.np.mean(app.np.array(app.pnl_history) > 0) if app.pnl_history else 0
            expectancy = app.np.mean(app.pnl_history) if app.pnl_history else 0
            profit_factor = (
                abs(sum([p for p in app.pnl_history if p > 0]) / sum([abs(p) for p in app.pnl_history if p < 0]) + 1e-8)
                if any(p < 0 for p in app.pnl_history)
                else 0
            )
            maxdd = (
                min(
                    (app.np.maximum.accumulate(app.equity_curve) - app.equity_curve)
                    / app.np.maximum.accumulate(app.equity_curve)
                )
                * 100
                if len(app.equity_curve) > 1
                else 0
            )
            app.logger.info(
                f"ORACLE metrics | Sharpe {sharpe:.2f} | Expected ${expectancy:.0f} | Winrate {winrate:.1%} | PF {profit_factor:.2f} | MaxDD {maxdd:.1f}%"
            )

        if time.time() - last_save > 30:
            try:
                app.save_state()
                app.logger.info("STATE_SAVED,status=ok")
            except Exception as _save_exc:
                app.logger.error(f"STATE_SAVE_FAILED: {_save_exc}\n{traceback.format_exc()}")
            last_save = time.time()

        time.sleep(1)


def run_forever_loop(app: RuntimeContext) -> None:
    supervisor_loop(app)


def state_persist_daemon(app: RuntimeContext, interval_seconds: int = 30) -> None:
    """Persist runtime state on a fixed cadence, independent from supervisor loop latency."""
    interval = max(5, int(interval_seconds))
    while True:
        try:
            app.save_state()
        except Exception as exc:
            app.logger.error(f"STATE_PERSIST_DAEMON_FAILED: {exc}\n{traceback.format_exc()}")
        time.sleep(interval)


def supervisor_loop(app: RuntimeContext) -> None:
    _old_supervisor_loop(app)
