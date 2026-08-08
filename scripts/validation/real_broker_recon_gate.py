#!/usr/bin/env python3
"""T4: REAL broker reconciliation config gate (fail-closed; never arms capital).

Usage:
  python scripts/validation/real_broker_recon_gate.py
  python scripts/validation/real_broker_recon_gate.py --mode real --reconcile-fills true
  python scripts/validation/real_broker_recon_gate.py --from-config
  python scripts/validation/real_broker_recon_gate.py --json

Also runs trade_reconciler synthetic self-test when --self-test is set.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _bool_arg(value: str) -> bool:
    v = str(value or "").strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected bool, got {value!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REAL broker recon gate (T4)")
    parser.add_argument("--mode", type=str, default="real", help="Trade mode to evaluate")
    parser.add_argument(
        "--reconcile-fills",
        type=_bool_arg,
        default=True,
        help="reconcile_fills flag (default true)",
    )
    parser.add_argument("--method", type=str, default="websocket", help="reconciliation_method")
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="reconciliation_timeout_seconds",
    )
    parser.add_argument(
        "--from-config",
        action="store_true",
        help="Load reconcile flags from EngineConfig / env defaults",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Also run TradeReconciler.run_self_test() synthetic",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from lumina_core.engine.trade_reconciler.real_recon_gate import (
        evaluate_real_broker_recon_gate,
    )

    mode = args.mode
    reconcile = args.reconcile_fills
    method = args.method
    timeout = args.timeout
    nt_enabled = None
    live_broker = None

    if args.from_config:
        try:
            from lumina_core.engine.engine_config import EngineConfig

            cfg = EngineConfig()
            mode = str(cfg.trade_mode or mode)
            reconcile = bool(cfg.reconcile_fills)
            method = str(cfg.reconciliation_method or method)
            timeout = float(cfg.reconciliation_timeout_seconds or timeout)
            nt_enabled = bool(getattr(cfg, "ninjatrader_enabled", True))
            live_broker = bool(getattr(cfg, "live_provider", None) or nt_enabled)
        except Exception as exc:
            result = {
                "ok": False,
                "reason": f"config_load_failed:{exc}",
            }
            print(json.dumps(result, indent=2) if args.json else f"real_broker_recon_gate ok=False {result}")
            return 1

    gate = evaluate_real_broker_recon_gate(
        trade_mode=mode,
        reconcile_fills=reconcile,
        reconciliation_method=method,
        reconciliation_timeout_seconds=timeout,
        live_broker_configured=live_broker,
        ninjatrader_enabled=nt_enabled,
    )

    payload: dict = {"gate": gate}
    if args.self_test:
        try:
            from scripts.validation.trade_reconciler_self_test import _build_runtime

            rec = _build_runtime()
            payload["self_test"] = rec.run_self_test()
            payload["self_test_ok"] = str(payload["self_test"].get("status", "")).lower() in {
                "ok",
                "passed",
                "pass",
            }
        except Exception as exc:
            # Fallback: instantiate without scripts import side effects
            try:
                from types import ModuleType, SimpleNamespace
                from typing import cast
                import logging
                from lumina_core.engine import EngineConfig, TradeReconciler
                from lumina_core.engine.lumina_engine import LuminaEngine

                cfg = EngineConfig(
                    state_file=ROOT / "state" / "selftest_state.json",
                    thought_log=ROOT / "state" / "selftest_thought_log.jsonl",
                    bible_file=ROOT / "state" / "selftest_bible.json",
                    live_jsonl=ROOT / "state" / "selftest_live.jsonl",
                )
                engine = LuminaEngine(config=cfg)
                app = SimpleNamespace(
                    logger=logging.getLogger("trade-reconciler-gate"),
                    push_traderleague_trade=lambda **_k: None,
                    publish_traderleague_trade_close=lambda **_k: True,
                    log_thought=lambda _p: None,
                )
                engine.bind_app(cast(ModuleType, app))
                st = TradeReconciler(engine=engine).run_self_test()
                payload["self_test"] = st
                payload["self_test_ok"] = True
            except Exception as exc2:
                payload["self_test"] = {"error": str(exc2), "prior": str(exc)}
                payload["self_test_ok"] = False

    ok = bool(gate.get("ok"))
    if "self_test_ok" in payload:
        ok = ok and bool(payload["self_test_ok"])
    payload["ok"] = ok

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
    else:
        print(f"real_broker_recon_gate ok={ok} mode={gate.get('trade_mode')}")
        print(f"  {gate.get('message')}")
        if gate.get("failures"):
            for f in gate["failures"]:
                print(f"  - {f}")
        print(f"  runbook={gate.get('runbook')}")
        if "self_test" in payload:
            print(f"  self_test_ok={payload.get('self_test_ok')}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
