import { FieldCard, ToggleRow } from "@/components/config/BotConfigFormPrimitives";
import { HelpTip } from "@/components/ui/HelpTip";
import type { BotConfigDraft, MutationDepth } from "@/lib/botConfigDraft";
import { CONSEQUENCE_HINTS, helpFor } from "@/lib/helpTexts";
import { luminaSurfaceMutedClass } from "@/lib/glassGlowTaxonomy";
import { cn } from "@/lib/utils";

const MUTATION_OPTIONS: {
  value: MutationDepth;
  label: string;
  hint: string;
  risk: string;
}[] = [
  {
    value: "conservative",
    label: "Conservative",
    hint: "Minimal hyperparameter drift",
    risk: "Slowest learning, safest policy steps.",
  },
  {
    value: "moderate",
    label: "Moderate",
    hint: "Balanced exploration",
    risk: "Default middle ground for controlled growth.",
  },
  {
    value: "radical",
    label: "Radical",
    hint: "SIM only — deep mutations",
    risk: "Fastest change; constitution blocks this in REAL.",
  },
];

export interface BotConfigEvolutionTabProps {
  draft: BotConfigDraft;
  onChange: (patch: Partial<BotConfigDraft>) => void;
  className?: string;
}

export function BotConfigEvolutionTab({
  draft,
  onChange,
  className,
}: BotConfigEvolutionTabProps) {
  const isReal = draft.mode === "real";

  const setMutationDepth = (depth: MutationDepth) => {
    if (isReal && depth === "radical") {
      return;
    }
    onChange({
      evolution: { ...draft.evolution, max_mutation_depth: depth },
    });
  };

  return (
    <div className={className}>
      <div className="mb-1 flex items-center gap-1.5">
        <h3 className="bot-config-section-title mb-0">Evolution governance</h3>
        <HelpTip text={helpFor("max_mutation_depth") ?? ""} />
      </div>
      <p className="mb-3 text-[11px] leading-relaxed text-muted-foreground">
        How hard the organism may rewrite itself — and whether you hold the
        final key. Agents propose; you (or Final Arbitration) decide.
      </p>

      <FieldCard
        label="Aggressive evolution"
        tip={helpFor("aggressive_evolution")}
        hint={
          isReal
            ? "Not recommended for REAL — prefer stable, approved steps."
            : "Faster exploration in SIM; pair with approval if you want control."
        }
      >
        <ToggleRow
          label="Enable aggressive evolution"
          checked={draft.evolution.aggressive_evolution}
          onChange={(aggressive_evolution) =>
            onChange({
              evolution: { ...draft.evolution, aggressive_evolution },
            })
          }
          warn={
            isReal && draft.evolution.aggressive_evolution
              ? "Aggressive evolution + REAL target is high risk."
              : null
          }
        />
      </FieldCard>

      <FieldCard
        label="Mutation depth"
        tip={helpFor("max_mutation_depth")}
        className="mt-3"
      >
        <div className="mt-1 grid gap-2">
          {MUTATION_OPTIONS.map((option) => {
            const disabled = isReal && option.value === "radical";
            const active = draft.evolution.max_mutation_depth === option.value;
            return (
              <button
                key={option.value}
                type="button"
                disabled={disabled}
                onClick={() => setMutationDepth(option.value)}
                className={cn(
                  "risk-envelope-mutation-card",
                  active && "risk-envelope-mutation-card--active",
                  disabled && "cursor-not-allowed opacity-40",
                  !active &&
                    !disabled &&
                    luminaSurfaceMutedClass(
                      "border border-white/10 hover:border-white/20",
                    ),
                )}
                aria-pressed={active}
              >
                <p className="font-mono text-xs text-foreground">{option.label}</p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  {option.hint}
                </p>
                <p className="mt-1 text-[10px] text-cyan-200/55">{option.risk}</p>
                {disabled ? (
                  <p className="mt-1 text-[10px] text-rose-300/80">
                    {CONSEQUENCE_HINTS.radical_blocked}
                  </p>
                ) : null}
              </button>
            );
          })}
        </div>
      </FieldCard>

      <FieldCard
        label="Human approval"
        tip={helpFor("approval_required")}
        hint={
          draft.evolution.approval_required
            ? CONSEQUENCE_HINTS.approval_on
            : CONSEQUENCE_HINTS.approval_off
        }
        className="mt-3"
      >
        <ToggleRow
          label="Require operator approval for mutations"
          checked={draft.evolution.approval_required}
          onChange={(approval_required) =>
            onChange({
              evolution: { ...draft.evolution, approval_required },
            })
          }
          hint="Approve or reject from Decision Theater and Evolution deck."
        />
      </FieldCard>
    </div>
  );
}
