import type { Bucket, ParticipantMetrics, RankingRow, TradeReplay } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export function fetchLiveMetrics(): Promise<ParticipantMetrics[]> {
  return getJson<ParticipantMetrics[]>("/rankings/live");
}

export function fetchRankings(bucket: Bucket): Promise<RankingRow[]> {
  return getJson<RankingRow[]>(`/rankings?bucket=${bucket}`);
}

export function fetchReplay(tradeId: number): Promise<TradeReplay> {
  return getJson<TradeReplay>(`/replay/trade/${tradeId}`);
}
