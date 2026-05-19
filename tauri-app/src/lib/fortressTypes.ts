export interface FortressSnapshot {
  drawdown_pct: number | null;
  drawdown_kill_pct: number;
  kill_switch_active: boolean;
  mc_drawdown_pct: number | null;
  pending_reconciliations: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function coerceFloat(value: unknown): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return null;
}

function coerceInt(value: unknown, defaultValue = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  return defaultValue;
}

export function parseFortressSnapshot(value: unknown): FortressSnapshot | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (!isRecord(value)) {
    return null;
  }

  const drawdownKill = coerceFloat(value.drawdown_kill_pct) ?? 8;

  return {
    drawdown_pct: coerceFloat(value.drawdown_pct),
    drawdown_kill_pct: drawdownKill,
    kill_switch_active: value.kill_switch_active === true,
    mc_drawdown_pct: coerceFloat(value.mc_drawdown_pct),
    pending_reconciliations: coerceInt(value.pending_reconciliations),
  };
}
