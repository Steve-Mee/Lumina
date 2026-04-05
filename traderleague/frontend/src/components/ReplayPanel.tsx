import type { TradeReplay } from "../types";

type Props = { replay: TradeReplay | null };

export function ReplayPanel({ replay }: Props) {
  if (!replay) {
    return <div className="panel">Select a trade ID to replay.</div>;
  }

  return (
    <section className="panel">
      <h3>Trade Replay #{replay.trade_id}</h3>
      <p>
        {replay.symbol} | Qty {replay.quantity} | PnL {replay.pnl.toFixed(2)}
      </p>
      <p>
        Entry {new Date(replay.entry_time).toLocaleString()} @ {replay.entry_price} | Exit {new Date(replay.exit_time).toLocaleString()} @ {replay.exit_price}
      </p>
      <p><strong>Reflection:</strong> {replay.reflection || "No reflection provided"}</p>
      {replay.chart_snapshot_url ? (
        <img src={replay.chart_snapshot_url} alt="Trade chart snapshot" className="chart" />
      ) : (
        <div className="chart-placeholder">No chart snapshot URL</div>
      )}
    </section>
  );
}
