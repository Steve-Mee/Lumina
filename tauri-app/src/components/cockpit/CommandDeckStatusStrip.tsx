import { useMemo } from "react";

import { StatusChip } from "@/components/birth/BirthGenesisDeckPrimitives";
import type { BarBookTelemetry } from "@/lib/websocket";
import {
  aggregateIntegrity,
  deriveCitadelWallsFromInputs,
  integrityTier,
} from "@/lib/riskCitadelMetrics";
import {
  selectBarBook,
  selectConnectionStatus,
  selectCurrentMode,
  selectFortress,
  selectLiveMetrics,
  selectNinjaTraderStatus,
  selectRiskLevel,
  useCoreStore,
} from "@/store/coreStore";

export type BarBookChip = {
  label: string;
  state: "ok" | "partial" | "warn" | "idle";
  tip: string;
};

export function barBookChip(barBook: BarBookTelemetry | null): BarBookChip {
  if (barBook == null) {
    return { label: "BARS", state: "idle", tip: "Barboek nog niet gemeten." };
  }
  if (barBook.lock_new_entries) {
    const extra = (barBook.message || barBook.reason || "").trim();
    return {
      label: "BARS LOCK",
      state: "warn",
      tip: extra ? `Nieuwe entries dicht. ${extra}` : "Nieuwe entries dicht.",
    };
  }
  if (barBook.complete) {
    return {
      label: "BARS OK",
      state: "ok",
      tip: "NT 1m-barboek is volledig. Nieuwe entries open.",
    };
  }
  const extra = (barBook.message || barBook.reason || "").trim();
  return {
    label: "BARS",
    state: "partial",
    tip: extra || "Barboek onvolledig, entries nog open.",
  };
}

function formatEquity(equity: number | null): string {
  if (equity === null || !Number.isFinite(equity)) return "—";
  return equity.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function CommandDeckStatusStrip() {
  const mode = useCoreStore(selectCurrentMode);
  const connection = useCoreStore(selectConnectionStatus);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const riskLevel = useCoreStore(selectRiskLevel);
  const fortress = useCoreStore(selectFortress);
  const nt = useCoreStore(selectNinjaTraderStatus);
  const barBook = useCoreStore(selectBarBook);
  const bars = barBookChip(barBook);

  const walls = useMemo(
    () => deriveCitadelWallsFromInputs({ liveMetrics, riskLevel, fortress }),
    [liveMetrics, riskLevel, fortress],
  );
  const integrity = aggregateIntegrity(walls);
  const integrityState = integrityTier(integrity);
  const ntConnected = Boolean(nt?.connected && nt.state === "connected");
  const ntDegraded = nt?.state === "degraded";

  return (
    <div
      className="command-deck-ops__status birth-mission-status-strip risk-envelope-status-strip shrink-0"
      role="status"
      aria-label="Command deck status"
    >
      <StatusChip
        label={mode}
        state={mode === "REAL" ? "warn" : "ok"}
        tip={mode === "REAL" ? "Live capital path. Fail-closed." : "SIM capital. Fictional money, real order path."}
      />
      <StatusChip
        label={connection === "connected" ? "LINK" : connection.toUpperCase()}
        state={connection === "connected" ? "ok" : connection === "connecting" ? "partial" : "warn"}
        tip="Core live websocket."
      />
      <StatusChip
        label={ntConnected ? "NT8" : ntDegraded ? "NT8 DEG" : "NT8 OFF"}
        state={ntConnected ? "ok" : ntDegraded ? "warn" : "idle"}
        tip="NinjaTrader / Fabric link."
      />
      <StatusChip label={bars.label} state={bars.state} tip={bars.tip} />
      <StatusChip
        label={`EQ ${formatEquity(liveMetrics.equity)}`}
        state={liveMetrics.equity == null ? "idle" : "partial"}
        tip="Net liquidation of the NinjaTrader account. A stale file is not this number."
      />
      <StatusChip
        label={`INT ${Math.round(integrity)}`}
        state={integrityState === "green" ? "ok" : integrityState === "orange" ? "warn" : "warn"}
        tip="Weakest risk wall. Not a win-rate stamp."
      />
    </div>
  );
}
