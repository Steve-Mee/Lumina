CREATE TYPE account_mode AS ENUM ('paper', 'real');
CREATE TYPE time_bucket AS ENUM ('daily', 'weekly', 'monthly');

CREATE TABLE IF NOT EXISTS brokers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS participants (
    id SERIAL PRIMARY KEY,
    handle VARCHAR(80) UNIQUE NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    api_key_hash VARCHAR(128) NOT NULL,
    is_lumina_public BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS participant_accounts (
    id SERIAL PRIMARY KEY,
    participant_id INT NOT NULL REFERENCES participants(id),
    broker_id INT NOT NULL REFERENCES brokers(id),
    broker_account_ref VARCHAR(140) NOT NULL,
    mode account_mode NOT NULL,
    UNIQUE(participant_id, broker_id, broker_account_ref)
);

CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL PRIMARY KEY,
    participant_id INT NOT NULL REFERENCES participants(id),
    account_id INT NOT NULL REFERENCES participant_accounts(id),
    symbol VARCHAR(50) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    exit_price DOUBLE PRECISION NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    pnl DOUBLE PRECISION NOT NULL,
    max_drawdown_trade DOUBLE PRECISION NOT NULL DEFAULT 0,
    broker_fill_id VARCHAR(180) NOT NULL UNIQUE,
    reflection TEXT NOT NULL DEFAULT '',
    chart_snapshot_url VARCHAR(500),
    strategy_meta JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_participant_exit ON trades(participant_id, exit_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_exit ON trades(symbol, exit_time DESC);

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id BIGSERIAL PRIMARY KEY,
    participant_id INT NOT NULL REFERENCES participants(id),
    as_of_date DATE NOT NULL,
    pnl_total DOUBLE PRECISION NOT NULL DEFAULT 0,
    sharpe DOUBLE PRECISION NOT NULL DEFAULT 0,
    max_drawdown DOUBLE PRECISION NOT NULL DEFAULT 0,
    winrate DOUBLE PRECISION NOT NULL DEFAULT 0,
    UNIQUE(participant_id, as_of_date)
);

CREATE TABLE IF NOT EXISTS ranking_snapshots (
    id BIGSERIAL PRIMARY KEY,
    bucket time_bucket NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    participant_id INT NOT NULL REFERENCES participants(id),
    rank INT NOT NULL,
    score DOUBLE PRECISION NOT NULL
);

CREATE OR REPLACE VIEW v_live_metrics AS
SELECT
    p.id AS participant_id,
    p.handle,
    COALESCE(SUM(t.pnl), 0) AS pnl_total,
    CASE WHEN COALESCE(stddev_samp(t.pnl), 0) > 0
         THEN COALESCE(SUM(t.pnl), 0) / stddev_samp(t.pnl)
         ELSE 0 END AS sharpe,
    COALESCE(MIN(t.pnl), 0) AS max_drawdown,
    COALESCE(AVG(CASE WHEN t.pnl > 0 THEN 1.0 ELSE 0.0 END), 0) AS winrate
FROM participants p
LEFT JOIN trades t ON t.participant_id = p.id
GROUP BY p.id, p.handle;

INSERT INTO brokers (name, verified)
VALUES
  ('NinjaTrader', TRUE),
  ('Interactive Brokers', TRUE),
  ('Tradovate', TRUE)
ON CONFLICT (name) DO NOTHING;
