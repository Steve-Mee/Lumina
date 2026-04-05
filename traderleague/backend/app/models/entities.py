from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AccountMode(str, Enum):
    PAPER = "paper"
    REAL = "real"


class TimeBucket(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Broker(Base):
    __tablename__ = "brokers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_lumina_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ParticipantAccount(Base):
    __tablename__ = "participant_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), nullable=False)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"), nullable=False)
    broker_account_ref: Mapped[str] = mapped_column(String(140), nullable=False)
    mode: Mapped[AccountMode] = mapped_column(SqlEnum(AccountMode), nullable=False)

    participant = relationship("Participant")
    broker = relationship("Broker")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("participant_accounts.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown_trade: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    broker_fill_id: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    reflection: Mapped[str] = mapped_column(Text, default="", nullable=False)
    chart_snapshot_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    strategy_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    pnl_total: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sharpe: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    winrate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bucket: Mapped[TimeBucket] = mapped_column(SqlEnum(TimeBucket), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
