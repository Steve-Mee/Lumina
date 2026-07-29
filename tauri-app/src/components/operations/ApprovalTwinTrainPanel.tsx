import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Brain, RefreshCw } from "lucide-react";

import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";
import { TwinTrainGymSection } from "@/components/operations/TwinTrainGymSection";
import { TwinTrainHistorySection } from "@/components/operations/TwinTrainHistorySection";
import { TwinTrainMetricsSection } from "@/components/operations/TwinTrainMetricsSection";
import { TwinTrainModeSection } from "@/components/operations/TwinTrainModeSection";
import { TwinTrainReviewSection } from "@/components/operations/TwinTrainReviewSection";
import { Button } from "@/components/ui/button";
import { selectApiKeyConfigured, useApiKeyStore } from "@/store/apiKeyStore";
import {
  fetchTwinLabels,
  fetchTwinMetrics,
  fetchTwinMode,
  fetchTwinReviewQueueFull,
  postGymAnswer,
  postTwinLabel,
  postTwinPromote,
  postTwinTrain,
  startGymSession,
  twinScoreOf,
  type GymProposal,
  type GymSession,
  type TwinDecision,
  type TwinLabelRecord,
  type TwinMetrics,
  type TwinModeStatus,
  type TwinModeTarget,
  type TwinReviewItem,
} from "@/lib/twinClient";
import { cn } from "@/lib/utils";

export function ApprovalTwinTrainPanel({ className }: { className?: string }) {
  const apiKeyConfigured = useApiKeyStore(selectApiKeyConfigured);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<TwinMetrics | null>(null);
  const [modeStatus, setModeStatus] = useState<TwinModeStatus | null>(null);
  const [queue, setQueue] = useState<TwinReviewItem[]>([]);
  const [highStakesCount, setHighStakesCount] = useState(0);
  const [labels, setLabels] = useState<TwinLabelRecord[]>([]);
  const [includeLabeled, setIncludeLabeled] = useState(false);
  const [modifyNotes, setModifyNotes] = useState<Record<string, string>>({});
  const [activeModify, setActiveModify] = useState<string | null>(null);
  const [feedbackNotes, setFeedbackNotes] = useState<Record<string, string>>({});

  // Approval Gym (practice drills — does not promote DNA)
  const [gymSession, setGymSession] = useState<GymSession | null>(null);
  const [gymIndex, setGymIndex] = useState(0);
  const [gymModifyOpen, setGymModifyOpen] = useState(false);
  const [gymNotes, setGymNotes] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [m, mode, q, l] = await Promise.all([
        fetchTwinMetrics(),
        fetchTwinMode().catch(() => null),
        fetchTwinReviewQueueFull(15, { includeLabeled }),
        fetchTwinLabels(25),
      ]);
      setMetrics(m);
      setModeStatus(mode);
      setQueue(q.items);
      setHighStakesCount(q.high_stakes_count ?? 0);
      setLabels(l);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load Twin training data");
    } finally {
      setLoading(false);
    }
  }, [includeLabeled]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const submitLabel = async (item: TwinReviewItem, decision: TwinDecision) => {
    const dna = String(item.dna_hash ?? "").trim();
    if (!dna) {
      toast.error("Missing dna_hash on decision");
      return;
    }
    const key = `${dna}:${decision}`;
    setBusyKey(key);
    try {
      const notes =
        decision === "modify"
          ? (modifyNotes[dna] ?? "").trim()
          : (feedbackNotes[dna] ?? "").trim();
      const score = twinScoreOf(item);
      await postTwinLabel({
        decision,
        dna_hash: dna,
        notes,
        twin_score: score,
        twin_recommendation:
          typeof item.recommendation === "boolean" ? item.recommendation : null,
        explanation: String(item.explanation ?? ""),
        risk_flags: Array.isArray(item.risk_flags)
          ? item.risk_flags.map(String)
          : [],
        train_now: true,
      });
      const verb =
        decision === "reject" ? "VETO" : decision === "approve" ? "APPROVE" : "MODIFY";
      toast.success(`Recorded ${verb} — light RLHF applied locally`);
      setActiveModify(null);
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Label failed");
    } finally {
      setBusyKey(null);
    }
  };

  const handleTrain = async () => {
    setBusyKey("train");
    try {
      const res = await postTwinTrain(250);
      const steps = res.metrics?.training_steps ?? metrics?.training_steps;
      toast.success(
        steps != null
          ? `Twin retrained from local registry (steps: ${steps})`
          : "Twin retrained from local SteveValues registry",
      );
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Train failed");
    } finally {
      setBusyKey(null);
    }
  };

  const handlePromote = async (target: TwinModeTarget) => {
    setBusyKey(`promote:${target}`);
    try {
      const res = await postTwinPromote(target);
      toast.success(
        res.mode
          ? `Twin mode promoted to ${res.mode}`
          : `Twin mode promote → ${target} accepted`,
      );
      await refresh();
    } catch (err) {
      toast.error(
        err instanceof Error
          ? err.message
          : `Promote to ${target} blocked by gate (fail-closed)`,
      );
    } finally {
      setBusyKey(null);
    }
  };

  const handleStartGym = async () => {
    setBusyKey("gym-start");
    try {
      const session = await startGymSession({ count: 4, prefer_historical: true });
      setGymSession(session);
      setGymIndex(0);
      setGymModifyOpen(false);
      setGymNotes("");
      toast.success(
        `Gym started: ${session.count} drills (${session.historical_count ?? 0} historical / ${session.synthetic_count ?? 0} synthetic)`,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gym start failed");
    } finally {
      setBusyKey(null);
    }
  };

  const handleEndGym = () => {
    setGymSession(null);
    setGymIndex(0);
    setGymModifyOpen(false);
    setGymNotes("");
  };

  const submitGymAnswer = async (proposal: GymProposal, decision: TwinDecision) => {
    if (!gymSession) return;
    setBusyKey(`gym:${proposal.dna_hash}:${decision}`);
    try {
      const notes = decision === "modify" ? gymNotes.trim() : "";
      await postGymAnswer({
        decision,
        dna_hash: proposal.dna_hash,
        summary: proposal.summary,
        estimated_confidence: proposal.estimated_confidence,
        notes,
        session_id: gymSession.session_id,
        train_now: true,
      });
      const verb =
        decision === "reject" ? "VETO" : decision === "approve" ? "APPROVE" : "MODIFY";
      toast.success(`Gym ${verb} recorded (practice only)`);
      setGymModifyOpen(false);
      setGymNotes("");
      const next = gymIndex + 1;
      if (next >= gymSession.proposals.length) {
        toast.success("Gym session complete");
        handleEndGym();
      } else {
        setGymIndex(next);
      }
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gym answer failed");
    } finally {
      setBusyKey(null);
    }
  };

  if (!apiKeyConfigured) {
    return <ApiKeySetupCallout className={className} />;
  }

  const currentDrill: GymProposal | null =
    gymSession && gymSession.proposals[gymIndex] ? gymSession.proposals[gymIndex] : null;

  const localOnly = metrics?.local_only !== false;

  return (
    <div className={cn("space-y-4 overflow-y-auto p-1", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <Brain className="size-4 text-violet-300/90" />
        <h3 className="font-mono text-[11px] tracking-[0.14em] text-violet-200/90 uppercase">
          Approval Twin train
        </h3>
        {localOnly ? (
          <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[9px] tracking-wider text-emerald-200/90 uppercase">
            Local only
          </span>
        ) : null}
        <Button
          type="button"
          size="xs"
          variant="ghost"
          className="ml-auto"
          disabled={busyKey !== null}
          onClick={() => void refresh()}
        >
          <RefreshCw className="mr-1 size-3" />
          Refresh
        </Button>
        <Button
          type="button"
          size="xs"
          variant="secondary"
          disabled={busyKey !== null}
          onClick={() => void handleTrain()}
        >
          Train from registry
        </Button>
      </div>

      <p className="text-[10px] leading-relaxed text-muted-foreground">
        Review Twin decisions, label as you would (approve / veto / modify), and retrain the
        local model. Data stays on disk (SteveValues registry + twin model). Twin judgment never
        bypasses constitution, shadow aperture, or REAL PromotionGate.
      </p>

      <TwinTrainMetricsSection metrics={metrics} />

      <TwinTrainModeSection
        metrics={metrics}
        modeStatus={modeStatus}
        busyKey={busyKey}
        onPromote={(target) => void handlePromote(target)}
      />

      <TwinTrainGymSection
        gymSession={gymSession}
        gymIndex={gymIndex}
        currentDrill={currentDrill}
        gymModifyOpen={gymModifyOpen}
        gymNotes={gymNotes}
        busyKey={busyKey}
        onStartGym={() => void handleStartGym()}
        onEndGym={handleEndGym}
        onGymNotesChange={setGymNotes}
        onGymModifyOpenChange={setGymModifyOpen}
        onSubmitGymAnswer={(proposal, decision) => void submitGymAnswer(proposal, decision)}
      />

      <TwinTrainReviewSection
        loading={loading}
        queue={queue}
        highStakesCount={highStakesCount}
        includeLabeled={includeLabeled}
        busyKey={busyKey}
        activeModify={activeModify}
        modifyNotes={modifyNotes}
        feedbackNotes={feedbackNotes}
        onIncludeLabeledChange={(checked) => {
          setLoading(true);
          setIncludeLabeled(checked);
        }}
        onActiveModifyChange={setActiveModify}
        onModifyNotesChange={(dna, notes) =>
          setModifyNotes((prev) => ({ ...prev, [dna]: notes }))
        }
        onFeedbackNotesChange={(dna, notes) =>
          setFeedbackNotes((prev) => ({ ...prev, [dna]: notes }))
        }
        onSubmitLabel={(item, decision) => void submitLabel(item, decision)}
      />

      <TwinTrainHistorySection labels={labels} />
    </div>
  );
}
