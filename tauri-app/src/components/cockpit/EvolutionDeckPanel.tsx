import { Suspense, lazy, useEffect } from "react";
import { motion } from "framer-motion";

import { SimReadinessPanel } from "@/components/operations/SimReadinessPanel";
import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { PPOEvolutionDeckView } from "@/components/cockpit/PPOEvolutionDeckView";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { springSoft, transitionOrNone } from "@/lib/motionPresets";
import { selectActiveCenterTab, useDeckPanelStore, type CenterDeckTab } from "@/store/deckPanelStore";
import { cn } from "@/lib/utils";

const EvolutionArena = lazy(() =>
  import("@/components/EvolutionArena").then((module) => ({
    default: module.EvolutionArena,
  })),
);

export const EVOLUTION_DECK_TAB_SUBTITLES: Record<CenterDeckTab, string> = {
  evolution: "Pending mutation proposals",
  ppo: "Live policy evolution & training analytics",
  readiness: "SIM stability & REAL readiness criteria",
};

interface EvolutionDeckPanelProps {
  className?: string;
}

function ThreeDPanelFallback() {
  return <PanelLoader label="Loading 3D module…" className="min-h-[220px]" />;
}

export function EvolutionDeckPanel({ className }: EvolutionDeckPanelProps) {
  const reducedMotion = usePrefersReducedMotion();
  const activeCenterTab = useDeckPanelStore(selectActiveCenterTab);
  const setActiveCenterTab = useDeckPanelStore((state) => state.setActiveCenterTab);
  const hydrateCenterTab = useDeckPanelStore((state) => state.hydrateCenterTab);

  useEffect(() => {
    hydrateCenterTab();
  }, [hydrateCenterTab]);

  return (
    <div
      data-tour="evolution-deck"
      className={cn(
        "cockpit-panel flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-white/10 py-0",
        className,
      )}
    >
      <Tabs
        value={activeCenterTab}
        onValueChange={(value) => setActiveCenterTab(value as CenterDeckTab)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="relative border-b border-white/5 px-4 py-3">
          <motion.div
            className="absolute inset-x-4 top-0 h-px origin-left bg-gradient-to-r from-cyan-400/60 to-violet-400/30"
            initial={reducedMotion ? { scaleX: 1 } : { scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={transitionOrNone(reducedMotion, { ...springSoft, delay: 0.1 })}
          />
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-mono text-xs tracking-[0.18em] text-cyan-200/90 uppercase">
                Command Center
              </h2>
              <p className="font-mono text-[11px] text-muted-foreground/80">
                {EVOLUTION_DECK_TAB_SUBTITLES[activeCenterTab]}
              </p>
            </div>
            <TabsList>
              <TabsTrigger value="evolution">Evolution Queue</TabsTrigger>
              <TabsTrigger value="ppo">PPO Evolution</TabsTrigger>
              <TabsTrigger value="readiness">SIM Readiness</TabsTrigger>
            </TabsList>
          </div>
        </div>

        <TabsContent value="evolution" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <Suspense fallback={<ThreeDPanelFallback />}>
            <EvolutionArena className="h-full min-h-[280px] w-full" />
          </Suspense>
        </TabsContent>
        <TabsContent value="ppo" className="mt-0 flex min-h-0 flex-1 flex-col p-0">
          <PPOEvolutionDeckView className="flex-1" />
        </TabsContent>
        <TabsContent value="readiness" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <SimReadinessPanel className="h-full min-h-[280px]" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
