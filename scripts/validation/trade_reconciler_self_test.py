from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import websockets
from dotenv import load_dotenv

from lumina_core.engine import EngineConfig, TradeReconciler
from lumina_core.engine.lumina_engine import LuminaEngine


def _build_runtime() -> TradeReconciler:
    cfg = EngineConfig(
        state_file=Path("state/selftest_state.json"),
        thought_log=Path("state/selftest_thought_log.jsonl"),
        bible_file=Path("state/selftest_bible.json"),
        live_jsonl=Path("state/selftest_live.jsonl"),
    )
    engine = LuminaEngine(config=cfg)
    app = SimpleNamespace(
        logger=logging.getLogger("trade-reconciler-self-test"),
        push_traderleague_trade=lambda **_kwargs: None,
        publish_traderleague_trade_close=lambda **_kwargs: True,
        log_thought=lambda _payload: None,
    )
    engine.bind_app(cast(ModuleType, app))
    return TradeReconciler(engine=engine)


async def _capture_live_sample(reconciler: TradeReconciler, timeout_seconds: float) -> dict:
    uri = reconciler.engine.config.crosstrade_fill_ws_url
    headers = {"Authorization": f"Bearer {reconciler.engine.config.crosstrade_token or ''}"}
    account = reconciler.engine.config.crosstrade_account
    async with websockets.connect(uri, additional_headers=headers, ping_interval=None, ping_timeout=None) as ws:
        await ws.send(json.dumps({"action": "subscribe", "accounts": [account], "channels": ["fills", "executions"]}))
        while True:
            message = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
            payload = json.loads(message)
            normalized = reconciler._normalize_fill_event(payload)
            if normalized is None:
                continue
            return {
                "raw_payload": payload,
                "normalized": {
                    "fill_id": normalized.fill_id,
                    "symbol": normalized.symbol,
                    "side": normalized.side,
                    "quantity": normalized.quantity,
                    "price": normalized.price,
                    "commission": normalized.commission,
                    "event_ts": normalized.event_ts.isoformat(),
                },
            }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="TradeReconciler synthetic/live self-test")
    parser.add_argument("--live-window-seconds", type=float, default=0.0, help="Optional live websocket sample timeout")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    reconciler = _build_runtime()

    synthetic = reconciler.run_self_test()
    print("=== Synthetic self-test ===")
    print(json.dumps(synthetic, ensure_ascii=False, indent=2))

    if args.live_window_seconds > 0:
        print("=== Live websocket sample ===")
        try:
            result = asyncio.run(_capture_live_sample(reconciler, args.live_window_seconds))
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as exc:
            print(json.dumps({"status": "live_sample_failed", "error": str(exc)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
