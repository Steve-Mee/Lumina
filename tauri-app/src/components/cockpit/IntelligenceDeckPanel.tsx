import { ChevronDown } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";

import { AdaptiveIntelligenceHistoryPanel } from "@/components/intelligence/AdaptiveIntelligenceHistoryPanel";
import { AdaptiveIntelligenceRecentEvents } from "@/components/intelligence/AdaptiveIntelligenceRecentEvents";
import { AdaptiveIntelligenceStatusCard } from "@/components/intelligence/AdaptiveIntelligenceStatusCard";
import { SystemMonitorPanel } from "@/components/intelligence/SystemMonitorPanel";
import { AdminPanel } from "@/components/operations/AdminPanel";
import { CommunityPanel } from "@/components/operations/CommunityPanel";
import { EvolutionApprovalsPanel } from "@/components/operations/EvolutionApprovalsPanel";
import { HardwareModelPanel } from "@/components/operations/HardwareModelPanel";
import { LiveActivityPanel } from "@/components/operations/LiveActivityPanel";
import { RealOperationsPanel } from "@/components/operations/RealOperationsPanel";
import { TradingPerformancePanel } from "@/components/performance/TradingPerformancePanel";
import { DecisionTheater } from "@/components/DecisionTheater";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { springSoft, transitionOrNone } from "@/lib/motionPresets";
import {
  selectActiveRightTab,
  useDeckPanelStore,
  type RightDeckTab,
} from "@/store/deckPanelStore";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";

export const INTELLIGENCE_DECK_TAB_SUBTITLES: Record<RightDeckTab, string> = {
  brief: "Decision theater & reasoning chain",
  adaptive: "Live policy stack & transition history",
  performance: "Equity curve, P&L & session KPIs",
  realOps: "REAL capital preservation & exposure",
  evolutionApprovals: "Open challenger proposals",
  liveActivity: "Engine status & log tail",
  monitor: "Health, twin, shadow & training metrics",
  community: "Trader league & global wisdom",
  hardware: "Hardware tier & model management",
  admin: "Maintenance & first-boot reset",
};

const PRIMARY_TABS: RightDeckTab[] = ["brief", "performance", "monitor", "liveActivity"];

interface MoreTabOption {
  value: RightDeckTab;
  label: string;
}

interface IntelligenceDeckPanelProps {
  className?: string;
}

export function IntelligenceDeckPanel({ className }: IntelligenceDeckPanelProps) {
  const reducedMotion = usePrefersReducedMotion();
  const activeRightTab = useDeckPanelStore(selectActiveRightTab);
  const setActiveRightTab = useDeckPanelStore((state) => state.setActiveRightTab);
  const hydrateRightTab = useDeckPanelStore((state) => state.hydrateRightTab);
  const operatorMode = useCoreStore(selectCurrentMode);
  const isReal = operatorMode === "REAL";
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  const moreTabs = useMemo((): MoreTabOption[] => {
    const tabs: MoreTabOption[] = [
      { value: "adaptive", label: "Adaptive" },
      { value: "evolutionApprovals", label: "Evolution" },
      { value: "community", label: "Community" },
      { value: "hardware", label: "Hardware" },
      { value: "admin", label: "Admin" },
    ];
    if (isReal) {
      tabs.unshift({ value: "realOps", label: "REAL Ops" });
    }
    return tabs;
  }, [isReal]);

  const isMoreTabActive = moreTabs.some((tab) => tab.value === activeRightTab);
  const activeMoreLabel =
    moreTabs.find((tab) => tab.value === activeRightTab)?.label ?? "More";

  useEffect(() => {
    hydrateRightTab();
  }, [hydrateRightTab]);

  useEffect(() => {
    if (!moreOpen) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(event.target as Node)) {
        setMoreOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [moreOpen]);

  return (
    <div
      data-tour="intelligence-deck"
      className={cn(
        "cockpit-panel flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-white/10 py-0",
        className,
      )}
    >
      <Tabs
        value={activeRightTab}
        onValueChange={(value) => setActiveRightTab(value as RightDeckTab)}
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
                Intelligence
              </h2>
              <p className="font-mono text-[11px] text-muted-foreground/80">
                {INTELLIGENCE_DECK_TAB_SUBTITLES[activeRightTab]}
              </p>
            </div>
            <div className="flex max-w-full flex-wrap items-center gap-1">
              <TabsList className="max-w-full flex-wrap justify-end">
                {PRIMARY_TABS.map((tab) => (
                  <TabsTrigger key={tab} value={tab}>
                    {tab === "liveActivity" ? "Activity" : tab === "brief" ? "Brief" : tab.charAt(0).toUpperCase() + tab.slice(1)}
                  </TabsTrigger>
                ))}
              </TabsList>
              <div ref={moreRef} className="relative">
                <button
                  type="button"
                  onClick={() => setMoreOpen((open) => !open)}
                  className={cn(
                    "inline-flex h-8 items-center gap-1 rounded-md border px-2.5 font-mono text-[10px] tracking-wide uppercase transition-colors",
                    isMoreTabActive
                      ? "border-cyan-400/40 bg-cyan-500/10 text-cyan-200"
                      : "border-white/10 bg-black/20 text-muted-foreground hover:border-white/20 hover:text-foreground",
                  )}
                >
                  {isMoreTabActive ? activeMoreLabel : "More"}
                  <ChevronDown className={cn("size-3 transition-transform", moreOpen && "rotate-180")} />
                </button>
                {moreOpen ? (
                  <div className="absolute right-0 top-full z-30 mt-1 min-w-[140px] rounded-md border border-white/10 bg-black/95 py-1 shadow-xl">
                    {moreTabs.map((tab) => (
                      <button
                        key={tab.value}
                        type="button"
                        className={cn(
                          "block w-full px-3 py-1.5 text-left font-mono text-[10px] tracking-wide uppercase transition-colors hover:bg-white/5",
                          activeRightTab === tab.value ? "text-cyan-200" : "text-muted-foreground",
                        )}
                        onClick={() => {
                          setActiveRightTab(tab.value);
                          setMoreOpen(false);
                        }}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        <TabsContent value="brief" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <DecisionTheater className="h-full min-h-[280px] w-full" />
        </TabsContent>

        <TabsContent value="adaptive" className="mt-0 flex min-h-0 flex-1 flex-col p-0">
          <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-2 [scrollbar-width:thin]">
            <AdaptiveIntelligenceStatusCard />
            <AdaptiveIntelligenceRecentEvents />
            <div className="min-h-[180px] flex-1">
              <AdaptiveIntelligenceHistoryPanel className="h-full" />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="performance" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <TradingPerformancePanel className="h-full min-h-[280px]" />
        </TabsContent>

        {isReal ? (
          <TabsContent value="realOps" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
            <RealOperationsPanel className="h-full min-h-[200px]" />
          </TabsContent>
        ) : null}

        <TabsContent value="evolutionApprovals" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <EvolutionApprovalsPanel className="h-full min-h-[200px]" />
        </TabsContent>

        <TabsContent value="liveActivity" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <LiveActivityPanel className="h-full min-h-[200px]" />
        </TabsContent>

        <TabsContent value="monitor" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <div className="h-full min-h-0 overflow-y-auto pr-1 [scrollbar-width:thin]">
            <SystemMonitorPanel />
          </div>
        </TabsContent>

        <TabsContent value="community" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <CommunityPanel className="h-full min-h-[200px]" />
        </TabsContent>

        <TabsContent value="hardware" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <HardwareModelPanel className="h-full min-h-[200px]" />
        </TabsContent>

        <TabsContent value="admin" className="mt-0 flex min-h-0 flex-1 flex-col p-2">
          <AdminPanel className="h-full min-h-[200px]" />
        </TabsContent>
      </Tabs>
    </div>
  );
}
