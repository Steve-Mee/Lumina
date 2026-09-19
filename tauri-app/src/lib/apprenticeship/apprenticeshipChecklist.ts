/**
 * Apprenticeship AND checklist — HUD green ⇔ engine proofs.
 */
import type { StagePassChecklist, StagePassRequirement } from "@/lib/birth/birthStagePassChecklist";
import {
  resolveBooleanConditionTone,
  resolveConditionTone,
  type ConditionTone,
} from "@/lib/conditionTone";

const GATES: readonly { id: string; label: string }[] = [
  { id: "playground_completed", label: "Playground completed" },
  { id: "birth_freeze_intact", label: "Birth freeze" },
  { id: "playground_child_loaded", label: "Playground child loaded" },
  { id: "sim_envelope_sealed", label: "SIM envelope sealed" },
  { id: "deck_live", label: "Command Deck live" },
  { id: "mode_sim_real_guard", label: "sim_real_guard" },
  { id: "n_A>=150", label: "n_A ≥ 150" },
  { id: "n_D>=5", label: "5 green session days" },
  { id: "occupancy_in_band", label: "Occupancy exam band" },
  { id: "process_r", label: "Process-R" },
  { id: "risk_discipline", label: "Sharpe ≥ 0.20 · DD ≤ 12%" },
  { id: "constitution_0", label: "Constitution 0" },
  { id: "recovery_ok", label: "Never-stop recovery" },
];

export interface ApprenticeshipProgressView {
  pass_now?: boolean;
  missing?: string[];
  learned?: Record<string, unknown>;
  runner_active?: boolean;
  progress?: Record<string, unknown>;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function pct(value: unknown): string {
  const n = asNumber(value);
  if (n == null) return "—";
  const ratio = Math.abs(n) <= 1.5 ? n : n / 100;
  return `${(ratio * 100).toFixed(1)}%`;
}

function proofsOf(learned: Record<string, unknown>): Set<string> {
  const raw = learned.exit_proofs ?? learned.proofs;
  if (!Array.isArray(raw)) return new Set();
  return new Set(raw.map((item) => String(item)));
}

function yn(value: unknown): string {
  if (value === true) return "yes";
  if (value === false) return "no";
  return "—";
}

function currentFor(id: string, learned: Record<string, unknown>): { current: string; need: string } {
  switch (id) {
    case "playground_completed":
      return { current: yn(learned.playground_completed), need: "ADR-0050 AND held" };
    case "birth_freeze_intact":
      return { current: yn(learned.freeze_ok), need: "Birth artefacts read-only" };
    case "playground_child_loaded":
      return { current: yn(Boolean(learned.child_sha)), need: "child ≠ Birth π*" };
    case "sim_envelope_sealed":
      return { current: yn(learned.envelope_sealed), need: "operator-sealed" };
    case "deck_live":
      return { current: yn(learned.deck_live), need: "fabric + NT live" };
    case "mode_sim_real_guard":
      return { current: String(learned.mode || "—"), need: "sim_real_guard" };
    case "n_A>=150":
      return {
        current: `${Math.round(asNumber(learned.n_a) ?? 0).toLocaleString("en-US")}`,
        need: "≥ 150 policy closes",
      };
    case "n_D>=5":
      return {
        current: `${Math.round(asNumber(learned.n_d) ?? 0)}`,
        need: "≥ 5 consecutive green days",
      };
    case "occupancy_in_band":
      return { current: pct(learned.occupancy), need: "25–75%" };
    case "process_r":
      return {
        current: asNumber(learned.median_loss_r)?.toFixed(2) ?? "—",
        need: "median loss R ≤ 1.5",
      };
    case "risk_discipline":
      return {
        current: `Sharpe ${asNumber(learned.sharpe)?.toFixed(2) ?? "—"} · DD ${pct(learned.dd_pct)}`,
        need: "Sharpe ≥ 0.20 · DD ≤ 12%",
      };
    case "constitution_0":
      return {
        current: asNumber(learned.risk_events) ? `${learned.risk_events} events` : "0",
        need: "no risk / VaR / kill",
      };
    case "recovery_ok":
      return { current: yn(learned.recovery_ok), need: "resume same tape" };
    default:
      return { current: "—", need: id.replace(/_/g, " ") };
  }
}

function toneFor(id: string, met: boolean, learned: Record<string, unknown>): ConditionTone {
  if (met) return "ok";
  if (id === "n_A>=150") {
    return resolveConditionTone({
      value: asNumber(learned.n_a),
      target: 150,
      direction: "higher",
      criticalGap: 100,
    });
  }
  if (id === "n_D>=5") {
    return resolveConditionTone({
      value: asNumber(learned.n_d),
      target: 5,
      direction: "higher",
      criticalGap: 4,
    });
  }
  return resolveBooleanConditionTone(false);
}

export function buildApprenticeshipChecklist(
  view: ApprenticeshipProgressView | null,
): StagePassChecklist {
  const learned = view?.learned ?? {};
  const proofs = proofsOf(learned);
  const missing = new Set((view?.missing ?? []).map((item) => String(item)));
  const requirements: StagePassRequirement[] = GATES.map((gate) => {
    const met = proofs.has(gate.id) && !missing.has(gate.id);
    const { current, need } = currentFor(gate.id, learned);
    return {
      id: gate.id,
      label: gate.label,
      current,
      need,
      tone: toneFor(gate.id, met, learned),
      met,
      kind: "gate",
    };
  });
  const metCount = requirements.filter((row) => row.met).length;
  const extraMissing = (view?.missing ?? []).length > 0;
  const allMet = Boolean(view?.pass_now) && metCount === requirements.length && !extraMissing;
  const tones = requirements.map((row) => row.tone);
  let overallTone: ConditionTone = "default";
  if (tones.includes("danger") || extraMissing) overallTone = "danger";
  else if (tones.includes("warn")) overallTone = "warn";
  else if (allMet) overallTone = "ok";
  return {
    stageTitle: "Walk",
    stageIndex: null,
    stageTotal: null,
    passCriteriaId: "apprenticeship_and_adr_0051",
    mission: "Multi-day SIM under REAL rules. Sharpe ≥ 0.20, DD ≤ 12%, 5 green days. Not REAL.",
    requirements,
    metCount,
    totalCount: requirements.length,
    allMet,
    skillMetCount: 0,
    skillTotalCount: 0,
    overallTone,
    passMode: "skill",
  };
}
