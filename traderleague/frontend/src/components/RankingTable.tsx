import type { RankingRow } from "../types";

type Props = { rows: RankingRow[] };

export function RankingTable({ rows }: Props) {
  return (
    <table className="ranking-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Handle</th>
          <th>Score</th>
          <th>PnL</th>
          <th>Sharpe</th>
          <th>Winrate</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.participant_id}>
            <td>{r.rank}</td>
            <td>{r.handle}</td>
            <td>{r.score.toFixed(2)}</td>
            <td>{r.pnl_total.toFixed(2)}</td>
            <td>{r.sharpe.toFixed(2)}</td>
            <td>{(r.winrate * 100).toFixed(1)}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
