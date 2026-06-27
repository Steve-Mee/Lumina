import { Suspense, lazy, type ReactNode } from "react";
import type { Transition } from "framer-motion";
import { motion } from "framer-motion";

import { AnalyticsAnnexShell } from "@/components/cockpit/AnalyticsAnnexShell";
import { ObservationDeckFrame } from "@/components/cockpit/ObservationDeckFrame";
import { PanelLoader } from "@/components/cockpit/PanelLoader";
import { AdaptiveIntelligenceHistoryPanel } from "@/components/intelligence/AdaptiveIntelligenceHistoryPanel";
import { AdaptiveIntelligenceRecentEvents } from "@/components/intelligence/AdaptiveIntelligenceRecentEvents";
import { AdaptiveIntelligenceStatusCard } from "@/components/intelligence/AdaptiveIntelligenceStatusCard";
import { CommunityPanel } from "@/components/operations/CommunityPanel";
import { EvolutionApprovalsPanel } from "@/components/operations/EvolutionApprovalsPanel";
import { LiveActivityPanel } from "@/components/operations/LiveActivityPanel";
import { RealOperationsPanel } from "@/components/operations/RealOperationsPanel";
import { DECK_LOADING_COPY } from "@/lib/deckLoadingCopy";
import { INTELLIGENCE_DECK_TAB_SUBTITLES } from "@/lib/intelligenceDeckNav";
import { panelCrossfadeWith, transitionOrNone } from "@/lib/motionPresets";
import type { RightDeckTab } from "@/store/deckPanelStore";
import type { TradingMode } from "@/store/coreStore";

const DecisionTheater = lazy(() =>
  import("@/components/DecisionTheater").then((module) => ({
    default: module.DecisionTheater,
  })),
);

const SystemMonitorPanel = lazy(() =>
  import("@/components/intelligence/SystemMonitorPanel").then((module) => ({
    default: module.SystemMonitorPanel,
  })),
);

const AdminPanel = lazy(() =>
  import("@/components/operations/AdminPanel").then((module) => ({
    default: module.AdminPanel,
  })),
);

const HardwareModelPanel = lazy(() =>
  import("@/components/operations/HardwareModelPanel").then((module) => ({
    default: module.HardwareModelPanel,
  })),
);

const TradingPerformancePanel = lazy(() =>
  import("@/components/performance/TradingPerformancePanel").then((module) => ({
    default: module.TradingPerformancePanel,
  })),
);

function TabFallback({ label }: { label: string }) {
  return <PanelLoader label={label} className="min-h-[220px]" />;
}

function AnnexTabContent({
  tab,
  children,
  inset = false,
}: {
  tab: RightDeckTab;
  children: ReactNode;
  inset?: boolean;
}) {
  if (tab === "brief") {
    return <>{children}</>;
  }
  if (tab === "performance") {
    return (
      <ObservationDeckFrame subtitle={INTELLIGENCE_DECK_TAB_SUBTITLES[tab]} inset={inset}>
        {children}
      </ObservationDeckFrame>
    );
  }
  if (
    tab === "hardware" ||
    tab === "monitor" ||
    tab === "liveActivity" ||
    tab === "community"
  ) {
    return (
      <ObservationDeckFrame subtitle={INTELLIGENCE_DECK_TAB_SUBTITLES[tab]}>
        {children}
      </ObservationDeckFrame>
    );
  }
  return (
    <AnalyticsAnnexShell subtitle={INTELLIGENCE_DECK_TAB_SUBTITLES[tab]}>
      {children}
    </AnalyticsAnnexShell>
  );
}

interface IntelligenceTabContentProps {
  tab: RightDeckTab;
  operatorMode: TradingMode;
  reducedMotion: boolean;
  modeMotion: Transition | undefined;
}

export function IntelligenceTabContent({
  tab,
  operatorMode,
  reducedMotion,
  modeMotion,
}: IntelligenceTabContentProps) {
  const motionProps = {
    className: "flex min-h-0 flex-1 flex-col",
    variants: panelCrossfadeWith(modeMotion),
    initial: reducedMotion ? false : ("hidden" as const),
    animate: "visible" as const,
    transition: transitionOrNone(reducedMotion, modeMotion),
  };

  switch (tab) {
    case "brief":
      return (
        <motion.div key="brief" {...motionProps}>
          <Suspense fallback={<TabFallback label={DECK_LOADING_COPY.neuralCore} />}>
            <DecisionTheater className="h-full min-h-[280px] w-full" />
          </Suspense>
        </motion.div>
      );
    case "adaptive":
      return (
        <motion.div key="adaptive" {...motionProps}>
          <AnnexTabContent tab="adaptive">
            <div className="flex min-h-0 flex-1 flex-col gap-3 p-2">
              <AdaptiveIntelligenceStatusCard />
              <AdaptiveIntelligenceRecentEvents />
              <div className="min-h-[180px] flex-1">
                <AdaptiveIntelligenceHistoryPanel className="h-full" />
              </div>
            </div>
          </AnnexTabContent>
        </motion.div>
      );
    case "performance":
      return (
        <motion.div key="performance" {...motionProps}>
          <AnnexTabContent tab="performance" inset>
            <Suspense fallback={<TabFallback label={DECK_LOADING_COPY.ppoSync} />}>
              <TradingPerformancePanel />
            </Suspense>
          </AnnexTabContent>
        </motion.div>
      );
    case "realOps":
      if (operatorMode !== "REAL") {
        return null;
      }
      return (
        <motion.div key="realOps" {...motionProps}>
          <AnnexTabContent tab="realOps">
            <RealOperationsPanel className="p-2" />
          </AnnexTabContent>
        </motion.div>
      );
    case "evolutionApprovals":
      return (
        <motion.div key="evolutionApprovals" {...motionProps}>
          <AnnexTabContent tab="evolutionApprovals">
            <EvolutionApprovalsPanel className="p-2" />
          </AnnexTabContent>
        </motion.div>
      );
    case "liveActivity":
      return (
        <motion.div key="liveActivity" {...motionProps}>
          <AnnexTabContent tab="liveActivity">
            <LiveActivityPanel />
          </AnnexTabContent>
        </motion.div>
      );
    case "monitor":
      return (
        <motion.div key="monitor" {...motionProps}>
          <AnnexTabContent tab="monitor">
            <Suspense fallback={<TabFallback label={DECK_LOADING_COPY.generic3d} />}>
              <SystemMonitorPanel />
            </Suspense>
          </AnnexTabContent>
        </motion.div>
      );
    case "community":
      return (
        <motion.div key="community" {...motionProps}>
          <AnnexTabContent tab="community">
            <CommunityPanel />
          </AnnexTabContent>
        </motion.div>
      );
    case "hardware":
      return (
        <motion.div key="hardware" {...motionProps}>
          <AnnexTabContent tab="hardware">
            <Suspense fallback={<TabFallback label={DECK_LOADING_COPY.generic3d} />}>
              <HardwareModelPanel />
            </Suspense>
          </AnnexTabContent>
        </motion.div>
      );
    case "admin":
      return (
        <motion.div key="admin" {...motionProps}>
          <AnnexTabContent tab="admin">
            <Suspense fallback={<TabFallback label={DECK_LOADING_COPY.settingsSync} />}>
              <AdminPanel className="p-2" />
            </Suspense>
          </AnnexTabContent>
        </motion.div>
      );
    default:
      return null;
  }
}
