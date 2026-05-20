import { motion } from "framer-motion";

import { useMemo } from "react";



import { DecisionTheaterStage } from "@/components/decision/DecisionTheaterStage";

import { DecisionTheaterStatusHero } from "@/components/decision/DecisionTheaterStatusHero";

import { ReasoningSpine } from "@/components/decision/ReasoningSpine";

import { useAdaptiveIntelligenceContext } from "@/context/AdaptiveIntelligenceContext";

import { useLiveTrading } from "@/hooks/useLiveTrading";

import { useModeMotion } from "@/hooks/useModeMotion";

import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { panelCrossfadeWith, transitionOrNone } from "@/lib/motionPresets";

import { isCommandDeckBlocked } from "@/lib/commandDeckGuard";
import { deriveDecisionBrief, type DecisionBrief } from "@/lib/decisionTheaterModel";

import { cn } from "@/lib/utils";

import {

  selectConnectionStatus,

  selectCurrentMode,

  selectEvolutionState,

  selectLiveMetrics,

  selectRiskLevel,

  selectSafeModeActive,

  selectTradingLive,

  useCoreStore,

} from "@/store/coreStore";

import {

  selectVisualQuality,

  useVisualSettingsStore,

} from "@/store/visualSettingsStore";



interface DecisionTheaterProps {

  className?: string;

  brief?: DecisionBrief;

}



export function DecisionTheater({ className, brief: briefOverride }: DecisionTheaterProps) {

  const currentMode = useCoreStore(selectCurrentMode);

  const connectionStatus = useCoreStore(selectConnectionStatus);

  const safeModeActive = useCoreStore(selectSafeModeActive);

  const liveMetrics = useCoreStore(selectLiveMetrics);

  const riskLevel = useCoreStore(selectRiskLevel);

  const evolutionState = useCoreStore(selectEvolutionState);

  const tradingLive = useCoreStore(selectTradingLive);

  const { healthSnapshot } = useAdaptiveIntelligenceContext();

  const { trades } = useLiveTrading();

  const reducedMotion = usePrefersReducedMotion();

  const visualQuality = useVisualSettingsStore(selectVisualQuality);

  const lowQuality = visualQuality === "low";

  const modeMotion = useModeMotion();



  const brief = useMemo(() => {

    if (briefOverride) {

      return briefOverride;

    }

    return deriveDecisionBrief({

      ...useCoreStore.getState(),

      operatorMode: currentMode,

      liveMetrics,

      riskLevel,

      evolutionState,

      tradingLive,

    });

  }, [briefOverride, currentMode, liveMetrics, riskLevel, evolutionState, tradingLive]);



  const deckBlocked = isCommandDeckBlocked({

    ...useCoreStore.getState(),

    operatorMode: currentMode,

    safeModeActive,

  });



  const hasLiveData =

    trades.length > 0 ||

    Boolean(tradingLive?.active_signal) ||

    Boolean(tradingLive?.current_dream) ||

    brief.steps.length > 0;



  const statusHeroVisible =

    connectionStatus === "connecting" ||

    connectionStatus === "reconnecting" ||

    (connectionStatus === "disconnected" && !hasLiveData) ||

    (connectionStatus === "disconnected" && hasLiveData);



  const motionReduced = reducedMotion || lowQuality;



  return (

    <div

      data-mode={currentMode}

      className={cn("decision-theater-shell decision-theater-shell--immersive flex h-full min-h-[320px] flex-col", className)}

      aria-label={`Decision theater — ${brief.steps.length} reasoning steps`}

    >

      {statusHeroVisible ? (

        <DecisionTheaterStatusHero

          connectionStatus={connectionStatus}

          hasLiveData={hasLiveData}

          mode={currentMode}

          className="mx-3 mt-3 shrink-0"

        />

      ) : null}



      <motion.div

        className="decision-theater-layout min-h-0 flex-1"

        variants={panelCrossfadeWith(modeMotion)}

        initial={motionReduced ? false : "hidden"}

        animate="visible"

        transition={transitionOrNone(motionReduced, modeMotion)}

      >

        <ReasoningSpine steps={brief.steps} mode={currentMode} motionReduced={motionReduced} />

        <DecisionTheaterStage

          brief={brief}

          trading={tradingLive}

          trades={trades}

          currentMode={currentMode}

          riskLevel={riskLevel}

          killSwitchActive={Boolean(healthSnapshot?.kill_switch_active)}

          deckBlocked={deckBlocked}

          motionReduced={motionReduced}

        />

      </motion.div>

    </div>

  );

}


