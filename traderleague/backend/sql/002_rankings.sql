CREATE OR REPLACE FUNCTION rank_period(start_date DATE, end_date DATE)
RETURNS TABLE (
    rank BIGINT,
    participant_id INT,
    handle VARCHAR,
    score DOUBLE PRECISION,
    pnl_total DOUBLE PRECISION,
    sharpe DOUBLE PRECISION,
    winrate DOUBLE PRECISION
)
LANGUAGE SQL
AS $$
WITH scoped AS (
    SELECT
        p.id AS participant_id,
        p.handle,
        COALESCE(SUM(t.pnl), 0) AS pnl_total,
        COALESCE(stddev_samp(t.pnl), 0) AS pnl_std,
        COALESCE(AVG(CASE WHEN t.pnl > 0 THEN 1.0 ELSE 0.0 END), 0) AS winrate
    FROM participants p
    LEFT JOIN trades t
           ON t.participant_id = p.id
          AND t.exit_time::DATE BETWEEN start_date AND end_date
    GROUP BY p.id, p.handle
)
SELECT
    ROW_NUMBER() OVER (ORDER BY (pnl_total + winrate * 100.0) DESC) AS rank,
    participant_id,
    handle,
    (pnl_total + winrate * 100.0) AS score,
    pnl_total,
    CASE WHEN pnl_std > 0 THEN pnl_total / pnl_std ELSE 0 END AS sharpe,
    winrate
FROM scoped
ORDER BY rank;
$$;
