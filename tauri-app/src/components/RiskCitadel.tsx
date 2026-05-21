import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { motion, useMotionValueEvent, useSpring, useTransform } from "framer-motion";
import { Shield, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { FadeInView } from "@/components/cockpit/FadeInView";
import { CitadelEnergyField } from "@/components/cockpit/CitadelEnergyField";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { citadelCoreGradient, citadelShieldClass, distressPanelClass, warnOverlayBodyClass } from "@/lib/modePresentation";
import {
  aggregateIntegrity,
  citadelModeHeadline,
  deriveCitadelWalls,
  integrityTier,
  tierBarClass,
  tierBorderClass,
  tierLabel,
  tierRingClass,
  wallEducationCopy,
  type WallMetric,
} from "@/lib/riskCitadelMetrics";
import { cn } from "@/lib/utils";
import {
  selectCurrentMode,
  selectFortress,
  selectLiveMetrics,
  selectRiskLevel,
  selectSafeModeActive,
  useCoreStore,
} from "@/store/coreStore";

interface RiskCitadelProps {
  className?: string;
  walls?: WallMetric[];
}

interface CitadelWallProps {
  wall: WallMetric;
  gridArea: string;
  onSelect: (wall: WallMetric) => void;
  reducedMotion: boolean;
}

function formatUsd(value: number | null): string {
  if (value === null) {
    return "—";
  }
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function IntegrityBar({
  integrity,
  tier,
  reducedMotion,
  calmMode,
}: {
  integrity: number;
  tier: WallMetric["tier"];
  reducedMotion: boolean;
  calmMode: boolean;
}) {
  const spring = useSpring(integrity, {
    stiffness: 120,
    damping: 18,
    mass: 0.6,
  });
  const height = useTransform(spring, (value) => `${value}%`);

  return (
    <div className="relative h-16 w-2 overflow-hidden rounded-full bg-white/5">
      <motion.div
        className={cn(
          "absolute bottom-0 w-full rounded-full",
          tierBarClass(tier),
          !calmMode && !reducedMotion && "citadel-bar-shimmer",
        )}
        style={{ height: reducedMotion ? `${integrity}%` : height }}
      />
    </div>
  );
}

function CitadelWall({
  wall,
  gridArea,
  onSelect,
  reducedMotion,
  calmMode,
}: CitadelWallProps & { calmMode: boolean }) {
  const isCritical = wall.tier === "red";

  return (
    <div className="citadel-wall-segment" style={{ gridArea }}>
      <motion.button
        type="button"
        aria-label={`${wall.label} integrity ${Math.round(wall.integrity)} percent`}
        onClick={() => onSelect(wall)}
        whileHover={reducedMotion ? undefined : { scale: 1.03 }}
        whileTap={reducedMotion ? undefined : { scale: 0.98 }}
        className={cn(
          "citadel-wall lumina-glass flex h-full w-full flex-col items-center justify-between gap-2 rounded-lg border px-2 py-2.5 transition-colors focus-visible:ring-2 focus-visible:ring-cyan-400/50 focus-visible:outline-none",
          tierBorderClass(wall.tier),
          isCritical && "citadel-wall-critical",
        )}
      >
        <span className="text-[9px] tracking-[0.14em] text-muted-foreground uppercase">
          {wall.label}
        </span>
        <IntegrityBar
          integrity={wall.integrity}
          tier={wall.tier}
          reducedMotion={reducedMotion}
          calmMode={calmMode}
        />
        <span className="font-mono text-[11px] text-foreground/90">
          {Math.round(wall.integrity)}%
        </span>
      </motion.button>
    </div>
  );
}

function CitadelCore({
  integrity,
  tier,
  reducedMotion,
  mode,
  calmMode,
}: {
  integrity: number;
  tier: ReturnType<typeof integrityTier>;
  reducedMotion: boolean;
  mode: ReturnType<typeof selectCurrentMode>;
  calmMode: boolean;
}) {
  const spring = useSpring(integrity, {
    stiffness: 100,
    damping: 20,
  });
  const [displayValue, setDisplayValue] = useState(Math.round(integrity));
  const ringDuration = reducedMotion ? null : calmMode ? 24 : 12;

  useEffect(() => {
    spring.set(integrity);
  }, [integrity, spring]);

  useMotionValueEvent(spring, "change", (latest) => {
    setDisplayValue(Math.round(latest));
  });

  return (
    <div
      className="citadel-core-field relative flex items-center justify-center"
      style={{ gridArea: "core" }}
    >
      {ringDuration !== null ? (
        <motion.div
          className={cn(
            "absolute size-24 rounded-full border border-dashed md:size-28",
            tierRingClass(tier),
          )}
          animate={{ rotate: 360 }}
          transition={{ duration: ringDuration, repeat: Infinity, ease: "linear" }}
        />
      ) : (
        <div
          className={cn(
            "absolute size-24 rounded-full border border-dashed md:size-28",
            tierRingClass(tier),
          )}
        />
      )}
      <div
        className={cn(
          "relative flex size-20 flex-col items-center justify-center rounded-2xl border bg-gradient-to-br md:size-24",
          citadelCoreGradient(mode),
          tierRingClass(tier),
        )}
      >
        <Shield className={cn("mb-1 size-5", citadelShieldClass(mode))} aria-hidden />
        <motion.span
          key={displayValue}
          initial={reducedMotion ? false : { scale: 0.92, opacity: 0.7 }}
          animate={{ scale: 1, opacity: 1 }}
          className={cn(
            "font-mono text-xl font-medium md:text-2xl",
            mode === "SIM" ? "text-cyan-100" : "text-amber-100/90",
          )}
        >
          {reducedMotion ? Math.round(integrity) : displayValue}
        </motion.span>
        <span className="text-[8px] tracking-[0.18em] text-muted-foreground uppercase">
          Integrity
        </span>
      </div>
    </div>
  );
}

function WallDetailDialog({
  wall,
  mode,
  lastUpdatedTs,
  open,
  onOpenChange,
}: {
  wall: WallMetric | null;
  mode: ReturnType<typeof selectCurrentMode>;
  lastUpdatedTs: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!wall) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-cyan-100">
            {wall.label}
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px] tracking-wider uppercase",
                wall.tier === "green" && "bg-emerald-500/15 text-emerald-300",
                wall.tier === "orange" && "bg-amber-500/15 text-amber-300",
                wall.tier === "red" && "bg-red-500/15 text-red-300",
              )}
            >
              {tierLabel(wall.tier)}
            </span>
          </DialogTitle>
          <DialogDescription>{wall.description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <p className="text-[10px] text-muted-foreground/90">
            {wallEducationCopy(wall.id, mode)}
          </p>

          <div className="flex items-baseline justify-between border-b border-white/10 pb-2">
            <span className="text-[10px] tracking-[0.14em] text-muted-foreground uppercase">
              Integrity
            </span>
            <span className="font-mono text-2xl text-foreground">
              {Math.round(wall.integrity)}%
            </span>
          </div>

          <dl className="space-y-1.5 text-[11px]">
            {Object.entries(wall.rawValues).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-4">
                <dt className="text-muted-foreground">{key}</dt>
                <dd className="text-right text-cyan-100/90">
                  {value === null ? "—" : String(value)}
                </dd>
              </div>
            ))}
          </dl>

          {wall.isStandby ? (
            <p className="text-[10px] text-amber-300/80">
              Standby estimate — awaiting live telemetry for this wall.
            </p>
          ) : null}

          {lastUpdatedTs ? (
            <p className="text-[10px] text-muted-foreground/70">
              Last updated: {lastUpdatedTs}
            </p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function CitadelProtectiveBanner({
  safeModeActive,
  killSwitchActive,
}: {
  safeModeActive: boolean;
  killSwitchActive: boolean;
}) {
  if (!safeModeActive && !killSwitchActive) {
    return null;
  }

  return (
    <div className={cn("citadel-lockdown-banner mb-2 flex items-center gap-2 px-2 py-1.5 text-[10px]", distressPanelClass("warn"))}>
      <ShieldAlert className="size-3.5 shrink-0" aria-hidden />
      <span className={warnOverlayBodyClass()}>
        {killSwitchActive
          ? "Kill switch active — fortress in protective lockdown"
          : "REAL safe mode — telemetry disconnected, controls blocked"}
      </span>
    </div>
  );
}

function CitadelCapitalFooter({
  equity,
  dailyPnl,
  openPnl,
}: {
  equity: number | null;
  dailyPnl: number | null;
  openPnl: number | null;
}) {
  return (
    <div className="citadel-capital-strip mt-2 grid grid-cols-3 gap-2 font-mono text-[9px]">
      <div className="px-1 py-0.5">
        <span className="text-muted-foreground">Equity</span>
        <p className="text-cyan-100/90">
          {equity !== null ? `$${equity.toLocaleString()}` : "—"}
        </p>
      </div>
      <div className="px-1 py-0.5">
        <span className="text-muted-foreground">Daily PnL</span>
        <p className={dailyPnl !== null && dailyPnl < 0 ? "text-red-300/90" : "text-emerald-300/90"}>
          {formatUsd(dailyPnl)}
        </p>
      </div>
      <div className="px-1 py-0.5">
        <span className="text-muted-foreground">Open PnL</span>
        <p className={openPnl !== null && openPnl < 0 ? "text-red-300/90" : "text-emerald-300/90"}>
          {formatUsd(openPnl)}
        </p>
      </div>
    </div>
  );
}

export function RiskCitadel({ className, walls: wallsOverride }: RiskCitadelProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const mode = useCoreStore(selectCurrentMode);
  const safeModeActive = useCoreStore(selectSafeModeActive);
  const fortress = useCoreStore(selectFortress);
  const riskLevel = useCoreStore(selectRiskLevel);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const reducedMotion = prefersReducedMotion;
  const calmMode = mode === "REAL";
  const lockdown = safeModeActive || (fortress?.kill_switch_active ?? false);

  const walls = useMemo(() => {
    if (wallsOverride) {
      return wallsOverride;
    }
    return deriveCitadelWalls(useCoreStore.getState());
  }, [wallsOverride, riskLevel, liveMetrics, fortress, mode]);

  const aggregate = useMemo(() => aggregateIntegrity(walls), [walls]);
  const aggregateTier = integrityTier(aggregate);

  const wallById = useMemo(
    () => ({
      risk: walls.find((wall) => wall.id === "risk")!,
      kelly: walls.find((wall) => wall.id === "kelly")!,
      regime: walls.find((wall) => wall.id === "regime")!,
      drawdown: walls.find((wall) => wall.id === "drawdown")!,
    }),
    [walls],
  );

  const [selectedWall, setSelectedWall] = useState<WallMetric | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const openWallDetail = (wall: WallMetric) => {
    setSelectedWall(wall);
    setDialogOpen(true);
  };

  return (
    <>
      <FadeInView className={cn("w-full", className)}>
        <div
          className="citadel-shell flex flex-col items-center"
          data-mode={mode}
          data-lockdown={lockdown ? "true" : undefined}
        >
          <CitadelProtectiveBanner
            safeModeActive={safeModeActive}
            killSwitchActive={fortress?.kill_switch_active ?? false}
          />

          <p
            className={cn(
              "mb-2 text-center text-[9px] tracking-[0.12em] uppercase",
              mode === "SIM" ? "text-cyan-300/70" : "text-amber-200/60",
            )}
          >
            {citadelModeHeadline(mode)}
          </p>

          <div className="relative w-full max-w-sm md:max-w-md">
            <CitadelEnergyField
              aggregate={aggregate}
              tier={aggregateTier}
              walls={walls}
              mode={mode}
              lockdown={lockdown}
              calmMode={calmMode}
              reducedMotion={reducedMotion}
            />
            <div
              role="img"
              aria-label={`Risk citadel aggregate integrity ${Math.round(aggregate)} percent`}
              className="relative grid w-full grid-cols-3 grid-rows-3 gap-2 md:gap-2.5"
              style={{
                gridTemplateAreas: `
            ". risk ."
            "kelly core regime"
            ". drawdown ."
          `,
              }}
            >
              <CitadelWall
                wall={wallById.risk}
                gridArea="risk"
                onSelect={openWallDetail}
                reducedMotion={reducedMotion}
                calmMode={calmMode}
              />
              <CitadelWall
                wall={wallById.kelly}
                gridArea="kelly"
                onSelect={openWallDetail}
                reducedMotion={reducedMotion}
                calmMode={calmMode}
              />
              <CitadelCore
                integrity={aggregate}
                tier={aggregateTier}
                reducedMotion={reducedMotion}
                mode={mode}
                calmMode={calmMode}
              />
              <CitadelWall
                wall={wallById.regime}
                gridArea="regime"
                onSelect={openWallDetail}
                reducedMotion={reducedMotion}
                calmMode={calmMode}
              />
              <CitadelWall
                wall={wallById.drawdown}
                gridArea="drawdown"
                onSelect={openWallDetail}
                reducedMotion={reducedMotion}
                calmMode={calmMode}
              />
            </div>
          </div>

          <CitadelCapitalFooter
            equity={liveMetrics.equity}
            dailyPnl={liveMetrics.dailyPnlUsd}
            openPnl={liveMetrics.openPnl}
          />
        </div>
      </FadeInView>

      <WallDetailDialog
        wall={selectedWall}
        mode={mode}
        lastUpdatedTs={liveMetrics.lastUpdatedTs}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </>
  );
}
