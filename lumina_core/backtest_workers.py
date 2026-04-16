import time
from datetime import datetime
from typing import Any

from lumina_core.backtester_engine import BacktesterEngine
from lumina_core.runtime_context import RuntimeContext


def run_backtest_on_snapshot(app: RuntimeContext, snapshot: list[dict[str, Any]]) -> None:
    print(f"🔬 Auto-backtest started on {len(snapshot)} ticks")
    results = BacktesterEngine(app=app).generate_full_report(snapshot)

    trades = int(results.get("trades", 0))
    if trades <= 0:
        print("Auto-backtest: no trades")
        return

    sharpe = float(results.get("sharpe", 0.0))
    winrate = float(results.get("winrate", 0.0))
    maxdd = float(results.get("maxdd", 0.0))
    net_pnl = float(results.get("net_pnl", 0.0))
    avg_slip = float(results.get("avg_slippage_ticks", 0.0))
    commission_paid = float(results.get("commission_paid", 0.0))

    mc = dict(results.get("monte_carlo", {}))
    wf = dict(results.get("walk_forward", {}))
    wfo = dict(results.get("walk_forward_optimization", {}))

    print(
        "🔥 AUTO-BACKTEST COMPLETE -> "
        f"Sharpe {sharpe:.2f} | Winrate {winrate:.1%} | MaxDD {maxdd:.1f}% | "
        f"Net ${net_pnl:.2f} | Slip {avg_slip:.2f} ticks | Fees ${commission_paid:.2f}"
    )
    print(
        "🎲 MC(1000) -> "
        f"Mean ${float(mc.get('mean_pnl', 0.0)):.2f} | "
        f"P05 ${float(mc.get('p05', 0.0)):.2f} | "
        f"P50 ${float(mc.get('p50', 0.0)):.2f} | "
        f"P95 ${float(mc.get('p95', 0.0)):.2f}"
    )
    print(
        "🧪 Walk-forward -> "
        f"windows {int(wf.get('windows', 0))} | "
        f"mean pnl ${float(wf.get('mean_pnl', 0.0)):.2f} | "
        f"mean sharpe {float(wf.get('mean_sharpe', 0.0)):.2f} | "
        f"mean winrate {float(wf.get('mean_winrate', 0.0)):.1%}"
    )
    print(
        "⚙️ Walk-forward optimization (30d) -> "
        f"windows {int(wfo.get('windows', 0))} | "
        f"mean test pnl ${float(wfo.get('mean_test_pnl', 0.0)):.2f} | "
        f"mean test sharpe {float(wfo.get('mean_test_sharpe', 0.0)):.2f}"
    )
    print(
        "📊 Backtest artifacts -> "
        f"json: {results.get('report_json_path', '')} | "
        f"dashboard: {results.get('dashboard_plot_path', '')}"
    )

    app.log_thought(
        {
            "type": "auto_backtest_result",
            "sharpe": sharpe,
            "winrate": winrate,
            "maxdd": maxdd,
            "net_pnl": net_pnl,
            "avg_slippage_ticks": avg_slip,
            "commission_paid": commission_paid,
            "monte_carlo": mc,
            "walk_forward": wf,
            "walk_forward_optimization": wfo,
            "regime_attribution": results.get("regime_attribution", {}),
            "report_json_path": results.get("report_json_path", ""),
            "dashboard_plot_path": results.get("dashboard_plot_path", ""),
        }
    )


def auto_backtester_daemon(app: RuntimeContext) -> None:
    while True:
        time.sleep(2700)
        with app.live_data_lock:
            if len(app.ohlc_1min) >= 7200 and not app.is_market_open():
                snapshot = app.ohlc_1min.tail(14400).copy()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔬 Starting ADVANCED backtest...")

                # 1. Realistic base
                base_res = app.engine.backtester.run_backtest_on_snapshot(snapshot)

                # 2. Walk-Forward
                wf = app.engine.advanced_backtester.walk_forward_test(snapshot)

                # 3. Regime OOS
                regime_res = app.engine.advanced_backtester.regime_specific_oos(snapshot)

                # 4. Monte Carlo (800 runs voor snelheid op 1080 Ti)
                monte = app.engine.advanced_backtester.full_monte_carlo(snapshot, runs=800)

                # 5. Dashboard
                dashboard_path = app.engine.advanced_backtester.generate_regime_dashboard(
                    snapshot, wf, monte, regime_res
                )

                app.log_thought({
                    "type": "advanced_backtest",
                    "base": base_res,
                    "walk_forward": wf,
                    "regime_oos": regime_res,
                    "monte_carlo": monte,
                })

                worst_regime_dd = max((v["maxdd"] for v in regime_res.values()), default=0.0)
                print(f"✅ ADVANCED BACKTEST COMPLETE")
                print(f"   Walk-Forward avg Sharpe : {wf['avg_test_sharpe']:.2f}")
                print(f"   Worst regime MaxDD      : {worst_regime_dd:.1f}%")
                print(f"   Monte Carlo worst DD    : {monte['worst_maxdd']:.1f}%")
                print(f"   Dashboard saved → {dashboard_path}")

                # Nightly PPO training alleen bij voldoende basisperformance.
                base_sharpe = float(base_res.get("sharpe", 0.0)) if isinstance(base_res, dict) else 0.0
                if base_sharpe > 1.2 and getattr(app.engine, "ppo_trainer", None) is not None:
                    print(
                        f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Nightly PPO train trigger "
                        f"(base sharpe {base_sharpe:.2f})"
                    )
                    app.engine.ppo_trainer.train(total_timesteps=50000)

                # Nightly infinite simulation om 03:00 (1x per kalenderdag).
                now_dt = datetime.now()
                today = now_dt.date().isoformat()
                _sim_results: dict[str, Any] = {}
                if now_dt.hour == 3 and getattr(app.engine, "infinite_simulator", None) is not None:
                    if getattr(app.engine, "infinite_sim_last_run_date", None) != today:
                        print("🌌 Nightly Infinite Simulation started...")
                        simulator = app.engine.infinite_simulator
                        if hasattr(simulator, "run_nightly_simulation"):
                            _sim_results = simulator.run_nightly_simulation(num_trades_total=1_000_000)
                        else:
                            _sim_results = simulator.run_nightly()
                        app.engine.infinite_sim_last_run_date = today

                # Nightly EmotionalTwin training om 04:00 (1x per kalenderdag).
                if now_dt.hour == 4 and getattr(app.engine, "emotional_twin", None) is not None:
                    if getattr(app.engine, "emotional_twin_last_train_date", None) != today:
                        print("🧠 Nightly EmotionalTwin training started...")
                        reflections = list(getattr(app, "trade_reflection_history", []) or [])
                        feedback = list(getattr(app, "user_feedback_history", []) or [])
                        app.engine.emotional_twin.nightly_train(reflections, feedback)
                        app.engine.emotional_twin_last_train_date = today

                # Ultimate validation na nightly cycle (3y swarm + paper vs real).
                validator = getattr(app.engine, "validator", None)
                if validator is not None and hasattr(validator, "run_3year_validation"):
                    try:
                        validation_report = validator.run_3year_validation()
                        comparison = validator.live_paper_vs_real_comparison()
                        app.log_thought(
                            {
                                "type": "ultimate_validation",
                                "report": validation_report,
                                "paper_vs_real": comparison,
                            }
                        )
                    except Exception as exc:
                        app.logger.error(f"Ultimate validation cycle failed: {exc}")

                orchestrator = getattr(app.engine, "meta_agent_orchestrator", None)
                if orchestrator is not None and hasattr(orchestrator, "run_nightly_reflection"):
                    try:
                        nightly_report = {
                            "trades": int(_sim_results.get("trades", 0) if isinstance(_sim_results, dict) else 0),
                            "wins": int(_sim_results.get("wins", 0) if isinstance(_sim_results, dict) else 0),
                            "winrate": float(_sim_results.get("winrate", 0.0) if isinstance(_sim_results, dict) else 0.0),
                            "net_pnl": float(_sim_results.get("net_pnl", 0.0) if isinstance(_sim_results, dict) else 0.0),
                            "sharpe": float(_sim_results.get("mean_worker_sharpe", 0.0) if isinstance(_sim_results, dict) else 0.0),
                            "advanced_backtest": {
                                "base": base_res,
                                "walk_forward": wf,
                                "regime_oos": regime_res,
                                "monte_carlo": monte,
                            },
                        }
                        orchestrator.run_nightly_reflection(
                            nightly_report=nightly_report,
                            dry_run=str(getattr(app.engine.config, "trade_mode", "paper")).strip().lower() in {"sim", "paper"},
                        )
                    except Exception as exc:
                        app.logger.error(f"Meta-agent nightly reflection failed: {exc}")
