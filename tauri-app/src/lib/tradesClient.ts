import { resolveBackendBaseUrl } from "@/lib/setupClient";
import { resolveMonitoringApiKey } from "@/lib/monitoringClient";
import type { TradeRecord } from "@/lib/liveTradingTypes";

function asNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

export async function fetchRecentTrades(limit = 20): Promise<TradeRecord[]> {
  const apiKey = resolveMonitoringApiKey();
  if (!apiKey) return [];

  const base = resolveBackendBaseUrl();
  const response = await fetch(`${base}/trades?limit=${limit}`, {
    headers: {
      Accept: "application/json",
      "X-API-Key": apiKey,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Trades HTTP ${response.status}`);
  }
  const rows = (await response.json()) as unknown[];
  if (!Array.isArray(rows)) return [];

  return rows.map((row) => {
    const record = row as Record<string, unknown>;
    return {
      ts: typeof record.ts === "string" ? record.ts : null,
      signal: String(record.signal ?? ""),
      entry: asNumber(record.entry),
      exit: asNumber(record.exit),
      qty: Math.trunc(asNumber(record.qty)),
      pnl: asNumber(record.pnl),
      confluence: 0,
      symbol: typeof record.symbol === "string" ? record.symbol : null,
      slippage_points:
        record.slippage_points == null ? null : asNumber(record.slippage_points),
      fill_latency_ms:
        record.fill_latency_ms == null ? null : asNumber(record.fill_latency_ms),
    };
  });
}
