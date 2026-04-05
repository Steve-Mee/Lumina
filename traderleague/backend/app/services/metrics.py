from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entities import TimeBucket


def _bucket_window(bucket: TimeBucket) -> tuple[date, date]:
    today = date.today()
    if bucket == TimeBucket.DAILY:
        return today, today
    if bucket == TimeBucket.WEEKLY:
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1) - timedelta(days=1)
    return start, end


def fetch_live_metrics(db: Session) -> list[dict]:
    sql = text(
        """
        SELECT p.id AS participant_id,
               p.handle,
               COALESCE(SUM(t.pnl), 0) AS pnl_total,
               COALESCE(stddev_samp(t.pnl), 0) AS pnl_std,
               COALESCE(AVG(CASE WHEN t.pnl > 0 THEN 1.0 ELSE 0.0 END), 0) AS winrate,
               COALESCE(MIN(t.pnl), 0) AS max_drawdown
        FROM participants p
        LEFT JOIN trades t ON t.participant_id = p.id
        GROUP BY p.id, p.handle
        ORDER BY pnl_total DESC
        """
    )
    rows = db.execute(sql).mappings().all()
    out = []
    for row in rows:
        pnl_std = float(row["pnl_std"] or 0.0)
        sharpe = float(row["pnl_total"]) / pnl_std if pnl_std > 0 else 0.0
        out.append(
            {
                "participant_id": row["participant_id"],
                "handle": row["handle"],
                "pnl_total": float(row["pnl_total"]),
                "sharpe": sharpe,
                "max_drawdown": float(row["max_drawdown"]),
                "winrate": float(row["winrate"]),
            }
        )
    return out


def fetch_rankings(db: Session, bucket: TimeBucket) -> list[dict]:
    start, end = _bucket_window(bucket)
    sql = text(
        """
        WITH scoped AS (
            SELECT p.id AS participant_id,
                   p.handle,
                   COALESCE(SUM(t.pnl), 0) AS pnl_total,
                   COALESCE(stddev_samp(t.pnl), 0) AS pnl_std,
                   COALESCE(AVG(CASE WHEN t.pnl > 0 THEN 1.0 ELSE 0.0 END), 0) AS winrate
            FROM participants p
            LEFT JOIN trades t ON t.participant_id = p.id
                              AND t.exit_time::date BETWEEN :start_date AND :end_date
            GROUP BY p.id, p.handle
        )
        SELECT ROW_NUMBER() OVER (ORDER BY (pnl_total + winrate * 100.0) DESC) AS rank,
               participant_id,
               handle,
               (pnl_total + winrate * 100.0) AS score,
               pnl_total,
               CASE WHEN pnl_std > 0 THEN pnl_total / pnl_std ELSE 0 END AS sharpe,
               winrate
        FROM scoped
        ORDER BY rank ASC
        """
    )
    rows = db.execute(sql, {"start_date": start, "end_date": end}).mappings().all()
    return [dict(row) for row in rows]


def fetch_trade_replay(db: Session, trade_id: int) -> dict | None:
    sql = text(
        """
        SELECT id AS trade_id,
               participant_id,
               symbol,
               entry_time,
               exit_time,
               entry_price,
               exit_price,
               quantity,
               pnl,
               reflection,
               chart_snapshot_url
        FROM trades
        WHERE id = :trade_id
        """
    )
    row = db.execute(sql, {"trade_id": trade_id}).mappings().first()
    return dict(row) if row else None
