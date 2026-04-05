from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from typing import cast

from backend.database import Participant, SessionLocal, TradeEntry


def clear_demo_data() -> tuple[int, int]:
    db = SessionLocal()
    try:
        demo_participants = db.query(Participant).filter(Participant.name.like("DEMO_%")).all()
        demo_ids = [p.id for p in demo_participants]

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
        return deleted_participants, deleted_trades
    finally:
        db.close()


def ensure_participant(name: str, mode: str, is_lumina: int = 0) -> int:
    db = SessionLocal()
    try:
        participant = db.query(Participant).filter(Participant.name == name).first()
        if participant is None:
            participant = Participant(name=name, mode=mode, is_lumina=is_lumina)
            db.add(participant)
            db.commit()
            db.refresh(participant)
        return cast(int, participant.id)
    finally:
        db.close()


def seed_demo_data() -> int:
    lumina_id = ensure_participant("DEMO_LUMINA", "paper", is_lumina=1)
    alpha_id = ensure_participant("DEMO_ALPHA", "paper")
    beta_id = ensure_participant("DEMO_BETA", "real")

    now = datetime.utcnow()
    demo_trades = [
        {
            "participant_id": lumina_id,
            "symbol": "NQ",
            "signal": "long",
            "entry": 18250.0,
            "exit": 18263.0,
            "qty": 1,
            "pnl": 260.0,
            "sharpe": 1.45,
            "maxdd": 50.0,
            "reflection": {"note": "Breakout continuation"},
            "chart_base64": None,
        },
        {
            "participant_id": alpha_id,
            "symbol": "ES",
            "signal": "short",
            "entry": 5320.0,
            "exit": 5312.5,
            "qty": 2,
            "pnl": 375.0,
            "sharpe": 1.7,
            "maxdd": 35.0,
            "reflection": {"note": "Mean reversion fade"},
            "chart_base64": None,
        },
        {
            "participant_id": beta_id,
            "symbol": "CL",
            "signal": "long",
            "entry": 81.2,
            "exit": 80.9,
            "qty": 3,
            "pnl": -90.0,
            "sharpe": 0.6,
            "maxdd": 110.0,
            "reflection": {"note": "Late entry, weak momentum"},
            "chart_base64": None,
        },
        {
            "participant_id": lumina_id,
            "symbol": "NQ",
            "signal": "short",
            "entry": 18290.0,
            "exit": 18270.0,
            "qty": 1,
            "pnl": 400.0,
            "sharpe": 1.9,
            "maxdd": 55.0,
            "reflection": {"note": "Reversal at resistance"},
            "chart_base64": None,
        },
    ]

    db = SessionLocal()
    try:
        for i, payload in enumerate(demo_trades):
            trade = TradeEntry(
                participant_id=payload["participant_id"],
                ts=now - timedelta(minutes=(len(demo_trades) - i) * 5),
                symbol=payload["symbol"],
                signal=payload["signal"],
                entry=payload["entry"],
                exit=payload["exit"],
                qty=payload["qty"],
                pnl=payload["pnl"],
                sharpe=payload["sharpe"],
                maxdd=payload["maxdd"],
                reflection=payload["reflection"],
                chart_base64=payload["chart_base64"],
            )
            db.add(trade)
        db.commit()
        return len(demo_trades)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed or clear Trader League demo data")
    parser.add_argument("--clear", action="store_true", help="Delete all DEMO_* participants and trades")
    args = parser.parse_args()

    if args.clear:
        deleted_participants, deleted_trades = clear_demo_data()
        print(
            f"Demo data verwijderd: participants={deleted_participants}, trades={deleted_trades}"
        )
        return

    deleted_participants, deleted_trades = clear_demo_data()
    inserted = seed_demo_data()
    print(
        "Demo data seeded. "
        f"Oude demo verwijderd: participants={deleted_participants}, trades={deleted_trades}. "
        f"Nieuwe trades={inserted}."
    )


if __name__ == "__main__":
    main()
