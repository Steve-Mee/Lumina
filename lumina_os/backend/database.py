from datetime import datetime, timezone
import os
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "LUMINA_OS_DATABASE_URL",
    os.getenv("TRADER_LEAGUE_DATABASE_URL", "sqlite:///lumina_os.db"),
)

engine_kwargs: dict = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine)
Base: Any = declarative_base()


class Participant(Base):
    __tablename__ = "participants"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    mode = Column(String)  # "paper" / "real"
    is_lumina = Column(Integer, default=0)  # 1 = jouw bot


class TradeEntry(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    symbol = Column(String)
    signal = Column(String)
    entry = Column(Float)
    exit = Column(Float)
    qty = Column(Float)
    pnl = Column(Float)
    broker_fill_id = Column(String)
    commission = Column(Float)
    slippage_points = Column(Float)
    fill_latency_ms = Column(Float)
    reconciliation_status = Column(String)
    sharpe = Column(Float)
    maxdd = Column(Float)
    reflection = Column(JSON)
    chart_base64 = Column(String)  # voor replay


class CommunityBible(Base):
    __tablename__ = "community_bibles"
    id = Column(Integer, primary_key=True)
    trader_name = Column(String, unique=True)
    bible_hash = Column(String)
    upload_ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    performance_score = Column(Float, default=0.0)
    reflection_count = Column(Integer, default=0)
    evolvable_layer = Column(JSON)


class CommunityReflection(Base):
    __tablename__ = "community_reflections"
    id = Column(Integer, primary_key=True)
    bible_id = Column(Integer)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    reflection = Column(Text)
    key_lesson = Column(String)
    suggested_update = Column(JSON)
    pnl_impact = Column(Float)


Base.metadata.create_all(engine)


def _ensure_trade_columns() -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("trades")}
    statements: list[str] = []
    if "broker_fill_id" not in columns:
        statements.append("ALTER TABLE trades ADD COLUMN broker_fill_id VARCHAR")
    if "commission" not in columns:
        statements.append("ALTER TABLE trades ADD COLUMN commission FLOAT")
    if "slippage_points" not in columns:
        statements.append("ALTER TABLE trades ADD COLUMN slippage_points FLOAT")
    if "fill_latency_ms" not in columns:
        statements.append("ALTER TABLE trades ADD COLUMN fill_latency_ms FLOAT")
    if "reconciliation_status" not in columns:
        statements.append("ALTER TABLE trades ADD COLUMN reconciliation_status VARCHAR")
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


_ensure_trade_columns()
