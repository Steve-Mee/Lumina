import { BirthHoloSlider } from "@/components/birth/BirthHoloSlider";
import { cn } from "@/lib/utils";

export type MaturationPhaseId =
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
  short: string;
}

export const MATURATION_STEPS: MaturationStep[] = [
  { id: "genesis", label: "Genesis", short: "Maturity contract" },
  { id: "birth", label: "Birth", short: "Historical curriculum" },
  { id: "awakening", label: "Awakening", short: "Certificate + proof" },
  { id: "playground", label: "Playground", short: "NT sim — explore" },
  { id: "apprenticeship", label: "Apprenticeship", short: "REAL rules, sim capital" },
  { id: "proving_ground", label: "Proving Ground", short: "Shadow + promotion" },
  { id: "real", label: "REAL", short: "Live capital" },
];

interface GenesisMaturityLadderProps {
  activePhase?: MaturationPhaseId;
  className?: string;
}

export function GenesisMaturityLadder({
  activePhase = "genesis",
  className,
}: GenesisMaturityLadderProps) {
  const activeIdx = MATURATION_STEPS.findIndex((s) => s.id === activePhase);

  return (
    <div className={cn("genesis-maturity-ladder", className)} aria-label="Lumina maturation ladder">
      <ol className="flex flex-wrap justify-center gap-1.5">
        {MATURATION_STEPS.map((step, idx) => {
          const isActive = idx === activeIdx;
          const isPast = idx < activeIdx;
          return (
            <li
              key={step.id}
              className={cn(
                "rounded border px-2 py-1 font-mono text-[9px] tracking-wide uppercase",
                isActive
                  ? "border-cyan-400/50 bg-cyan-950/40 text-cyan-100"
                  : isPast
                    ? "border-emerald-500/30 bg-emerald-950/20 text-emerald-200/80"
                    : "border-border/40 bg-muted/10 text-muted-foreground/60",
              )}
              title={step.short}
            >
              {step.label}
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
  "Evolution Proof: +5% lift of polish OOS ≥ 45% (≥500 trades)",
  "Apprenticeship: sim_real_guard stabiliteit, constitution 0 violations",
  "Proving Ground: shadow pass + PromotionGate + human approval",
];

export function GenesisMaturityGoalsPreview({ className }: GenesisMaturityGoalsPreviewProps) {
  return (
    <div className={cn("genesis-maturity-goals", className)}>
      <p className="genesis-maturity-goals__title font-mono text-[10px] tracking-[0.14em] text-violet-200/90 uppercase">
        Volwassenheidsdoelen (REAL)
      </p>
      <ul className="genesis-maturity-goals__list">
        {MATURITY_GOALS.map((goal) => (
          <li key={goal} className="genesis-maturity-goals__item font-mono text-[10px] text-violet-100/85">
            {goal}
          </li>
        ))}
      </ul>
      <p className="genesis-maturity-goals__footnote font-mono text-[9px] text-violet-200/65">
        Birth winrate gate hierboven is pipeline-validatie — geen REAL-garantie.
      </p>
    </div>
  );
}

function gateWarningCopy(gatePct: number): { tone: "ok" | "warn" | "danger"; text: string } {
  if (gatePct >= 45) {
    return { tone: "ok", text: "Aanbevolen — sluit aan bij certificate OOS." };
  }
  if (gatePct >= 38) {
    return {
      tone: "warn",
      text: "Birth kan doorgaan; verwacht sterkere post-birth Evolution Proof.",
    };
  }
  return {
    tone: "danger",
    text: "Pipeline-validatie only; REAL geblokkeerd tot Evolution Proof + OOS ≥48%.",
  };
}

export function GenesisWinrateGateBlock({
  gatePct,
  disabled,
  onChange,
}: {
  gatePct: number;
  disabled?: boolean;
  onChange: (pct: number) => void;
}) {
  const warning = gateWarningCopy(gatePct);
  return (
    <div className="space-y-1">
      <BirthHoloSlider
        label="Stage 1 winrate gate"
        value={gatePct}
        min={35}
        max={45}
        step={1}
        format={(v) => `${v}%`}
        disabled={disabled}
        onChange={onChange}
      />
      <p
        className={cn(
          "text-xs",
          warning.tone === "ok"
            ? "text-emerald-200/90"
            : warning.tone === "warn"
              ? "text-amber-200/90"
              : "text-orange-200/90",
        )}
      >
        {warning.text}
      </p>
    </div>
  );
}
