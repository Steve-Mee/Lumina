import { Suspense, lazy, type ReactNode } from "react";
import type { Transition } from "framer-motion";
import { motion } from "framer-motion";

import { ObservationDeckFrame } from "@/components/cockpit/ObservationDeckFrame";
import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { PPOEvolutionDeckView } from "@/components/cockpit/PPOEvolutionDeckView";
import { SimReadinessPanel } from "@/components/operations/SimReadinessPanel";
import { DECK_LOADING_COPY } from "@/lib/deckLoadingCopy";
import { EVOLUTION_DECK_TAB_SUBTITLES } from "@/lib/evolutionDeckNav";
import { panelCrossfadeWith, transitionOrNone } from "@/lib/motionPresets";
import type { CenterDeckTab } from "@/store/deckPanelStore";

const EvolutionArena = lazy(() =>
  import("@/components/EvolutionArena").then((module) => ({
    default: module.EvolutionArena,
  })),
);

function TabFallback({ label }: { label: string }) {
  return <PanelLoader label={label} className="min-h-[220px]" />;
}

function AnnexTabContent({
  tab,
  children,
}: {
  tab: CenterDeckTab;
  children: ReactNode;
}) {
  if (tab === "evolution") {
    return <>{children}</>;
  }
  return (
    <ObservationDeckFrame subtitle={EVOLUTION_DECK_TAB_SUBTITLES[tab]}>
      {children}
    </ObservationDeckFrame>
  );
}

interface EvolutionTabContentProps {
  tab: CenterDeckTab;
  reducedMotion: boolean;
  modeMotion: Transition | undefined;
}

export function EvolutionTabContent({
  tab,
  reducedMotion,
  modeMotion,
}: EvolutionTabContentProps) {
  const motionProps = {
    className: "flex min-h-0 flex-1 flex-col",
    variants: panelCrossfadeWith(modeMotion),
    initial: reducedMotion ? false : ("hidden" as const),
    animate: "visible" as const,
    transition: transitionOrNone(reducedMotion, modeMotion),
  };

  switch (tab) {
    case "evolution":
      return (
        <motion.div key="evolution" {...motionProps}>
          <Suspense fallback={<TabFallback label={DECK_LOADING_COPY.generic3d} />}>
            <EvolutionArena className="h-full min-h-[280px] w-full" />
          </Suspense>
        </motion.div>
      );
    case "ppo":
      return (
        <motion.div key="ppo" {...motionProps}>
          <AnnexTabContent tab="ppo">
            <PPOEvolutionDeckView className="flex-1" />
          </AnnexTabContent>
        </motion.div>
      );
    case "readiness":
      return (
        <motion.div key="readiness" {...motionProps}>
          <AnnexTabContent tab="readiness">
            <SimReadinessPanel />
          </AnnexTabContent>
        </motion.div>
      );
    default:
      return null;
  }
}
