export interface RealOpsSnapshot {
  realizedPnl: number;
  maxDrawdownUsd: number;
  riskEvents: number;
  varBreachCount: number;
  winRate: number;
  sharpeAnnualized: number;
  sessionGuardBlocks: number;
  totalTrades: number;
  windowPnl: { h24: number; d7: number; d30: number };
  exposure: { livePositionQty: number; pendingReconciliations: number };
  capitalPreservation: {
    protocolGreen: boolean;
    gates: {
      riskEventsZero: boolean;
      varBreachesZero: boolean;
      drawdownUnder500: boolean;
      sharpeAtLeast1: boolean;
      pnl24hNonNegative: boolean;
    };
  };
}

function asNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

export function parseRealOpsSnapshot(raw: unknown): RealOpsSnapshot | null {
  if (typeof raw !== "object" || raw === null) return null;
  const record = raw as Record<string, unknown>;
  const windowRaw = record.window_pnl;
  const window = typeof windowRaw === "object" && windowRaw !== null ? (windowRaw as Record<string, unknown>) : {};
  const exposureRaw = record.exposure;
  const exposure =
    typeof exposureRaw === "object" && exposureRaw !== null ? (exposureRaw as Record<string, unknown>) : {};
  const capRaw = record.capital_preservation;
  const cap = typeof capRaw === "object" && capRaw !== null ? (capRaw as Record<string, unknown>) : {};
  const gatesRaw = cap.gates;
  const gates = typeof gatesRaw === "object" && gatesRaw !== null ? (gatesRaw as Record<string, unknown>) : {};

  return {
    realizedPnl: asNumber(record.realized_pnl),
    maxDrawdownUsd: asNumber(record.max_drawdown_usd),
    riskEvents: asNumber(record.risk_events),
    varBreachCount: asNumber(record.var_breach_count),
    winRate: asNumber(record.win_rate),
    sharpeAnnualized: asNumber(record.sharpe_annualized),
    sessionGuardBlocks: asNumber(record.session_guard_blocks),
    totalTrades: asNumber(record.total_trades),
    windowPnl: {
      h24: asNumber(window.h24),
      d7: asNumber(window.d7),
      d30: asNumber(window.d30),
    },
    exposure: {
      livePositionQty: asNumber(exposure.live_position_qty),
      pendingReconciliations: asNumber(exposure.pending_reconciliations),
    },
    capitalPreservation: {
      protocolGreen: Boolean(cap.protocol_green),
      gates: {
        riskEventsZero: Boolean(gates.risk_events_zero),
        varBreachesZero: Boolean(gates.var_breaches_zero),
        drawdownUnder500: Boolean(gates.drawdown_under_500),
        sharpeAtLeast1: Boolean(gates.sharpe_at_least_1),
        pnl24hNonNegative: Boolean(gates.pnl_24h_non_negative),
      },
    },
  };
}
