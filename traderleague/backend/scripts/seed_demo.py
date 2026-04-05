from datetime import datetime, timedelta
import hashlib

from sqlalchemy import create_engine, text

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)

    now = datetime.utcnow()
    participants = [
        ("lumina_public", "LUMINA Public", "lumina_public_demo_key", True),
        ("alpha_monk", "Alpha Monk", "alpha_demo_key", False),
        ("quant_fox", "Quant Fox", "quant_demo_key", False),
    ]

    with engine.begin() as conn:
        for handle, display_name, api_key_plain, is_public in participants:
            api_key_hash = hashlib.sha256(api_key_plain.encode("utf-8")).hexdigest()
            conn.execute(
                text(
                    """
                    INSERT INTO participants(handle, display_name, api_key_hash, is_lumina_public)
                    VALUES (:handle, :display_name, :api_key_hash, :is_public)
                    ON CONFLICT (handle) DO NOTHING
                    """
                ),
                {
                    "handle": handle,
                    "display_name": display_name,
                    "api_key_hash": api_key_hash,
                    "is_public": is_public,
                },
            )

        broker_row = conn.execute(text("SELECT id FROM brokers WHERE name='NinjaTrader' LIMIT 1")).fetchone()
        if broker_row is None:
            raise RuntimeError("NinjaTrader broker not found. Run init_db first.")
        broker_id = broker_row[0]

        participant_rows = conn.execute(text("SELECT id, handle FROM participants")).fetchall()
        for pid, handle in participant_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO participant_accounts(participant_id, broker_id, broker_account_ref, mode)
                    VALUES (:participant_id, :broker_id, :broker_account_ref, :mode)
                    ON CONFLICT (participant_id, broker_id, broker_account_ref) DO NOTHING
                    """
                ),
                {
                    "participant_id": pid,
                    "broker_id": broker_id,
                    "broker_account_ref": f"SIM-{handle}",
                    "mode": "paper",
                },
            )

        accounts = conn.execute(
            text(
                """
                SELECT pa.id, pa.participant_id, p.handle
                FROM participant_accounts pa
                JOIN participants p ON p.id = pa.participant_id
                """
            )
        ).fetchall()

        for account_id, participant_id, handle in accounts:
            for i in range(1, 9):
                entry_time = now - timedelta(days=i, minutes=20)
                exit_time = now - timedelta(days=i, minutes=5)
                pnl = (1 if i % 3 != 0 else -1) * (30 + i * 6)
                conn.execute(
                    text(
                        """
                        INSERT INTO trades(
                            participant_id, account_id, symbol, entry_time, exit_time,
                            entry_price, exit_price, quantity, pnl, max_drawdown_trade,
                            broker_fill_id, reflection, chart_snapshot_url, strategy_meta
                        )
                        VALUES (
                            :participant_id, :account_id, :symbol, :entry_time, :exit_time,
                            :entry_price, :exit_price, :quantity, :pnl, :maxdd,
                            :broker_fill_id, :reflection, :chart_snapshot_url, :strategy_meta::jsonb
                        )
                        ON CONFLICT (broker_fill_id) DO NOTHING
                        """
                    ),
                    {
                        "participant_id": participant_id,
                        "account_id": account_id,
                        "symbol": "MES",
                        "entry_time": entry_time,
                        "exit_time": exit_time,
                        "entry_price": 5200.0 + i,
                        "exit_price": 5201.0 + i,
                        "quantity": 1,
                        "pnl": float(pnl),
                        "maxdd": float(-abs(pnl) * 0.35),
                        "broker_fill_id": f"DEMO-{handle}-{i}",
                        "reflection": f"Demo reflection {i} for {handle}",
                        "chart_snapshot_url": "",
                        "strategy_meta": '{"seed": true, "engine": "Lumina"}',
                    },
                )

    print("Demo data seeded")


if __name__ == "__main__":
    main()
