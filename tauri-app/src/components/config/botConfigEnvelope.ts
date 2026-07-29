import { CONSEQUENCE_HINTS } from "@/lib/helpTexts";
import type { BotConfigDraft } from "@/lib/botConfigDraft";

export function patchDraft(
  draft: BotConfigDraft,
  patch: Partial<BotConfigDraft>,
): BotConfigDraft {
  return {
    ...draft,
    ...patch,
    risk: { ...draft.risk, ...(patch.risk ?? {}) },
    evolution: { ...draft.evolution, ...(patch.evolution ?? {}) },
  };
}

export function kellyConsequence(kelly: number, isReal: boolean): string {
  if (isReal) {
    return kelly <= 0.25
      ? CONSEQUENCE_HINTS.kelly_real_safe
      : CONSEQUENCE_HINTS.kelly_real_hot;
  }
  if (kelly >= 0.75) return CONSEQUENCE_HINTS.kelly_high;
  if (kelly <= 0.25) return "Low Kelly — small size, slower growth, shallower drawdowns.";
  return "Balanced Kelly — size scales with edge confidence.";
}

export function dailyCapConsequence(cap: number | null): string {
  if (cap == null || cap === 0) return CONSEQUENCE_HINTS.daily_none;
  return CONSEQUENCE_HINTS.daily_on;
}

export function openRiskConsequence(value: number, isReal: boolean): string {
  if (isReal && value <= 200) return CONSEQUENCE_HINTS.open_risk_tight;
  if (value >= 2500) return CONSEQUENCE_HINTS.open_risk_high;
  return CONSEQUENCE_HINTS.open_risk_tight;
}

export function envelopeSummaryLine(draft: BotConfigDraft): string {
  const cap =
    draft.risk.daily_loss_cap == null ? "None" : `$${draft.risk.daily_loss_cap}`;
  return [
    `Mode ${draft.mode.toUpperCase()}`,
    `Kelly ${draft.risk.kelly_fraction.toFixed(2)}`,
    `Day cap ${cap}`,
    `Open $${draft.risk.max_total_open_risk}`,
    `Mut ${draft.evolution.max_mutation_depth}`,
    draft.evolution.approval_required ? "Approval ON" : "Approval OFF",
  ].join(" · ");
}

export function envelopeConsequenceLine(draft: BotConfigDraft): string {
  if (draft.mode === "real") return CONSEQUENCE_HINTS.real_target;
  if (draft.mode === "paper") return CONSEQUENCE_HINTS.paper_path;
  if (draft.mode === "sim_real_guard") {
    return "SIM with REAL-like guards — still no live capital; tighter rehearsal.";
  }
  if (
    draft.risk.daily_loss_cap == null &&
    draft.risk.kelly_fraction >= 0.75 &&
    draft.evolution.max_mutation_depth === "radical"
  ) {
    return CONSEQUENCE_HINTS.sim_loose;
  }
  return "Envelope set — Birth stays SIM until you graduate to live capital.";
}

export type EnvelopeChipState = "idle" | "ok" | "partial" | "fail" | "warn";

export function resolveEnvelopeChips(draft: BotConfigDraft): {
  mode: EnvelopeChipState;
  risk: EnvelopeChipState;
  evolution: EnvelopeChipState;
  birth: EnvelopeChipState;
} {
  const isReal = draft.mode === "real";
  const looseSim =
    !isReal &&
    draft.risk.kelly_fraction >= 0.75 &&
    draft.risk.daily_loss_cap == null;

  let risk: EnvelopeChipState = "ok";
  if (isReal) {
    const hot =
      draft.risk.kelly_fraction > 0.25 ||
      draft.risk.daily_loss_cap == null ||
      draft.risk.max_total_open_risk > 500;
    risk = hot ? "warn" : "ok";
  } else if (looseSim) {
    risk = "partial";
  }

  let evolution: EnvelopeChipState = "ok";
  if (isReal && draft.evolution.max_mutation_depth === "radical") {
    evolution = "fail";
  } else if (
    draft.evolution.aggressive_evolution ||
    draft.evolution.max_mutation_depth === "radical"
  ) {
    evolution = draft.evolution.approval_required ? "partial" : "warn";
  } else if (!draft.evolution.approval_required) {
    evolution = "partial";
  }

  return {
    mode: isReal ? "warn" : draft.mode === "sim_real_guard" ? "partial" : "ok",
    risk,
    evolution,
    birth: "ok",
  };
}
