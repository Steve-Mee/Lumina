from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import AccountMode, Broker, Participant, ParticipantAccount, Trade
from app.schemas.traderleague import TradeCloseWebhookIn


def ensure_verified_account(db: Session, payload: TradeCloseWebhookIn) -> tuple[Participant, ParticipantAccount]:
    broker = db.execute(select(Broker).where(Broker.name == payload.broker_name)).scalar_one_or_none()
    if broker is None or not broker.verified:
        raise ValueError("Unverified broker")

    participant = db.execute(select(Participant).where(Participant.handle == payload.participant_handle)).scalar_one_or_none()
    if participant is None:
        raise ValueError("Participant not registered")

    account = db.execute(
        select(ParticipantAccount).where(
            ParticipantAccount.participant_id == participant.id,
            ParticipantAccount.broker_id == broker.id,
            ParticipantAccount.broker_account_ref == payload.broker_account_ref,
        )
    ).scalar_one_or_none()

    if account is None:
        account = ParticipantAccount(
            participant_id=participant.id,
            broker_id=broker.id,
            broker_account_ref=payload.broker_account_ref,
            mode=AccountMode(payload.account_mode),
        )
        db.add(account)
        db.flush()

    return participant, account


def upsert_trade_close(db: Session, payload: TradeCloseWebhookIn, participant_id: int, account_id: int) -> Trade:
    existing = db.execute(select(Trade).where(Trade.broker_fill_id == payload.broker_fill_id)).scalar_one_or_none()
    if existing:
        return existing

    trade = Trade(
        participant_id=participant_id,
        account_id=account_id,
        symbol=payload.symbol,
        entry_time=payload.entry_time,
        exit_time=payload.exit_time,
        entry_price=payload.entry_price,
        exit_price=payload.exit_price,
        quantity=payload.quantity,
        pnl=payload.pnl,
        max_drawdown_trade=payload.max_drawdown_trade,
        broker_fill_id=payload.broker_fill_id,
        reflection=payload.reflection,
        chart_snapshot_url=payload.chart_snapshot_url,
        strategy_meta=payload.strategy_meta,
    )
    db.add(trade)
    db.flush()
    return trade
