import { Suspense, lazy, useEffect, useState } from "react";

import { BarChart3 } from "lucide-react";

import { motion } from "framer-motion";



import { EvolutionTabContent } from "@/components/cockpit/EvolutionTabContent";

import { SubsystemsDrawer, SubsystemsDrawerTrigger } from "@/components/cockpit/SubsystemsDrawer";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

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

  EVOLUTION_PRIMARY_TABS,

  evolutionOpsTabLabel,

  isEvolutionOpsTab,

  primaryEvolutionTabLabel,

} from "@/lib/evolutionDeckNav";

import { transitionOrNone } from "@/lib/motionPresets";

import { modePanelClass, modeTitleClass } from "@/lib/modePresentation";

import { selectActiveCenterTab, useDeckPanelStore, type CenterDeckTab } from "@/store/deckPanelStore";

import { selectCurrentMode, useCoreStore } from "@/store/coreStore";

import { cn } from "@/lib/utils";



export { EVOLUTION_DECK_TAB_SUBTITLES } from "@/lib/evolutionDeckNav";



interface EvolutionDeckPanelProps {

  className?: string;

}



export function EvolutionDeckPanel({ className }: EvolutionDeckPanelProps) {

  const reducedMotion = usePrefersReducedMotion();

  const modeMotion = useModeMotion();

  const operatorMode = useCoreStore(selectCurrentMode);

  const activeCenterTab = useDeckPanelStore(selectActiveCenterTab);

  const setActiveCenterTab = useDeckPanelStore((state) => state.setActiveCenterTab);

  const hydrateCenterTab = useDeckPanelStore((state) => state.hydrateCenterTab);

  const isReal = operatorMode === "REAL";

  const isAnnexActive = isAnalyticsCenterTab(activeCenterTab);

  const isOpsActive = isEvolutionOpsTab(activeCenterTab);

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

        "lumina-glass lumina-glass--panel lumina-glass--interactive flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg py-0",

        modePanelClass(operatorMode),

        className,

      )}

    >

      <Tabs

        value={activeCenterTab}

        onValueChange={(value) => setActiveCenterTab(value as CenterDeckTab)}

        className="flex min-h-0 flex-1 flex-col"

      >

        <div

          className={cn(

            "relative border-b border-white/5 px-4 py-3",

            isAnnexActive && "deck-header--annex",

          )}

        >

          <motion.div

            className="deck-panel-accent absolute inset-x-4 top-0 h-px origin-left"

            initial={reducedMotion ? { scaleX: 1 } : { scaleX: 0 }}

            animate={{ scaleX: 1 }}

            transition={transitionOrNone(reducedMotion, { ...modeMotion, delay: 0.1 })}

          />

          <div className="flex flex-wrap items-start justify-between gap-3">

            <div>

              <h2

                className={cn(

                  "deck-header-title deck-title mode-text-tier2",

                  isAnnexActive ? "text-muted-foreground/80" : modeTitleClass(operatorMode),

                )}

              >

                Evolution{isAnnexActive ? " · Annex" : ""}

              </h2>

              {!hideSubtitle ? (

                <p className="font-mono text-[11px] text-muted-foreground/80">

                  {EVOLUTION_DECK_TAB_SUBTITLES[activeCenterTab]}

                </p>

              ) : null}

            </div>

            <div className="flex items-center gap-1">

              <TabsList>

                {EVOLUTION_PRIMARY_TABS.map((tab) => (

                  <TabsTrigger key={tab} value={tab}>

                    {primaryEvolutionTabLabel(tab)}

                  </TabsTrigger>

                ))}

              </TabsList>

              <SubsystemsDrawerTrigger

                label="Analytics"

                icon={BarChart3}

                onClick={() => setDrawerOpen(true)}

                className={isOpsActive ? "deck-tab-chip deck-tab-chip--active border-transparent" : undefined}

              />

            </div>

          </div>

        </div>



        <div className="mt-0 flex min-h-0 flex-1 flex-col p-2">

          <EvolutionTabContent

            tab={activeCenterTab}

            reducedMotion={reducedMotion}

            modeMotion={modeMotion}

          />

        </div>

      </Tabs>



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

