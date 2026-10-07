import { useEffect, useState } from "react";

import { BarChart3 } from "lucide-react";
import { motion } from "framer-motion";

import { EvolutionTabContent } from "@/components/cockpit/EvolutionTabContent";
import { SubsystemsDrawer, SubsystemsDrawerTrigger } from "@/components/cockpit/SubsystemsDrawer";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePanelTabTransition } from "@/hooks/usePanelTabTransition";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import {
  analyticsAnnexTabClass,
  isAnalyticsCenterTab,
} from "@/lib/analyticsAnnexPresentation";
import {
  EVOLUTION_DECK_TAB_SUBTITLES,
  EVOLUTION_OPS_SECTIONS,
  evolutionOpsTabLabel,
  isEvolutionOpsTab,
} from "@/lib/evolutionDeckNav";
import { luminaSurfaceMutedClass } from "@/lib/glassGlowTaxonomy";
import { deckPanelFrameClass, modeTitleClass } from "@/lib/modePresentation";
import { transitionOrNone } from "@/lib/motionPresets";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { selectActiveCenterTab, useDeckPanelStore } from "@/store/deckPanelStore";
import { cn } from "@/lib/utils";

export { EVOLUTION_DECK_TAB_SUBTITLES } from "@/lib/evolutionDeckNav";

interface EvolutionDeckPanelProps {
  className?: string;
  frameVariant?: "glass" | "muted";
}

export function EvolutionDeckPanel({
  className,
  frameVariant = "muted",
}: EvolutionDeckPanelProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const operatorMode = useCoreStore(selectCurrentMode);
  const activeCenterTab = useDeckPanelStore(selectActiveCenterTab);
  const setActiveCenterTab = useDeckPanelStore((state) => state.setActiveCenterTab);
  const hydrateCenterTab = useDeckPanelStore((state) => state.hydrateCenterTab);
  const isReal = operatorMode === "REAL";
  const isAnnexActive = isAnalyticsCenterTab(activeCenterTab);
  const isOpsActive = isEvolutionOpsTab(activeCenterTab);
  const arenaActive = activeCenterTab === "evolution";
  const [drawerOpen, setDrawerOpen] = useState(false);
  const hideSubtitle = drawerOpen || isOpsActive;
  const { pulseTabTransition } = usePanelTabTransition('[data-tour="evolution-deck"]');

  useEffect(() => {
    hydrateCenterTab();
  }, [hydrateCenterTab]);

  useEffect(() => {
    pulseTabTransition();
  }, [activeCenterTab, pulseTabTransition]);

  return (
    <div
      data-tour="evolution-deck"
      data-mode={operatorMode}
      className={cn(
        "flex min-h-0 flex-1 flex-col overflow-hidden",
        deckPanelFrameClass(frameVariant, operatorMode),
        className,
      )}
    >
      <div
        className={cn(
          "deck-panel-toolbar risk-envelope-panel__toolbar relative",
          arenaActive && cn(luminaSurfaceMutedClass(), "rounded-none border-white/5"),
          isAnnexActive && "deck-header--annex",
        )}
      >
        <motion.div
          className="deck-panel-accent absolute inset-x-4 top-0 h-px origin-left"
          initial={reducedMotion ? { scaleX: 1 } : { scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={transitionOrNone(reducedMotion, { ...modeMotion, delay: 0.1 })}
        />
        <div className="command-deck-ops__board-chrome-row">
          <div className="command-deck-ops__board-identity min-w-0">
            <p
              className={cn(
                "risk-envelope-panel__toolbar-title",
                isAnnexActive ? "text-muted-foreground/80" : modeTitleClass(operatorMode),
              )}
            >
              Evolution{isAnnexActive ? " · Annex" : ""}
            </p>
            {!hideSubtitle ? (
              <p className="mt-0.5 truncate font-mono text-[0.5rem] tracking-wide text-white/30 uppercase">
                {EVOLUTION_DECK_TAB_SUBTITLES[activeCenterTab]}
              </p>
            ) : null}
          </div>
          <div className="command-deck-ops__board-nav">
            <button
              type="button"
              className={cn(
                "genesis-recovery-action-card__btn command-deck-ops__organ-btn",
                arenaActive && "genesis-recovery-action-card__btn--accent",
              )}
              aria-pressed={arenaActive}
              onClick={() => {
                setDrawerOpen(false);
                setActiveCenterTab("evolution");
              }}
            >
              Arena
            </button>
            <SubsystemsDrawerTrigger
              label="Analytics"
              icon={BarChart3}
              onClick={() => setDrawerOpen(true)}
              className={isOpsActive ? "deck-tab-chip deck-tab-chip--active border-transparent" : undefined}
            />
          </div>
        </div>
      </div>

      <div className={cn("mt-0 flex min-h-0 flex-1 flex-col", arenaActive ? "p-0" : "p-2")}>
        <EvolutionTabContent
          tab={activeCenterTab}
          reducedMotion={reducedMotion}
          modeMotion={modeMotion}
        />
      </div>

      <SubsystemsDrawer
        open={drawerOpen}
        activeTab={activeCenterTab}
        onOpenChange={setDrawerOpen}
        onSelectTab={setActiveCenterTab}
        sections={EVOLUTION_OPS_SECTIONS}
        getTabLabel={evolutionOpsTabLabel}
        title="Analytics"
        subtitle="PPO evolution & SIM readiness"
        footerText={`${EVOLUTION_OPS_SECTIONS.length} section · ${operatorMode} mode`}
        getTabHighlightClass={(tab) =>
          tab === "readiness" && isReal ? analyticsAnnexTabClass() : undefined
        }
      />
    </div>
  );
}
