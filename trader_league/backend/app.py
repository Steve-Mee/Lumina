from datetime import datetime, timezone
import json
import os
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.database import Participant, SessionLocal, TradeEntry
from backend.models import TradeSubmit

RECONCILIATION_STATUS_FILE = os.getenv(
    "TRADER_LEAGUE_RECONCILIATION_STATUS_FILE",
    os.getenv("TRADE_RECONCILER_STATUS_FILE", "state/trade_reconciler_status.json"),
)

app = FastAPI(title="Trader League Live - Powered by LUMINA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/webhook/trade")
def submit_trade(trade: TradeSubmit) -> dict[str, int | str]:
    db = SessionLocal()
    try:
        participant = db.query(Participant).filter_by(name=trade.participant).first()
        if not participant:
            participant = Participant(
                name=trade.participant,
                mode=trade.mode,
                is_lumina=1 if "LUMINA" in trade.participant.upper() else 0,
            )
            db.add(participant)
            db.commit()
            db.refresh(participant)

        entry = TradeEntry(
            participant_id=participant.id,
            symbol=trade.symbol,
            signal=trade.signal,
            entry=trade.entry,
            exit=trade.exit,
            qty=trade.qty,
            pnl=trade.pnl,
            broker_fill_id=trade.broker_fill_id,
            commission=trade.commission,
            slippage_points=trade.slippage_points,
            fill_latency_ms=trade.fill_latency_ms,
            reconciliation_status=trade.reconciliation_status,
            reflection=trade.reflection,
            chart_base64=trade.chart_base64,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return {"status": "ok", "trade_id": entry.id}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Trade ingest failed: {exc}") from exc
    finally:
        db.close()


@app.post("/trades")
def submit_trade_alias(trade: TradeSubmit) -> dict[str, int | str]:
    # Compatibility endpoint used by dashboard/tests; same behavior as webhook.
    return submit_trade(trade)


@app.get("/trades")
def get_trades(
    limit: int = Query(default=100, ge=1, le=1000),
    participant: str | None = None,
) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        query = db.query(TradeEntry).order_by(TradeEntry.ts.desc()).limit(limit)
        rows = query.all()
        participant_map = {p.id: p for p in db.query(Participant).all()}

        output: list[dict[str, Any]] = []
        participant_filter = participant.strip().lower() if participant else None
        for row in rows:
            p = participant_map.get(row.participant_id)
            p_name = p.name if p else "unknown"
            if participant_filter and p_name.lower() != participant_filter:
                continue
            output.append(
                {
                    "id": row.id,
                    "participant": p_name,
                    "mode": p.mode if p else "unknown",
                    "ts": row.ts.isoformat() if row.ts else None,
                    "symbol": row.symbol,
                    "signal": row.signal,
                    "entry": row.entry,
                    "exit": row.exit,
                    "qty": row.qty,
                    "pnl": row.pnl,
                    "broker_fill_id": row.broker_fill_id,
                    "commission": row.commission,
                    "slippage_points": row.slippage_points,
                    "fill_latency_ms": row.fill_latency_ms,
                    "reconciliation_status": row.reconciliation_status,
                    "sharpe": row.sharpe,
                    "maxdd": row.maxdd,
                    "reflection": row.reflection,
                    "chart_base64": row.chart_base64,
                }
            )
        return output
    finally:
        db.close()


@app.get("/leaderboard")
def get_leaderboard() -> dict[str, list[dict[str, int | float | str]] | str]:
    db = SessionLocal()
    try:
        trades = db.query(TradeEntry).all()
        participants = {p.id: p for p in db.query(Participant).all()}

        grouped: dict[int, dict[str, int | float | str]] = {}
        for trade in trades:
            participant = participants.get(trade.participant_id)
            if participant is None:
                continue
            if trade.participant_id not in grouped:
                grouped[trade.participant_id] = {
                    "participant": participant.name,
                    "mode": participant.mode,
                    "is_lumina": participant.is_lumina,
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "total_pnl": 0.0,
                    "avg_pnl": 0.0,
                    "win_rate": 0.0,
                }

            row = grouped[trade.participant_id]
            row["trades"] = int(row["trades"]) + 1
            row["total_pnl"] = float(row["total_pnl"]) + float(trade.pnl or 0.0)
            if float(trade.pnl or 0.0) > 0:
                row["wins"] = int(row["wins"]) + 1
            elif float(trade.pnl or 0.0) < 0:
                row["losses"] = int(row["losses"]) + 1

        leaderboard: list[dict[str, int | float | str]] = []
        for row in grouped.values():
            trades_count = int(row["trades"])
            total_pnl = float(row["total_pnl"])
            wins = int(row["wins"])
            row["avg_pnl"] = round(total_pnl / trades_count, 4) if trades_count else 0.0
            row["win_rate"] = round((wins / trades_count) * 100, 2) if trades_count else 0.0
            row["total_pnl"] = round(total_pnl, 4)
            leaderboard.append(row)

        leaderboard.sort(key=lambda item: float(item["total_pnl"]), reverse=True)
        return {
            "leaderboard": leaderboard[:50],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        db.close()


@app.get("/reconciliation-status")
def get_reconciliation_status() -> dict[str, Any]:
    try:
        if not os.path.exists(RECONCILIATION_STATUS_FILE):
            return {
                "status": "unavailable",
                "connection_state": "offline",
                "pending_count": 0,
                "pending_symbols": [],
                "last_error": None,
                "last_message_ts": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        with open(RECONCILIATION_STATUS_FILE, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Invalid reconciliation status payload")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reconciliation status unavailable: {exc}") from exc


@app.delete("/trades")
def delete_all_trades() -> dict[str, int]:
    db = SessionLocal()
    try:
        deleted = db.query(TradeEntry).delete()
        db.commit()
        return {"deleted": deleted}
    finally:
        db.close()


@app.delete("/demo-data")
def delete_demo_data() -> dict[str, int]:
    db = SessionLocal()
    try:
        demo_participants = db.query(Participant).filter(Participant.name.like("DEMO_%")).all()
        demo_ids = [item.id for item in demo_participants]

        deleted_trades = 0
        if demo_ids:
            deleted_trades = (
                db.query(TradeEntry)
                .filter(TradeEntry.participant_id.in_(demo_ids))
                .delete(synchronize_session=False)
            )
        deleted_participants = (
            db.query(Participant)
            .filter(Participant.name.like("DEMO_%"))
            .delete(synchronize_session=False)
        )
        db.commit()
        return {
            "deleted_participants": deleted_participants,
            "deleted_trades": deleted_trades,
        }
    finally:
        db.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
