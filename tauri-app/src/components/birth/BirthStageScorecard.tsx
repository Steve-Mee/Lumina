import type { BirthProgressPayload } from "@/lib/birthClient";
import {
  extractStageScorecard,
  shouldShowBirthAttentionBanner,
} from "@/lib/birthPhaseModel";
import { cn } from "@/lib/utils";
import { useBirthStore } from "@/store/birthStore";

import {
  formatMetricValue,
  showAdaptationHud,
} from "@/components/birth/BirthStageScorecardFormat";
import {
  EvolutionTabFields,
  RecoveryTabFields,
  StageTabFields,
} from "@/components/birth/BirthStageScorecardTabs";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface BirthStageScorecardProps {
  progress: BirthProgressPayload | undefined;
  birthStatus?: string;
  birthRunning?: boolean;
  resumePlateauRisk?: boolean;
  resumePlateauRiskTrades?: number | null;
  variant?: "default" | "compact";
  className?: string;
}

export function BirthStageScorecard({
  progress,
  birthStatus,
  birthRunning = false,
  resumePlateauRisk = false,
  resumePlateauRiskTrades = null,
  variant = "default",
  className,
}: BirthStageScorecardProps) {
  const scorecard = extractStageScorecard(progress);
  if (!scorecard) return null;

  const compact = variant === "compact";

  if (compact) {
    return (
      <p
        className={cn(
          "birth-stage-scorecard-compact font-mono text-[11px] text-cyan-200/85",
          className,
        )}
      >
        {scorecard.stageLabel} | {scorecard.tradesDone}/{scorecard.tradesRequired} trades
        {scorecard.metricValue != null
          ? ` | ${scorecard.metricLabel} ${formatMetricValue(scorecard)}`
          : ""}
        {scorecard.learningAttempt > 0 ? ` | attempt ${scorecard.learningAttempt}` : ""}
        {scorecard.patternsMined > 0
          ? ` | ${scorecard.patternsMined.toLocaleString()} patterns`
          : ""}
        {scorecard.explorationActive ? " | explore" : ""}
        {scorecard.stageWallRemainingSec != null
          ? ` | wall ${Math.ceil(scorecard.stageWallRemainingSec / 60)}m`
          : ""}
        {showAdaptationHud(scorecard) && scorecard.volumeGateStatus
          ? ` | gate ${scorecard.volumeGateStatus}`
          : ""}
        {scorecard.retriesThisStage > 0 ? ` | adapt ${scorecard.retriesThisStage}` : ""}
      </p>
    );
  }

  const attention = shouldShowBirthAttentionBanner(progress, {
    birthRunning,
    birthStatus,
  });
  const acceptChampion = useBirthStore((s) => s.acceptChampion);
  const wipeBirthData = useBirthStore((s) => s.wipeBirthData);
  const actions = Array.isArray(progress?.attention_recommended_actions)
    ? progress.attention_recommended_actions.map((a) => String(a))
    : [];
  const showAccept = actions.includes("accept_champion") || actions.includes("resume_champion");
  const showWipe = actions.includes("wipe_and_retry");
  const defaultTab =
    scorecard.adaptationCycling ||
    (scorecard.stallRemediationCycle != null && scorecard.stallRemediationCycle > 0)
      ? "recovery"
      : scorecard.evolutionPhase && scorecard.evolutionPhase !== "none"
        ? "evolution"
        : "stage";

  return (
    <div className={cn("birth-stage-scorecard flex min-h-0 flex-1 flex-col", className)}>
      {attention ? (
        <div className="risk-envelope-banner risk-envelope-banner--info mx-0 mb-2 shrink-0 space-y-2">
          <p className="text-[11px] leading-relaxed">
            <strong className="text-violet-200/90">Attention required:</strong>{" "}
            {String(progress?.attention_summary ?? "Lumina needs operator review.")}
          </p>
          {showAccept || showWipe ? (
            <div className="flex flex-wrap gap-2">
              {showAccept ? (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  className="h-7 text-[11px]"
                  onClick={() => void acceptChampion()}
                >
                  Accept champion
                </Button>
              ) : null}
              {showWipe ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 text-[11px]"
                  onClick={() => void wipeBirthData({ preserveTickCache: true })}
                >
                  Wipe &amp; retry
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      <Tabs defaultValue={defaultTab} className="risk-envelope-tabs birth-stage-scorecard__tabs min-h-0 flex-1">
        <TabsList className="risk-envelope-tab-list risk-envelope-tab-list--3 w-full shrink-0">
          <TabsTrigger value="stage">Stage</TabsTrigger>
          <TabsTrigger value="recovery">Recovery</TabsTrigger>
          <TabsTrigger value="evolution">Evolution</TabsTrigger>
        </TabsList>

        <div className="risk-envelope-tab-body birth-stage-scorecard__tab-body min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
          <TabsContent value="stage" className="risk-envelope-tab-content mt-0">
            <StageTabFields scorecard={scorecard} progress={progress} />
          </TabsContent>
          <TabsContent value="recovery" className="risk-envelope-tab-content mt-0">
            <RecoveryTabFields
              scorecard={scorecard}
              resumePlateauRisk={resumePlateauRisk}
              resumePlateauRiskTrades={resumePlateauRiskTrades}
            />
          </TabsContent>
          <TabsContent value="evolution" className="risk-envelope-tab-content mt-0">
            <EvolutionTabFields scorecard={scorecard} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
