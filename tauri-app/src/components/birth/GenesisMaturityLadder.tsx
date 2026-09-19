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
  { id: "awakening", label: "Awakening", short: "Prefer better policies" },
  { id: "playground", label: "Playground", short: "NT SIM — crawl · WR≥BE" },
  {
    id: "apprenticeship",
    label: "Apprenticeship",
    compactLabel: "Apprentice",
    short: "Walk · Sharpe ≥ 0.20 · 5 green days",
  },
  {
    id: "proving_ground",
    label: "Proving Ground",
    compactLabel: "Proving",
    short: "Cert 48% · shadow · gate",
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

interface MaturityGoal {
  id: MaturationPhaseId;
  phase: string;
  gate: string;
  detail: string;
  now?: boolean;
}

const MATURITY_GOALS: readonly MaturityGoal[] = [
  {
    id: "birth",
    phase: "Birth",
    gate: "5/5 plant",
    now: true,
    detail: "Birth: Foundation 5/5 + fitness (process-R + occupancy — not a WR exam)",
  },
  {
    id: "awakening",
    phase: "Awakening",
    gate: "STABLE · n≥500",
    detail:
      "Awakening: prefer-better AND — STABLE, n_B≥500 policy-only, occupancy, process-R, Twin-watch of this run. Lift ≥5pp or OOS ≥45% is necessary, not sufficient.",
  },
  {
    id: "playground",
    phase: "Playground",
    gate: "WR ≥ BE",
    detail: "Playground: skill WR ≥ geometry BE and mean R ≥ 0 + first SIM order",
  },
  {
    id: "apprenticeship",
    phase: "Apprentice",
    gate: "Sharpe · 0 viol",
    detail:
      "Apprenticeship: walk — 5 green sim_real_guard days, Sharpe ≥ 0.20, DD ≤ 12%, constitution 0",
  },
  {
    id: "proving_ground",
    phase: "Proving",
    gate: "OOS 48%",
    detail:
      "Proving Ground: Certificate OOS ≥ 48% / Sharpe ≥ 0.35 / DD ≤ 8% + this-run shadow + PromotionGate. Human approval is REAL.",
  },
];

/** Always-visible REAL walls as a one-plane strip (no accordion, no scroll). */
export function GenesisMaturityGoalsPreview({ className }: GenesisMaturityGoalsPreviewProps) {
  return (
    <div
      className={cn(
        "risk-envelope-field-card genesis-maturity-goals birth-genesis-goals-details",
        className,
      )}
    >
      <p className="risk-envelope-field-label genesis-maturity-goals__title">
        REAL walls
      </p>
      <ol className="genesis-maturity-goals__list" aria-label="REAL maturity walls">
        {MATURITY_GOALS.map((goal, idx) => (
          <li
            key={goal.id}
            className={cn(
              "genesis-maturity-goals__item",
              goal.now && "genesis-maturity-goals__item--now",
            )}
            title={goal.detail}
          >
            {idx > 0 ? (
              <span className="genesis-maturity-goals__arrow" aria-hidden>
                →
              </span>
            ) : null}
            <span className="genesis-maturity-goals__phase">{goal.phase}</span>
            <span className="genesis-maturity-goals__gate">{goal.gate}</span>
          </li>
        ))}
      </ol>
      <p className="genesis-maturity-goals__footnote">
        Birth is now · later walls block REAL · hover a node for the full gate
      </p>
    </div>
  );
}
