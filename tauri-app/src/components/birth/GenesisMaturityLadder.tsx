import { cn } from "@/lib/utils";

export type MaturationPhaseId =
  | "setup"
  | "genesis"
  | "birth"
  | "awakening"
  | "playground"
  | "apprenticeship"
  | "proving_ground"
  | "real";

export interface MaturationStep {
  id: MaturationPhaseId;
  label: string;
  /** Short label for dense pipeline when needed */
  compactLabel?: string;
  short: string;
}

export const MATURATION_STEPS: MaturationStep[] = [
  { id: "setup", label: "Setup", short: "Vault · envelope · fabric" },
  { id: "genesis", label: "Genesis", short: "Maturity contract" },
  { id: "birth", label: "Birth", short: "Historical curriculum" },
  { id: "awakening", label: "Awakening", short: "Certificate + proof" },
  { id: "playground", label: "Playground", short: "NT sim — explore" },
  {
    id: "apprenticeship",
    label: "Apprenticeship",
    compactLabel: "Apprentice",
    short: "REAL rules, sim capital",
  },
  {
    id: "proving_ground",
    label: "Proving Ground",
    compactLabel: "Proving",
    short: "Shadow + promotion",
  },
  { id: "real", label: "REAL", short: "Live capital" },
];

interface GenesisMaturityLadderProps {
  activePhase?: MaturationPhaseId;
  className?: string;
}

/**
 * Evolution pipeline: Genesis → Birth → … → REAL.
 * "You are here" anchors under the active node only.
 */
export function GenesisMaturityLadder({
  activePhase = "genesis",
  className,
}: GenesisMaturityLadderProps) {
  const activeIdx = MATURATION_STEPS.findIndex((s) => s.id === activePhase);

  return (
    <div
      className={cn("genesis-evolution-pipeline", className)}
      aria-label="Lumina maturation ladder"
    >
      <ol className="genesis-evolution-pipeline__list">
        {MATURATION_STEPS.map((step, idx) => {
          const isActive = idx === activeIdx;
          const isPast = idx < activeIdx;
          return (
            <li
              key={step.id}
              className={cn(
                "genesis-evolution-pipeline__item",
                isActive && "genesis-evolution-pipeline__item--active",
              )}
            >
              {idx > 0 ? (
                <span className="genesis-evolution-pipeline__arrow" aria-hidden>
                  →
                </span>
              ) : null}
              <div className="genesis-evolution-pipeline__node-wrap">
                <span
                  className={cn(
                    "genesis-evolution-pipeline__node",
                    isActive && "genesis-evolution-pipeline__node--active",
                    isPast && "genesis-evolution-pipeline__node--past",
                  )}
                  title={step.short}
                >
                  <span className="genesis-evolution-pipeline__node-full">{step.label}</span>
                  <span className="genesis-evolution-pipeline__node-compact">
                    {step.compactLabel ?? step.label}
                  </span>
                </span>
                {isActive ? (
                  <span className="genesis-evolution-pipeline__here" aria-current="step">
                    You are here
                    <span className="genesis-evolution-pipeline__here-sub">
                      {step.short}
                    </span>
                  </span>
                ) : (
                  <span className="genesis-evolution-pipeline__here-spacer" aria-hidden />
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

interface GenesisMaturityGoalsPreviewProps {
  className?: string;
}

const MATURITY_GOALS: readonly string[] = [
  "Certificate OOS winrate ≥ 48%",
  "Evolution Proof: +5% lift or polish OOS ≥ 45% (≥500 trades)",
  "Apprenticeship: sim_real_guard stability, constitution 0 violations",
  "Proving Ground: shadow pass + PromotionGate + human approval",
];

/** Always-visible REAL maturity goals (no accordion). */
export function GenesisMaturityGoalsPreview({ className }: GenesisMaturityGoalsPreviewProps) {
  return (
    <div
      className={cn(
        "risk-envelope-field-card genesis-maturity-goals birth-genesis-goals-details",
        className,
      )}
    >
      <p className="risk-envelope-field-label genesis-maturity-goals__title mb-2">
        REAL maturity goals ({MATURITY_GOALS.length})
      </p>
      <ul className="genesis-maturity-goals__list">
        {MATURITY_GOALS.map((goal) => (
          <li
            key={goal}
            className="genesis-maturity-goals__item font-mono text-[10px] text-violet-100/85"
          >
            {goal}
          </li>
        ))}
      </ul>
      <p className="genesis-maturity-goals__footnote mt-2 font-mono text-[9px] text-violet-200/65">
        Birth grades process-R and occupancy — not a WR exam, not a REAL guarantee.
      </p>
    </div>
  );
}
