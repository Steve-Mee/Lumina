export type Bucket = "daily" | "weekly" | "monthly";

export interface ParticipantMetrics {
  participant_id: number;
  handle: string;
  pnl_total: number;
  sharpe: number;
  max_drawdown: number;
  winrate: number;
}

export interface RankingRow {
  rank: number;
  participant_id: number;
  handle: string;
  score: number;
  pnl_total: number;
  sharpe: number;
  winrate: number;
}

export interface TradeReplay {
  trade_id: number;
  participant_id: number;
  symbol: string;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  reflection: string;
  chart_snapshot_url?: string | null;
}
