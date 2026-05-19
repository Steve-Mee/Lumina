import {
  motion,
  useMotionValueEvent,
  useReducedMotion,
  useSpring,
  useTransform,
} from "framer-motion";
import { Shield } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { FadeInView } from "@/components/cockpit/FadeInView";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  aggregateIntegrity,
  deriveCitadelWalls,
  integrityTier,
  tierBarClass,
  tierBorderClass,
  tierLabel,
  tierRingClass,
  type WallMetric,
} from "@/lib/riskCitadelMetrics";
import { cn } from "@/lib/utils";
import {
  selectLiveMetrics,
  selectRiskLevel,
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

function IntegrityBar({
  integrity,
  tier,
  reducedMotion,
}: {
  integrity: number;
  tier: WallMetric["tier"];
  reducedMotion: boolean;
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
        className={cn("absolute bottom-0 w-full rounded-full", tierBarClass(tier))}
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
}: CitadelWallProps) {
  const isCritical = wall.tier === "red";

  return (
    <motion.button
      type="button"
      style={{ gridArea }}
      aria-label={`${wall.label} integrity ${Math.round(wall.integrity)} percent`}
      onClick={() => onSelect(wall)}
      whileHover={reducedMotion ? undefined : { scale: 1.03 }}
      whileTap={reducedMotion ? undefined : { scale: 0.98 }}
      animate={
        isCritical && !reducedMotion
          ? { opacity: [0.78, 1, 0.78] }
          : { opacity: 1 }
      }
      transition={
        isCritical && !reducedMotion
          ? { duration: 1.4, repeat: Infinity, ease: "easeInOut" }
          : undefined
      }
      className={cn(
        "citadel-wall flex flex-col items-center justify-between gap-2 rounded-lg border bg-black/25 px-2 py-2.5 backdrop-blur-sm transition-colors focus-visible:ring-2 focus-visible:ring-cyan-400/50 focus-visible:outline-none",
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
      />
      <span className="font-mono text-[11px] text-foreground/90">
        {Math.round(wall.integrity)}%
      </span>
    </motion.button>
  );
}

function CitadelCore({
  integrity,
  tier,
  reducedMotion,
}: {
  integrity: number;
  tier: ReturnType<typeof integrityTier>;
  reducedMotion: boolean;
}) {
  const spring = useSpring(integrity, {
    stiffness: 100,
    damping: 20,
  });
  const [displayValue, setDisplayValue] = useState(Math.round(integrity));

  useEffect(() => {
    spring.set(integrity);
  }, [integrity, spring]);

  useMotionValueEvent(spring, "change", (latest) => {
    setDisplayValue(Math.round(latest));
  });

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ gridArea: "core" }}
    >
      <motion.div
        className={cn(
          "absolute size-24 rounded-full border-2 border-dashed md:size-28",
          tierRingClass(tier),
        )}
        animate={reducedMotion ? undefined : { rotate: 360 }}
        transition={
          reducedMotion
            ? undefined
            : { duration: 24, repeat: Infinity, ease: "linear" }
        }
      />
      <div
        className={cn(
          "relative flex size-20 flex-col items-center justify-center rounded-2xl border bg-gradient-to-br from-cyan-950/80 via-black/60 to-violet-950/70 md:size-24",
          tierRingClass(tier),
        )}
      >
        <Shield className="mb-1 size-5 text-cyan-300/80" aria-hidden />
        <motion.span
          key={displayValue}
          initial={reducedMotion ? false : { scale: 0.92, opacity: 0.7 }}
          animate={{ scale: 1, opacity: 1 }}
          className="font-mono text-xl font-medium text-cyan-100 md:text-2xl"
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
  lastUpdatedTs,
  open,
  onOpenChange,
}: {
  wall: WallMetric | null;
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

export function RiskCitadel({ className, walls: wallsOverride }: RiskCitadelProps) {
  const reducedMotion = useReducedMotion() ?? false;
  const riskLevel = useCoreStore(selectRiskLevel);
  const liveMetrics = useCoreStore(selectLiveMetrics);

  const walls = useMemo(() => {
    if (wallsOverride) {
      return wallsOverride;
    }
    return deriveCitadelWalls(useCoreStore.getState());
  }, [wallsOverride, riskLevel, liveMetrics]);

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
        role="img"
        aria-label={`Risk citadel aggregate integrity ${Math.round(aggregate)} percent`}
        className={cn(
          "grid w-full max-w-sm grid-cols-3 grid-rows-3 gap-2 md:max-w-md md:gap-2.5",
        )}
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
        />
        <CitadelWall
          wall={wallById.kelly}
          gridArea="kelly"
          onSelect={openWallDetail}
          reducedMotion={reducedMotion}
        />
        <CitadelCore
          integrity={aggregate}
          tier={aggregateTier}
          reducedMotion={reducedMotion}
        />
        <CitadelWall
          wall={wallById.regime}
          gridArea="regime"
          onSelect={openWallDetail}
          reducedMotion={reducedMotion}
        />
        <CitadelWall
          wall={wallById.drawdown}
          gridArea="drawdown"
          onSelect={openWallDetail}
          reducedMotion={reducedMotion}
        />
      </div>
      </FadeInView>

      <WallDetailDialog
        wall={selectedWall}
        lastUpdatedTs={liveMetrics.lastUpdatedTs}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </>
  );
}
