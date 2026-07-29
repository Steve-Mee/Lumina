import { DeckSection } from "@/components/cockpit/DeckSection";
import { Button } from "@/components/ui/button";
import {
  formatTwinPct,
  twinScoreOf,
  type TwinDecision,
  type TwinReviewItem,
} from "@/lib/twinClient";
import { cn } from "@/lib/utils";

export interface TwinTrainReviewSectionProps {
  loading: boolean;
  queue: TwinReviewItem[];
  highStakesCount: number;
  includeLabeled: boolean;
  busyKey: string | null;
  activeModify: string | null;
  modifyNotes: Record<string, string>;
  feedbackNotes: Record<string, string>;
  onIncludeLabeledChange: (checked: boolean) => void;
  onActiveModifyChange: (dna: string | null) => void;
  onModifyNotesChange: (dna: string, notes: string) => void;
  onFeedbackNotesChange: (dna: string, notes: string) => void;
  onSubmitLabel: (item: TwinReviewItem, decision: TwinDecision) => void;
}

export function TwinTrainReviewSection({
  loading,
  queue,
  highStakesCount,
  includeLabeled,
  busyKey,
  activeModify,
  modifyNotes,
  feedbackNotes,
  onIncludeLabeledChange,
  onActiveModifyChange,
  onModifyNotesChange,
  onFeedbackNotesChange,
  onSubmitLabel,
}: TwinTrainReviewSectionProps) {
  return (
    <DeckSection title="Review queue">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <label className="flex cursor-pointer items-center gap-1.5 font-mono text-[10px] text-muted-foreground">
          <input
            type="checkbox"
            className="size-3 rounded border-border"
            checked={includeLabeled}
            onChange={(e) => onIncludeLabeledChange(e.target.checked)}
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
              isHighStakes && "border border-[color:var(--status-warn-border)]",
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
                  onChange={(e) => onModifyNotesChange(dna, e.target.value)}
                />
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="xs"
                    disabled={busyKey !== null}
                    onClick={() => onSubmitLabel(item, "modify")}
                  >
                    Submit modify
                  </Button>
                  <Button
                    type="button"
                    size="xs"
                    variant="ghost"
                    onClick={() => onActiveModifyChange(null)}
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
                  onChange={(e) => onFeedbackNotesChange(dna, e.target.value)}
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="xs"
                    disabled={busyKey !== null}
                    onClick={() => onSubmitLabel(item, "approve")}
                  >
                    Approve
                  </Button>
                  <Button
                    type="button"
                    size="xs"
                    variant="secondary"
                    disabled={busyKey !== null}
                    onClick={() => onSubmitLabel(item, "reject")}
                  >
                    Veto
                  </Button>
                  <Button
                    type="button"
                    size="xs"
                    variant="ghost"
                    disabled={busyKey !== null}
                    onClick={() => onActiveModifyChange(dna)}
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
  );
}
