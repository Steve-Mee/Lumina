import { Dumbbell } from "lucide-react";

import { DeckSection } from "@/components/cockpit/DeckSection";
import { Button } from "@/components/ui/button";
import {
  formatTwinPct,
  type GymProposal,
  type GymSession,
  type TwinDecision,
} from "@/lib/twinClient";
import { cn } from "@/lib/utils";

export interface TwinTrainGymSectionProps {
  gymSession: GymSession | null;
  gymIndex: number;
  currentDrill: GymProposal | null;
  gymModifyOpen: boolean;
  gymNotes: string;
  busyKey: string | null;
  onStartGym: () => void;
  onEndGym: () => void;
  onGymNotesChange: (notes: string) => void;
  onGymModifyOpenChange: (open: boolean) => void;
  onSubmitGymAnswer: (proposal: GymProposal, decision: TwinDecision) => void;
}

export function TwinTrainGymSection({
  gymSession,
  gymIndex,
  currentDrill,
  gymModifyOpen,
  gymNotes,
  busyKey,
  onStartGym,
  onEndGym,
  onGymNotesChange,
  onGymModifyOpenChange,
  onSubmitGymAnswer,
}: TwinTrainGymSectionProps) {
  return (
    <DeckSection title="Approval Gym" icon={Dumbbell}>
      <div className="mb-2 flex items-center gap-2">
        {!gymSession ? (
          <Button
            type="button"
            size="xs"
            className="ml-auto"
            disabled={busyKey !== null}
            onClick={onStartGym}
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
            onClick={onEndGym}
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
                onChange={(e) => onGymNotesChange(e.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="xs"
                  disabled={busyKey !== null}
                  onClick={() => onSubmitGymAnswer(currentDrill, "modify")}
                >
                  Submit modify
                </Button>
                <Button
                  type="button"
                  size="xs"
                  variant="ghost"
                  onClick={() => {
                    onGymModifyOpenChange(false);
                    onGymNotesChange("");
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
                onClick={() => onSubmitGymAnswer(currentDrill, "approve")}
              >
                Approve
              </Button>
              <Button
                type="button"
                size="xs"
                variant="secondary"
                disabled={busyKey !== null}
                onClick={() => onSubmitGymAnswer(currentDrill, "reject")}
              >
                Veto
              </Button>
              <Button
                type="button"
                size="xs"
                variant="ghost"
                disabled={busyKey !== null}
                onClick={() => onGymModifyOpenChange(true)}
              >
                Modify…
              </Button>
            </div>
          )}
        </article>
      ) : null}
    </DeckSection>
  );
}
