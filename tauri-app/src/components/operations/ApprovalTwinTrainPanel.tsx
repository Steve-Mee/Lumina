import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Brain, Dumbbell, RefreshCw, Shield } from "lucide-react";

import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";
import { DeckMetricTile } from "@/components/cockpit/DeckMetricTile";
import { DeckSection } from "@/components/cockpit/DeckSection";
import { Button } from "@/components/ui/button";
import { selectApiKeyConfigured, useApiKeyStore } from "@/store/apiKeyStore";
import {
  fetchTwinLabels,
  fetchTwinMetrics,
  fetchTwinMode,
  fetchTwinReviewQueueFull,
  formatCalibrationSummary,
  formatConfidenceDistribution,
  formatRollingAgreement,
  formatTwinNum,
  formatTwinPct,
  isModeReady,
  postGymAnswer,
  postTwinLabel,
  postTwinPromote,
  postTwinTrain,
  promotionRatio,
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

function readinessFailReasons(value: unknown): string[] {
  if (!value || typeof value !== "object") return [];
  const rec = value as Record<string, unknown>;
  if (Array.isArray(rec.fail_reasons)) {
    return rec.fail_reasons.map(String).filter(Boolean);
  }
  if (typeof rec.reason === "string" && rec.reason.trim()) {
    return [rec.reason.trim()];
  }
  return [];
}

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

  const mode = String(modeStatus?.mode ?? metrics?.mode ?? "shadow");
  const authority = String(modeStatus?.authority ?? metrics?.authority ?? "—");
  const readiness = modeStatus?.readiness ?? metrics?.mode_readiness ?? null;
  const modeProgress =
    modeStatus?.mode_promotion_progress ?? metrics?.mode_promotion_progress ?? null;
  const assistedProgress = modeProgress?.progress?.assisted;
  const fullAutoProgress = modeProgress?.progress?.full_auto;
  const assistedReady =
    isModeReady(readiness?.assisted) || Boolean(assistedProgress?.ready);
  const fullAutoReady =
    isModeReady(readiness?.full_auto) || Boolean(fullAutoProgress?.ready);
  const assistedReasons =
    readinessFailReasons(readiness?.assisted).length > 0
      ? readinessFailReasons(readiness?.assisted)
      : (assistedProgress?.fail_reasons ?? []).map(String);
  const fullAutoReasons =
    readinessFailReasons(readiness?.full_auto).length > 0
      ? readinessFailReasons(readiness?.full_auto)
      : (fullAutoProgress?.fail_reasons ?? []).map(String);
  const riskTop = metrics?.risk_flag_top ?? {};
  const riskTopEntries = Object.entries(riskTop).slice(0, 6);
  const confLine = formatConfidenceDistribution(metrics?.confidence_distribution);
  const rollingLine = formatRollingAgreement(metrics?.rolling_agreement);
  const calibLine = formatCalibrationSummary(metrics?.calibration);
  const agreementSeries = (metrics?.agreement_over_time ?? []).slice(-5);
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

      {/* ── Metrics ──────────────────────────────────────────────── */}
      <DeckSection title="Twin metrics" icon={Brain}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <DeckMetricTile
            label="vs Steve"
            value={
              metrics?.twin_steve_agreement_pct != null
                ? formatTwinPct(metrics.twin_steve_agreement_pct)
                : "—"
            }
          />
          <DeckMetricTile
            label="Mode agree"
            value={
              metrics?.twin_agreement_pct != null
                ? formatTwinPct(metrics.twin_agreement_pct)
                : "—"
            }
          />
          <DeckMetricTile
            label="Rolling w50"
            value={
              metrics?.rolling_agreement?.w50 != null
                ? formatTwinPct(metrics.rolling_agreement.w50)
                : "—"
            }
          />
          <DeckMetricTile label="Reward" value={formatTwinNum(metrics?.reward)} />
          <DeckMetricTile
            label="Avg error"
            value={formatTwinNum(metrics?.avg_prediction_error)}
          />
          <DeckMetricTile
            label="High-conf agree"
            value={
              metrics?.calibration?.high_conf_agreement_pct != null
                ? formatTwinPct(metrics.calibration.high_conf_agreement_pct)
                : "—"
            }
          />
          <DeckMetricTile
            label="Calib |err|"
            value={formatTwinNum(metrics?.calibration?.mean_abs_calibration_error)}
          />
          <DeckMetricTile
            label="Risk caught"
            value={
              metrics?.risk_flags_caught != null
                ? `${metrics.risk_flags_caught}${
                    metrics.risk_flags_catch_rate_pct != null
                      ? ` (${formatTwinPct(metrics.risk_flags_catch_rate_pct)})`
                      : ""
                  }`
                : "—"
            }
          />
          <DeckMetricTile
            label="Risk missed"
            value={
              metrics?.risk_flags_missed != null
                ? `${metrics.risk_flags_missed}${
                    metrics.risk_flags_missed_pct != null
                      ? ` (${formatTwinPct(metrics.risk_flags_missed_pct)})`
                      : ""
                  }`
                : "—"
            }
          />
          <DeckMetricTile
            label="False + %"
            value={
              metrics?.false_positive_pct != null
                ? formatTwinPct(metrics.false_positive_pct)
                : "—"
            }
          />
          <DeckMetricTile
            label="Steps"
            value={String(metrics?.training_steps ?? "—")}
          />
          <DeckMetricTile
            label="Labels"
            value={String(metrics?.labels_total_recent_cap ?? "—")}
          />
        </div>
        <p className="mt-2 font-mono text-[10px] text-muted-foreground">
          Rolling: {rollingLine}
        </p>
        <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
          Calibration: {calibLine}
        </p>
        <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
          Confidence hist: {confLine}
        </p>
        {agreementSeries.length > 0 ? (
          <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
            Agree over time:{" "}
            {agreementSeries
              .map(
                (p) =>
                  `${p.period ?? "?"} ${
                    p.agreement_pct != null ? formatTwinPct(p.agreement_pct) : "—"
                  }`,
              )
              .join(" · ")}
          </p>
        ) : null}
        {riskTopEntries.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="font-mono text-[9px] tracking-wider text-muted-foreground uppercase">
              Risk flags
            </span>
            {riskTopEntries.map(([flag, count]) => (
              <span
                key={flag}
                className="rounded bg-amber-500/15 px-1.5 py-0.5 font-mono text-[9px] text-amber-100/90"
              >
                {flag}×{count}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-1 text-[10px] text-muted-foreground">
            No risk flags in recent decision window.
          </p>
        )}
        {metrics?.outcome_counts ? (
          <p className="mt-1 font-mono text-[10px] text-muted-foreground">
            Outcomes: auto {metrics.outcome_counts.auto_approved ?? 0} · veto{" "}
            {metrics.outcome_counts.veto ?? 0} · deferred{" "}
            {metrics.outcome_counts.deferred ?? 0} · other{" "}
            {metrics.outcome_counts.other ?? 0}
            {metrics.decisions_total != null
              ? ` · window ${metrics.decisions_total}`
              : ""}
          </p>
        ) : null}
      </DeckSection>

      {/* ── Judgment mode ────────────────────────────────────────── */}
      <DeckSection title="Judgment mode" icon={Shield}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded bg-violet-500/20 px-2 py-0.5 font-mono text-[10px] tracking-wider text-violet-100 uppercase">
            {mode}
          </span>
          <span className="font-mono text-[10px] text-muted-foreground">
            authority: {authority}
          </span>
          <span
            className={cn(
              "rounded px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider",
              assistedReady
                ? "bg-emerald-500/15 text-emerald-200"
                : "bg-muted/40 text-muted-foreground",
            )}
          >
            assisted {assistedReady ? "ready" : "gated"}
          </span>
          <span
            className={cn(
              "rounded px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider",
              fullAutoReady
                ? "bg-emerald-500/15 text-emerald-200"
                : "bg-muted/40 text-muted-foreground",
            )}
          >
            full_auto {fullAutoReady ? "ready" : "gated"}
          </span>
        </div>
        <p className="mt-1.5 text-[10px] text-muted-foreground">
          Promote only when measurable gates pass (agreement, FP rate, constitution, samples).
          Fail-closed — blocked promotions show why.
        </p>
        {assistedProgress || fullAutoProgress ? (
          <div className="mt-2 space-y-1.5">
            {(
              [
                ["assisted", assistedProgress],
                ["full_auto", fullAutoProgress],
              ] as const
            ).map(([label, prog]) => {
              if (!prog) return null;
              const sampleR = promotionRatio(prog.samples);
              const agreeR = promotionRatio(prog.agreement);
              const fpR = promotionRatio(prog.false_positive);
              return (
                <div key={label} className="space-y-0.5">
                  <p className="font-mono text-[9px] tracking-wider text-muted-foreground uppercase">
                    {label} progress · samples {(sampleR * 100).toFixed(0)}% · agree{" "}
                    {(agreeR * 100).toFixed(0)}% · fp room {(fpR * 100).toFixed(0)}%
                  </p>
                  <div className="flex h-1.5 gap-0.5 overflow-hidden rounded bg-muted/40">
                    <div
                      className="bg-violet-400/80 transition-all"
                      style={{ width: `${sampleR * 33.3}%` }}
                      title="samples"
                    />
                    <div
                      className="bg-emerald-400/80 transition-all"
                      style={{ width: `${agreeR * 33.3}%` }}
                      title="agreement"
                    />
                    <div
                      className="bg-cyan-400/70 transition-all"
                      style={{ width: `${fpR * 33.3}%` }}
                      title="fp room"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}
        {!assistedReady && assistedReasons.length > 0 ? (
          <p className="mt-1 font-mono text-[9px] text-amber-200/75">
            assisted gates: {assistedReasons.slice(0, 4).join("; ")}
          </p>
        ) : null}
        {!fullAutoReady && fullAutoReasons.length > 0 ? (
          <p className="mt-0.5 font-mono text-[9px] text-amber-200/75">
            full_auto gates: {fullAutoReasons.slice(0, 4).join("; ")}
          </p>
        ) : null}
        <div className="mt-2 flex flex-wrap gap-2">
          <Button
            type="button"
            size="xs"
            variant="secondary"
            disabled={busyKey !== null || mode === "assisted" || mode === "full_auto"}
            title={
              assistedReady
                ? "Promote to assisted when gates pass"
                : assistedReasons[0] ?? "Gate not ready (still allowed to try — server is SSOT)"
            }
            onClick={() => void handlePromote("assisted")}
          >
            Promote assisted
          </Button>
          <Button
            type="button"
            size="xs"
            variant="secondary"
            disabled={busyKey !== null || mode === "full_auto"}
            title={
              fullAutoReady
                ? "Promote to full_auto when gates pass"
                : fullAutoReasons[0] ?? "Gate not ready (still allowed to try — server is SSOT)"
            }
            onClick={() => void handlePromote("full_auto")}
          >
            Promote full_auto
          </Button>
        </div>
      </DeckSection>

      {/* ── Approval Gym ─────────────────────────────────────────── */}
      <DeckSection title="Approval Gym" icon={Dumbbell}>
        <div className="mb-2 flex items-center gap-2">
          {!gymSession ? (
            <Button
              type="button"
              size="xs"
              className="ml-auto"
              disabled={busyKey !== null}
              onClick={() => void handleStartGym()}
            >
              Start 3–5 drills
            </Button>
          ) : (
            <Button
              type="button"
              size="xs"
              variant="ghost"
              className="ml-auto"
              disabled={busyKey !== null}
              onClick={handleEndGym}
            >
              End gym
            </Button>
          )}
        </div>
        <p className="text-[10px] text-muted-foreground">
          Practice labels only — does not promote DNA or affect REAL gates. Prefer historical
          DNA when available; synthetic drills fill the rest.
        </p>

        {currentDrill ? (
          <article className="lumina-surface-muted mt-2 rounded-lg border border-cyan-500/20 p-3">
            <div className="flex items-center gap-2">
              <p className="font-mono text-[10px] text-cyan-200/90">
                Drill {gymIndex + 1} / {gymSession?.proposals.length ?? 0}
              </p>
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider",
                  currentDrill.source === "historical"
                    ? "bg-violet-500/20 text-violet-200"
                    : "bg-amber-500/15 text-amber-200/90",
                )}
              >
                {currentDrill.source}
              </span>
            </div>
            <p className="mt-1 font-mono text-xs text-violet-100/90">
              {currentDrill.dna_hash.length > 20
                ? `${currentDrill.dna_hash.slice(0, 18)}…`
                : currentDrill.dna_hash}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              est. conf {formatTwinPct(currentDrill.estimated_confidence)}
            </p>
            <p className="mt-2 text-[11px] leading-relaxed text-foreground/85">
              {currentDrill.summary}
            </p>

            {gymModifyOpen ? (
              <div className="mt-2 space-y-2">
                <textarea
                  className="min-h-[56px] w-full rounded-md border border-border/60 bg-background/40 p-2 text-[11px]"
                  placeholder="How should this have been decided?"
                  value={gymNotes}
                  onChange={(e) => setGymNotes(e.target.value)}
                />
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="xs"
                    disabled={busyKey !== null}
                    onClick={() => void submitGymAnswer(currentDrill, "modify")}
                  >
                    Submit modify
                  </Button>
                  <Button
                    type="button"
                    size="xs"
                    variant="ghost"
                    onClick={() => {
                      setGymModifyOpen(false);
                      setGymNotes("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="xs"
                  disabled={busyKey !== null}
                  onClick={() => void submitGymAnswer(currentDrill, "approve")}
                >
                  Approve
                </Button>
                <Button
                  type="button"
                  size="xs"
                  variant="secondary"
                  disabled={busyKey !== null}
                  onClick={() => void submitGymAnswer(currentDrill, "reject")}
                >
                  Veto
                </Button>
                <Button
                  type="button"
                  size="xs"
                  variant="ghost"
                  disabled={busyKey !== null}
                  onClick={() => setGymModifyOpen(true)}
                >
                  Modify…
                </Button>
              </div>
            )}
          </article>
        ) : null}
      </DeckSection>

      {/* ── Review queue ─────────────────────────────────────────── */}
      <DeckSection title="Review queue">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <label className="flex cursor-pointer items-center gap-1.5 font-mono text-[10px] text-muted-foreground">
            <input
              type="checkbox"
              className="size-3 rounded border-border"
              checked={includeLabeled}
              onChange={(e) => {
                setLoading(true);
                setIncludeLabeled(e.target.checked);
              }}
            />
            Show already labeled
          </label>
          {highStakesCount > 0 ? (
            <span className="font-mono text-[10px] text-amber-200/80">
              {highStakesCount} high-stakes in view
            </span>
          ) : null}
        </div>
        <p className="mb-2 text-[10px] text-muted-foreground">
          High-stakes first (risk flags or score below 80%). Label as Steve would; optional
          feedback notes train nuance. Already-labeled DNA is hidden by default.
        </p>
        {loading && queue.length === 0 ? (
          <p className="text-xs text-muted-foreground">Loading decisions…</p>
        ) : null}
        {!loading && queue.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No unlabeled twin decisions. Run birth/evolution activity, or use{" "}
            <span className="text-cyan-200/90">Approval Gym</span> above to train with drills.
          </p>
        ) : null}
        {queue.map((item, idx) => {
          const dna = String(item.dna_hash ?? `row-${idx}`);
          const score = twinScoreOf(item);
          const isMod = activeModify === dna;
          const isHighStakes =
            item.stakes === "high" ||
            (Array.isArray(item.risk_flags) && item.risk_flags.length > 0) ||
            (score != null && score < 0.8);
          const isRoutine = !isHighStakes;
          return (
            <article
              key={`${dna}-${idx}`}
              className={cn(
                "lumina-surface-muted mb-2 rounded-lg p-3",
                isHighStakes && "border border-amber-500/35",
                isRoutine && "opacity-90",
                item.already_labeled && "border border-border/50",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-mono text-xs text-violet-100/90">
                  {dna.length > 18 ? `${dna.slice(0, 16)}…` : dna}
                </p>
                {isHighStakes ? (
                  <span className="rounded bg-amber-500/20 px-1.5 py-0.5 font-mono text-[9px] tracking-wider text-amber-100 uppercase">
                    High stakes
                  </span>
                ) : (
                  <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 font-mono text-[9px] tracking-wider text-emerald-200/80 uppercase">
                    Routine
                  </span>
                )}
                {item.already_labeled ? (
                  <span className="rounded bg-muted/50 px-1.5 py-0.5 font-mono text-[9px] tracking-wider text-muted-foreground uppercase">
                    Labeled
                  </span>
                ) : null}
                {item.outcome ? (
                  <span className="font-mono text-[9px] text-muted-foreground">
                    outcome: {String(item.outcome)}
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                score {score != null ? formatTwinPct(score) : "—"} · rec={" "}
                {String(item.recommendation ?? "—")}
                {item.timestamp
                  ? ` · ${String(item.timestamp).slice(0, 19)}`
                  : ""}
              </p>
              {Array.isArray(item.risk_flags) && item.risk_flags.length > 0 ? (
                <p className="mt-0.5 font-mono text-[10px] text-amber-200/80">
                  risks: {item.risk_flags.map(String).join(", ")}
                </p>
              ) : null}
              {item.explanation ? (
                <p className="mt-1 text-[11px] leading-relaxed text-foreground/80">
                  {String(item.explanation)}
                </p>
              ) : null}

              {isMod ? (
                <div className="mt-2 space-y-2">
                  <textarea
                    className="min-h-[56px] w-full rounded-md border border-border/60 bg-background/40 p-2 text-[11px]"
                    placeholder="How should this have been decided? (size, risk, veto reason…)"
                    value={modifyNotes[dna] ?? ""}
                    onChange={(e) =>
                      setModifyNotes((prev) => ({ ...prev, [dna]: e.target.value }))
                    }
                  />
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      size="xs"
                      disabled={busyKey !== null}
                      onClick={() => void submitLabel(item, "modify")}
                    >
                      Submit modify
                    </Button>
                    <Button
                      type="button"
                      size="xs"
                      variant="ghost"
                      onClick={() => setActiveModify(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="mt-2 space-y-2">
                  <input
                    type="text"
                    className="w-full rounded-md border border-border/50 bg-background/30 px-2 py-1 text-[11px]"
                    placeholder="Optional feedback note (approve/veto)"
                    value={feedbackNotes[dna] ?? ""}
                    onChange={(e) =>
                      setFeedbackNotes((prev) => ({ ...prev, [dna]: e.target.value }))
                    }
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="xs"
                      disabled={busyKey !== null}
                      onClick={() => void submitLabel(item, "approve")}
                    >
                      Approve
                    </Button>
                    <Button
                      type="button"
                      size="xs"
                      variant="secondary"
                      disabled={busyKey !== null}
                      onClick={() => void submitLabel(item, "reject")}
                    >
                      Veto
                    </Button>
                    <Button
                      type="button"
                      size="xs"
                      variant="ghost"
                      disabled={busyKey !== null}
                      onClick={() => setActiveModify(dna)}
                    >
                      Modify…
                    </Button>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </DeckSection>

      {/* ── Label history ────────────────────────────────────────── */}
      <DeckSection title="Label history (local audit)">
        {labels.length === 0 ? (
          <p className="text-xs text-muted-foreground">No Steve labels yet.</p>
        ) : (
          <ul className="space-y-1.5">
            {labels.map((row, idx) => (
              <li
                key={`${row.timestamp}-${row.context_dna_hash}-${idx}`}
                className="rounded-md border border-border/40 px-2 py-1.5 font-mono text-[10px] text-muted-foreground"
              >
                <div className="flex flex-wrap gap-x-2">
                  <span className="text-violet-200/90">{row.steve_antwoord}</span>
                  <span>
                    {row.context_dna_hash.length > 14
                      ? `${row.context_dna_hash.slice(0, 12)}…`
                      : row.context_dna_hash}
                  </span>
                  <span>conf {formatTwinNum(row.confidence_score, 2)}</span>
                  <span>{row.timestamp.slice(0, 19)}</span>
                </div>
                {row.vraag ? (
                  <p className="mt-0.5 line-clamp-2 text-[9px] text-muted-foreground/80">
                    {row.vraag}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </DeckSection>
    </div>
  );
}
