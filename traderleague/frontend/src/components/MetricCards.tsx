import type { ParticipantMetrics } from "../types";

type Props = { data: ParticipantMetrics[] };

export function MetricCards({ data }: Props) {
  const totals = data.reduce(
    (acc, row) => {
      acc.pnl += row.pnl_total;
      acc.sharpe += row.sharpe;
      acc.maxdd = Math.min(acc.maxdd, row.max_drawdown);
      acc.winrate += row.winrate;
      return acc;
    },
    { pnl: 0, sharpe: 0, maxdd: 0, winrate: 0 },
  );

  const n = data.length || 1;
  const cards = [
    { label: "Live PnL", value: totals.pnl.toFixed(2) },
    { label: "Avg Sharpe", value: (totals.sharpe / n).toFixed(2) },
    { label: "Worst MaxDD", value: totals.maxdd.toFixed(2) },
    { label: "Avg Winrate", value: `${((totals.winrate / n) * 100).toFixed(1)}%` },
  ];

  return (
    <section className="cards">
      {cards.map((c) => (
        <article key={c.label} className="card">
          <h3>{c.label}</h3>
          <p>{c.value}</p>
        </article>
      ))}
    </section>
  );
}
