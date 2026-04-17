# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

import requests


def _parse_json_loose(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _infer_json(app: Any, payload: dict[str, Any], timeout: int, context: str) -> dict[str, Any] | None:
    infer_json_fn = getattr(app, "infer_json", None)
    if callable(infer_json_fn):
        data = infer_json_fn(payload, timeout=timeout, context=context)
        if isinstance(data, dict):
            return data

    post_xai_fn = getattr(app, "post_xai_chat", None)
    if not callable(post_xai_fn):
        return None
    response = post_xai_fn(payload, timeout=timeout, context=context)
    if not response or response.status_code != 200:
        return None

    content = response.json()["choices"][0]["message"]["content"]
    parsed = _parse_json_loose(content)
    return parsed if isinstance(parsed, dict) else None


def _post_reflection_to_lumina_os(app: Any, ref_json: dict[str, Any], pnl_dollars: float) -> None:
    api_base_url = str(os.getenv("LUMINA_OS_API_URL", "http://localhost:8000")).rstrip("/")
    trader_name = str(
        os.getenv("LUMINA_TRADER_NAME")
        or os.getenv("TRADERLEAGUE_PARTICIPANT_HANDLE")
        or "LUMINA_Steve"
    )
    payload = {
        "trader_name": trader_name,
        "reflection": str(ref_json.get("reflection", "")),
        "key_lesson": str(ref_json.get("key_lesson", "")),
        "suggested_update": ref_json.get("suggested_bible_update", {}),
        "pnl_impact": float(pnl_dollars),
    }
    try:
        requests.post(f"{api_base_url}/upload/reflection", json=payload, timeout=1.5)
    except requests.RequestException as exc:
        app.logger.debug(f"Reflection upload skipped: {exc}")


def reflect_on_trade(app: Any, pnl_dollars: float, entry_price: float, exit_price: float, position_qty: int) -> None:
    try:
        with app.live_data_lock:
            app.ohlc_1min.copy()

        chart_base64 = app.generate_multi_tf_chart(app.AI_DRAWN_FIBS if isinstance(app.AI_DRAWN_FIBS, dict) else {})

        reflection_prompt = [
            {
                "type": "text",
                "text": f"""Je hebt net een trade gesloten.
Resultaat: {'WIN' if pnl_dollars > 0 else 'LOSS'} van ${pnl_dollars:.0f}
Entry: {entry_price:.2f} | Exit: {exit_price:.2f} | Qty: {position_qty}
Kijk terug naar de chart image en je eigen vorige narrative_reasoning.
Schrijf een eerlijke 'lessons learned' in het veld 'reflection'.
Geef ALLEEN JSON met: reflection (max 400 chars), key_lesson, suggested_bible_update""",
            },
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart_base64}" if chart_base64 else ""}},
        ]

        payload = {
            "model": app.engine.config.vision_model,
            "messages": [
                {"role": "system", "content": "Je bent een eerlijke trading coach. Leer van elke trade en update de bible."},
                {"role": "user", "content": reflection_prompt},
            ],
            "max_tokens": 600,
            "temperature": 0.1,
        }

        ref_json = _infer_json(app, payload, timeout=35, context="reflect_on_trade")
        if not ref_json:
            return

        app.trade_reflection_history.append(
            {
                "ts": datetime.now().isoformat(),
                "pnl": pnl_dollars,
                "reflection": ref_json.get("reflection", ""),
                "key_lesson": ref_json.get("key_lesson", ""),
                "suggested_bible_update": ref_json.get("suggested_bible_update", {}),
            }
        )

        bible_engine = getattr(app, "bible_engine", None)
        if hasattr(bible_engine, "add_community_reflection"):
            bible_engine.add_community_reflection(ref_json)

        _post_reflection_to_lumina_os(app, ref_json, pnl_dollars)

        if ref_json.get("suggested_bible_update"):
            app.engine.evolve_bible(ref_json["suggested_bible_update"])

        app.logger.info(f"REFLECTION_COMPLETE,pnl={pnl_dollars:.0f},lesson={ref_json.get('key_lesson','N/A')[:80]}")

        reflection_text = ref_json.get("reflection", "No reflection")
        app.speak(f"Trade reflection: {reflection_text}")

        if app.engine.config.discord_webhook:
            try:
                requests.post(
                    app.engine.config.discord_webhook,
                    json={
                        "content": f"**LUMINA REFLECTION**\\nResultaat: {'WIN' if pnl_dollars > 0 else 'LOSS'} ${pnl_dollars:.0f}\\n{reflection_text}"
                    },
                    timeout=5,
                )
            except requests.RequestException as exc:
                app.logger.error(f"Discord webhook error: {exc}")
    except Exception as exc:
        app.logger.error(f"REFLECTION_CRASH: {exc}")


def process_user_feedback(app: Any, feedback_text: str, trade_data: dict | None = None) -> None:
    app.store_experience_to_vector_db(
        context=f"User Feedback: {feedback_text}",
        metadata={
            "type": "user_feedback",
            "date": datetime.now().isoformat(),
            "trade_signal": trade_data.get("signal") if trade_data else "unknown",
            "pnl": trade_data.get("pnl") if trade_data else 0,
        },
    )

    payload = {
        "model": "grok-4.20-0309-reasoning",
        "messages": [
            {
                "role": "system",
                "content": "Je bent een trading-coach. Verwerk user feedback en stel concrete updates voor evolvable_layer voor. Geef ALLEEN JSON.",
            },
            {
                "role": "user",
                "content": f"""User feedback: {feedback_text}
Laatste trade: {trade_data}
Huidige evolvable_layer: {json.dumps(app.bible['evolvable_layer'])}
Stel verbeteringen voor.""",
            },
        ],
        "temperature": 0.1,
    }

    try:
        update = _infer_json(app, payload, timeout=20, context="process_user_feedback")
        if update and update.get("suggested_bible_updates"):
            app.engine.evolve_bible(update["suggested_bible_updates"])
    except Exception as exc:
        app.logger.error(f"Feedback processing error: {exc}")


def dna_rewrite_daemon(app: Any, interval_seconds: int = 900) -> None:
    while True:
        try:
            if len(app.trade_log) > 5:
                recent = app.trade_log[-15:]
                winrate = len([t for t in recent if t["pnl"] > 0]) / len(recent)
                avg_pnl = app.np.mean([t["pnl"] for t in recent])
                summary = f"Winrate laatste 15: {winrate:.1%} | Avg PnL ${avg_pnl:.0f}"
                payload = {
                    "model": "grok-4.20-0309-reasoning",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Je bent LUMINA Bible Evolutie Engine. Sacred Core is HEILIG. Verbeter alleen evolvable_layer. Geef ALLEEN JSON.",
                        },
                        {
                            "role": "user",
                            "content": f"Huidige evolvable_layer:\n{json.dumps(app.bible['evolvable_layer'])}\nPerformance: {summary}\nOptimaliseer voor hogere Sharpe.",
                        },
                    ],
                    "temperature": 0.1,
                }

                new_layer = _infer_json(app, payload, timeout=22, context="dna_rewrite")
                if isinstance(new_layer, dict) and new_layer:
                    app.bible["evolvable_layer"] = new_layer
                    app.engine.bible_engine.save()
                    bible_engine = getattr(app, "bible_engine", None)
                    if hasattr(bible_engine, "evolve_from_community"):
                        bible_engine.evolve_from_community()
                    app.log_thought({"type": "bible_evolution"})
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            app.logger.error(f"DNA rewrite error: {exc}")
        time.sleep(interval_seconds)
