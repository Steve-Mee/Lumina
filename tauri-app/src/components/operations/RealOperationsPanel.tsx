import { Shield } from "lucide-react";

import { AnimatedMetric } from "@/components/cockpit/AnimatedMetric";
import { distressPanelClass, realOverlayIconClass, realOverlayTitleClass, utilityMetricTileClass } from "@/lib/modePresentation";
import { formatUsd, pnlToneClass } from "@/lib/tradingPerformanceModel";
import { selectRealOpsLive, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

function GateTile({ label, pass }: { label: string; pass: boolean }) {
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2 text-center font-mono text-[10px] tracking-wide uppercase",
        pass
          ? "border-emerald-500/30 bg-emerald-950/25 text-emerald-300"
          : "border-red-500/30 bg-red-950/25 text-red-300",
      )}
    >
      <p className="text-[9px] text-muted-foreground">{label}</p>
      <p className="mt-1">{pass ? "PASS" : "FAIL"}</p>
    </div>
  );
}

export function RealOperationsPanel({ className }: { className?: string }) {
  const realOps = useCoreStore(selectRealOpsLive);

  if (!realOps) {
    return (
      <p className={cn("text-xs text-muted-foreground", className)}>
        REAL operations data unavailable — start a REAL session or check backend state files.
      </p>
    );
  }

  const gates = realOps.capitalPreservation.gates;

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex items-center gap-2">
        <Shield className={cn("size-4", realOverlayIconClass())} />
        <h3 className={cn("font-mono text-[11px] tracking-[0.14em] uppercase", realOverlayTitleClass())}>
          REAL Operations
        </h3>
        <span
          className={cn(
            "ml-auto rounded px-2 py-0.5 font-mono text-[9px] uppercase",
            realOps.capitalPreservation.protocolGreen
              ? "bg-emerald-950/40 text-emerald-300"
              : distressPanelClass("warn"),
          )}
        >
          {realOps.capitalPreservation.protocolGreen ? "Protocol GREEN" : "Protocol AMBER"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <div className="lumina-surface-muted rounded-md px-3 py-2">
          <p className="font-mono text-[9px] text-muted-foreground uppercase">Realized P&L</p>
          <AnimatedMetric value={formatUsd(realOps.realizedPnl)} className={pnlToneClass(realOps.realizedPnl)} />
        </div>
        <div className="lumina-surface-muted rounded-md px-3 py-2">
          <p className="font-mono text-[9px] text-muted-foreground uppercase">Max DD</p>
          <AnimatedMetric value={formatUsd(-realOps.maxDrawdownUsd, { signed: false })} />
        </div>
        <div className="lumina-surface-muted rounded-md px-3 py-2">
          <p className="font-mono text-[9px] text-muted-foreground uppercase">Risk Events</p>
          <AnimatedMetric value={String(realOps.riskEvents)} />
        </div>
        <div className="lumina-surface-muted rounded-md px-3 py-2">
          <p className="font-mono text-[9px] text-muted-foreground uppercase">VaR Breaches</p>
          <AnimatedMetric value={String(realOps.varBreachCount)} />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="lumina-surface-muted rounded-md px-3 py-2">
          <p className="text-[9px] text-muted-foreground uppercase">24h P&L</p>
          <AnimatedMetric value={formatUsd(realOps.windowPnl.h24)} className={pnlToneClass(realOps.windowPnl.h24)} />
        </div>
        <div className="lumina-surface-muted rounded-md px-3 py-2">
          <p className="text-[9px] text-muted-foreground uppercase">7d P&L</p>
          <AnimatedMetric value={formatUsd(realOps.windowPnl.d7)} className={pnlToneClass(realOps.windowPnl.d7)} />
        </div>
        <div className="lumina-surface-muted rounded-md px-3 py-2">
          <p className="text-[9px] text-muted-foreground uppercase">30d P&L</p>
          <AnimatedMetric value={formatUsd(realOps.windowPnl.d30)} className={pnlToneClass(realOps.windowPnl.d30)} />
        </div>
      </div>

      <section className="lumina-surface-muted rounded-lg p-3">
        <p className="mb-2 font-mono text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
          Capital Preservation Protocol
        </p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <GateTile label="Risk Events = 0" pass={gates.riskEventsZero} />
          <GateTile label="VaR = 0" pass={gates.varBreachesZero} />
          <GateTile label="DD ≤ $500" pass={gates.drawdownUnder500} />
          <GateTile label="Sharpe ≥ 1" pass={gates.sharpeAtLeast1} />
          <GateTile label="24h P&L ≥ 0" pass={gates.pnl24hNonNegative} />
        </div>
      </section>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className={utilityMetricTileClass("REAL")}>
          Live qty: <span className="font-mono">{realOps.exposure.livePositionQty}</span>
        </div>
        <div className={utilityMetricTileClass("REAL")}>
          Pending recon: <span className="font-mono">{realOps.exposure.pendingReconciliations}</span>
        </div>
        <div className={utilityMetricTileClass("REAL")}>
          Trades: <span className="font-mono">{realOps.totalTrades}</span>
        </div>
      </div>
    </div>
  );
}
