import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Brain, Dumbbell, RefreshCw } from "lucide-react";

import { ApiKeySetupCallout } from "@/components/cockpit/ApiKeySetupCallout";
import { Button } from "@/components/ui/button";
import { selectApiKeyConfigured, useApiKeyStore } from "@/store/apiKeyStore";
import {
  fetchTwinLabels,
  fetchTwinMetrics,
  fetchTwinReviewQueue,
  postGymAnswer,
  postTwinLabel,
  postTwinTrain,
  startGymSession,
  twinScoreOf,
  type GymProposal,
  type GymSession,
  type TwinDecision,
  type TwinLabelRecord,
  type TwinMetrics,
  type TwinReviewItem,
} from "@/lib/twinClient";
import { cn } from "@/lib/utils";

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  if (n <= 1.5) return `${(n * 100).toFixed(1)}%`;
  return `${n.toFixed(1)}%`;
}

function fmtNum(v: number | null | undefined, digits = 3): string {
  if (v == null || Number.isNaN(Number(v))) return "—";
  return Number(v).toFixed(digits);
}

export function ApprovalTwinTrainPanel({ className }: { className?: string }) {
  const apiKeyConfigured = useApiKeyStore(selectApiKeyConfigured);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<TwinMetrics | null>(null);
  const [queue, setQueue] = useState<TwinReviewItem[]>([]);
  const [labels, setLabels] = useState<TwinLabelRecord[]>([]);
  const [modifyNotes, setModifyNotes] = useState<Record<string, string>>({});
  const [activeModify, setActiveModify] = useState<string | null>(null);

  // Approval Gym (practice drills — does not promote DNA)
  const [gymSession, setGymSession] = useState<GymSession | null>(null);
  const [gymIndex, setGymIndex] = useState(0);
  const [gymModifyOpen, setGymModifyOpen] = useState(false);
  const [gymNotes, setGymNotes] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [m, q, l] = await Promise.all([
        fetchTwinMetrics(),
        fetchTwinReviewQueue(15),
        fetchTwinLabels(25),
      ]);
      setMetrics(m);
      setQueue(q);
      setLabels(l);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load Twin training data");
    } finally {
      setLoading(false);
    }
  }, []);

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
      const notes = decision === "modify" ? (modifyNotes[dna] ?? "").trim() : "";
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
      toast.success(`Recorded ${decision.toUpperCase()} — light RLHF applied locally`);
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
      await postTwinTrain(250);
      toast.success("Twin retrained from local SteveValues registry");
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Train failed");
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
      toast.success(`Gym ${decision.toUpperCase()} recorded (practice only)`);
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

  return (
    <div className={cn("space-y-4 overflow-y-auto p-1", className)}>
      <div className="flex items-center gap-2">
        <Brain className="size-4 text-violet-300/90" />
        <h3 className="font-mono text-[11px] tracking-[0.14em] text-violet-200/90 uppercase">
          Approval Twin train
        </h3>
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
        Label past Twin decisions so the local model learns your risk style. Data stays on disk
        (SteveValues registry + twin model). Twin only covers routine high-conf judgment —
        constitution, shadow aperture, and REAL PromotionGate stay hard gates.
      </p>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <MetricTile label="Reward" value={fmtNum(metrics?.reward)} />
        <MetricTile label="Avg error" value={fmtNum(metrics?.avg_prediction_error)} />
        <MetricTile label="Steps" value={String(metrics?.training_steps ?? "—")} />
        <MetricTile
          label="vs Steve"
          value={
            metrics?.twin_steve_agreement_pct != null
              ? `${Number(metrics.twin_steve_agreement_pct).toFixed(1)}%`
              : "—"
          }
        />
      </div>

      {/* ── Approval Gym ─────────────────────────────────────────── */}
      <section className="space-y-2">
        <div className="flex items-center gap-2">
          <Dumbbell className="size-3.5 text-cyan-300/80" />
          <h4 className="font-mono text-[10px] tracking-[0.12em] text-muted-foreground uppercase">
            Approval Gym
          </h4>
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
          <article className="lumina-surface-muted rounded-lg border border-cyan-500/20 p-3">
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
              est. conf {fmtPct(currentDrill.estimated_confidence)}
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
                  Reject
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
      </section>

      <section className="space-y-2">
        <h4 className="font-mono text-[10px] tracking-[0.12em] text-muted-foreground uppercase">
          Review queue
        </h4>
        <p className="text-[10px] text-muted-foreground">
          High-stakes first (risk flags or score below 80%). Already-labeled DNA is hidden by
          default so only new judgments train the Twin.
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
                "lumina-surface-muted rounded-lg p-3",
                isHighStakes && "border border-amber-500/35",
                isRoutine && "opacity-90",
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
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                score {score != null ? fmtPct(score) : "—"} · rec={" "}
                {String(item.recommendation ?? "—")}
              </p>
              {Array.isArray(item.risk_flags) && item.risk_flags.length > 0 ? (
                <p className="mt-0.5 font-mono text-[10px] text-amber-200/80">
                  risks: {item.risk_flags.map(String).join(", ")}
                </p>
              ) : null}
              {item.explanation ? (
                <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">
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
                <div className="mt-3 flex flex-wrap gap-2">
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
                    Reject
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
              )}
            </article>
          );
        })}
      </section>

      <section className="space-y-2">
        <h4 className="font-mono text-[10px] tracking-[0.12em] text-muted-foreground uppercase">
          Label history (local audit)
        </h4>
        {labels.length === 0 ? (
          <p className="text-xs text-muted-foreground">No Steve labels yet.</p>
        ) : (
          <ul className="space-y-1.5">
            {labels.map((row, idx) => (
              <li
                key={`${row.timestamp}-${row.context_dna_hash}-${idx}`}
                className="rounded-md border border-border/40 px-2 py-1.5 font-mono text-[10px] text-muted-foreground"
              >
                <span className="text-violet-200/90">{row.steve_antwoord}</span>
                {" · "}
                {row.context_dna_hash.slice(0, 12)}
                {" · conf "}
                {fmtNum(row.confidence_score, 2)}
                {" · "}
                {row.timestamp.slice(0, 19)}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="lumina-surface-muted rounded-md px-2 py-1.5">
      <p className="font-mono text-[9px] tracking-[0.1em] text-muted-foreground uppercase">
        {label}
      </p>
      <p className="mt-0.5 font-mono text-sm text-foreground/90">{value}</p>
    </div>
  );
}
