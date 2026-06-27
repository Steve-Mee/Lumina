import { useEffect, useState } from "react";

import { IntelligenceTierBadgeLive } from "@/components/intelligence/IntelligenceTierBadge";
import { IntelligenceTabContent } from "@/components/cockpit/IntelligenceTabContent";
import { SubsystemsDrawer, SubsystemsDrawerTrigger } from "@/components/cockpit/SubsystemsDrawer";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePanelTabTransition } from "@/hooks/usePanelTabTransition";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import {
  analyticsAnnexTabClass,
  isAnalyticsRightTab,
} from "@/lib/analyticsAnnexPresentation";
import {
  INTELLIGENCE_DECK_TAB_SUBTITLES,
  INTELLIGENCE_PRIMARY_TABS,
  isOpsTab,
  opsTabLabel,
  primaryTabLabel,
  resolveOpsSections,
} from "@/lib/intelligenceDeckNav";
import { transitionOrNone } from "@/lib/motionPresets";
import {  modeTitleClass, pendingHighlightClass, deckPanelFrameClass } from "@/lib/modePresentation";
import {
  selectActiveRightTab,
  useDeckPanelStore,
  type RightDeckTab,
} from "@/store/deckPanelStore";
import {
  selectCurrentMode,
  selectEvolutionState,
  useCoreStore,
} from "@/store/coreStore";
import { useHudMetricsHintStore } from "@/store/hudMetricsHintStore";
import { REAL_OPS_HINT_KEY } from "@/lib/deckStatusConstants";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface IntelligenceDeckPanelProps {
  className?: string;
  frameVariant?: "glass" | "muted";
}

export function IntelligenceDeckPanel({
  className,
  frameVariant = "glass",
}: IntelligenceDeckPanelProps) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const activeRightTab = useDeckPanelStore(selectActiveRightTab);
  const setActiveRightTab = useDeckPanelStore((state) => state.setActiveRightTab);
  const hydrateRightTab = useDeckPanelStore((state) => state.hydrateRightTab);
  const operatorMode = useCoreStore(selectCurrentMode);
  const pendingApprovals = useCoreStore(selectEvolutionState).pendingCount;
  const isReal = operatorMode === "REAL";
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [realOpsHint, setRealOpsHint] = useState(false);
  const metricsHintActive = useHudMetricsHintStore((s) => s.active);
  const metricsHintPulse = useHudMetricsHintStore((s) => s.pulse);
  const isOpsActive = isOpsTab(activeRightTab);
  const isAnnexActive = isAnalyticsRightTab(activeRightTab);
  const hideSubtitle = drawerOpen || isOpsActive;
  const { pulseTabTransition } = usePanelTabTransition('[data-tour="intelligence-deck"]');

  useEffect(() => {
    hydrateRightTab();
  }, [hydrateRightTab]);

  useEffect(() => {
    pulseTabTransition();
  }, [activeRightTab, pulseTabTransition]);

  useEffect(() => {
    if (isReal && !sessionStorage.getItem(REAL_OPS_HINT_KEY)) {
      sessionStorage.setItem(REAL_OPS_HINT_KEY, "1");
      setRealOpsHint(true);
      const timer = window.setTimeout(() => setRealOpsHint(false), 8000);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [isReal]);

  return (
    <div
      data-tour="intelligence-deck"
      data-mode={operatorMode}
      className={cn(
        "flex min-h-0 flex-1 flex-col overflow-hidden",
        deckPanelFrameClass(frameVariant, operatorMode),
        className,
      )}
    >
      <Tabs
        value={activeRightTab}
        onValueChange={(value) => setActiveRightTab(value as RightDeckTab)}
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
                Intelligence{isAnnexActive ? " · Annex" : ""}
              </h2>
              {!hideSubtitle ? (
                <p className="font-mono text-[11px] text-muted-foreground/80">
                  {INTELLIGENCE_DECK_TAB_SUBTITLES[activeRightTab]}
                </p>
              ) : null}
            </div>
            <div className="flex max-w-full flex-wrap items-center gap-1">
              <TabsList className="max-w-full flex-wrap justify-end">
                {INTELLIGENCE_PRIMARY_TABS.map((tab) => (
                  <TabsTrigger
                    key={tab}
                    value={tab}
                    className={cn(
                      tab === "performance" ? analyticsAnnexTabClass() : undefined,
                      tab === "performance" &&
                        metricsHintActive &&
                        "deck-tab-chip deck-tab-chip--metrics-hint",
                      tab === "performance" &&
                        metricsHintPulse &&
                        "deck-tab-chip--hint-pulse",
                    )}
                  >
                    {primaryTabLabel(tab)}
                  </TabsTrigger>
                ))}
              </TabsList>
              <SubsystemsDrawerTrigger
                badgeCount={pendingApprovals}
                badgeVariant="mode"
                onClick={() => setDrawerOpen(true)}
                className={cn(
                  isOpsActive ? "deck-tab-chip deck-tab-chip--active border-transparent" : undefined,
                  realOpsHint && "deck-tab-chip--hint-pulse",
                )}
              />
            </div>
          </div>
        </div>

        <div className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <IntelligenceTabContent
            tab={activeRightTab}
            operatorMode={operatorMode}
            reducedMotion={reducedMotion}
            modeMotion={modeMotion}
          />
        </div>
      </Tabs>

      <SubsystemsDrawer
        open={drawerOpen}
        activeTab={activeRightTab}
        onOpenChange={setDrawerOpen}
        onSelectTab={setActiveRightTab}
        sections={resolveOpsSections(operatorMode)}
        getTabLabel={opsTabLabel}
        footerText={`${resolveOpsSections(operatorMode).length} sections · ${operatorMode} mode`}
        getTabBadge={(tab) => (tab === "evolutionApprovals" ? pendingApprovals : undefined)}
        getTabHighlightClass={(tab) =>
          tab === "evolutionApprovals" && pendingApprovals > 0
            ? pendingHighlightClass(operatorMode)
            : undefined
        }
        footerSlot={<IntelligenceTierBadgeLive compact />}
      />
    </div>
  );
}
