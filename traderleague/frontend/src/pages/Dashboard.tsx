import { useEffect, useMemo, useState } from "react";

import { fetchLiveMetrics, fetchRankings, fetchReplay } from "../api/client";
import { MetricCards } from "../components/MetricCards";
import { RankingTable } from "../components/RankingTable";
import { ReplayPanel } from "../components/ReplayPanel";
import type { Bucket, ParticipantMetrics, RankingRow, TradeReplay } from "../types";

export function Dashboard() {
  const [bucket, setBucket] = useState<Bucket>("daily");
  const [metrics, setMetrics] = useState<ParticipantMetrics[]>([]);
  const [rankings, setRankings] = useState<RankingRow[]>([]);
  const [tradeId, setTradeId] = useState<string>("");
  const [replay, setReplay] = useState<TradeReplay | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    void fetchLiveMetrics().then(setMetrics).catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    void fetchRankings(bucket).then(setRankings).catch((e: Error) => setError(e.message));
  }, [bucket]);

  const top = useMemo(() => rankings.slice(0, 10), [rankings]);

  async function onLoadReplay() {
    if (!tradeId.trim()) return;
    try {
      setReplay(await fetchReplay(Number(tradeId)));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <main className="layout">
      <header>
        <h1>TraderLeague</h1>
        <p>Live leaderboard for verified brokers and Lumina participants.</p>
      </header>

      {error && <p className="error">{error}</p>}

      <MetricCards data={metrics} />

      <section className="panel">
        <h2>Rankings</h2>
        <div className="bucket-controls">
          {(["daily", "weekly", "monthly"] as Bucket[]).map((b) => (
            <button key={b} className={bucket === b ? "active" : ""} onClick={() => setBucket(b)}>
              {b}
            </button>
          ))}
        </div>
        <RankingTable rows={top} />
      </section>

      <section className="panel">
        <h2>Trade Replay</h2>
        <div className="replay-controls">
          <input value={tradeId} onChange={(e) => setTradeId(e.target.value)} placeholder="Enter trade ID" />
          <button onClick={onLoadReplay}>Load Replay</button>
        </div>
        <ReplayPanel replay={replay} />
      </section>
    </main>
  );
}
