/**
 * Proving Ground AND checklist — HUD green ⇔ engine proofs.
 */
import type { StagePassChecklist, StagePassRequirement } from "@/lib/birth/birthStagePassChecklist";
import {
  resolveBooleanConditionTone,
  resolveConditionTone,
  type ConditionTone,
} from "@/lib/conditionTone";

const GATES: readonly { id: string; label: string }[] = [
  { id: "apprenticeship_completed", label: "Apprenticeship completed" },
  { id: "birth_freeze_intact", label: "Birth freeze" },
  { id: "apprenticeship_child_loaded", label: "Apprenticeship child loaded" },
  { id: "sim_envelope_sealed", label: "SIM envelope sealed" },
  { id: "deck_live", label: "Command Deck live" },
  { id: "mode_sim_fail_closed", label: "SIM mode" },
  { id: "n_G>=150", label: "n_G ≥ 150" },
  { id: "occupancy_in_band", label: "Occupancy exam band" },
  { id: "process_r", label: "Process-R" },
  { id: "exam_source_proving", label: "Exam source proving" },
  { id: "exam_eval_only", label: "Eval-only (no learn)" },
  { id: "exam_folds>=5", label: "Purged folds ≥ 5" },
  { id: "certificate_oos_walls", label: "Cert 48% / 0.35 / 8%" },
  { id: "shadow_this_run", label: "Shadow this clock" },
  { id: "promotion_gate_this_run", label: "PromotionGate 4/4" },
  { id: "constitution_0", label: "Constitution 0" },
  { id: "recovery_ok", label: "Never-stop recovery" },
];

export interface ProvingGroundProgressView {
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
    case "apprenticeship_completed":
      return { current: yn(learned.apprenticeship_completed), need: "ADR-0051 AND held" };
    case "birth_freeze_intact":
      return { current: yn(learned.freeze_ok), need: "Birth artefacts read-only" };
    case "apprenticeship_child_loaded":
      return { current: yn(Boolean(learned.child_sha)), need: "child ≠ Birth π*" };
    case "sim_envelope_sealed":
      return { current: yn(learned.envelope_sealed), need: "operator-sealed" };
    case "deck_live":
      return { current: yn(learned.deck_live), need: "fabric + NT live" };
    case "mode_sim_fail_closed":
      return { current: String(learned.mode || "—"), need: "sim / sim_real_guard" };
    case "n_G>=150":
      return {
        current: `${Math.round(asNumber(learned.n_g) ?? 0).toLocaleString("en-US")}`,
        need: "≥ 150 policy closes",
      };
    case "occupancy_in_band":
      return { current: pct(learned.occupancy), need: "25–75%" };
    case "process_r":
      return {
        current: asNumber(learned.median_loss_r)?.toFixed(2) ?? "—",
        need: "median loss R ≤ 1.5",
      };
    case "exam_source_proving":
      return { current: String(learned.exam_source || "—"), need: "proving_exam / proving_tape" };
    case "exam_eval_only":
      return { current: yn(learned.exam_eval_only), need: "no learn() on A/B" };
    case "exam_folds>=5":
      return {
        current: `${Math.round(asNumber(learned.exam_folds) ?? 0)}`,
        need: "≥ 5 purged folds",
      };
    case "certificate_oos_walls":
      return {
        current: `WR ${pct(learned.oos_wr)} · Sharpe ${asNumber(learned.oos_sharpe)?.toFixed(2) ?? "—"} · DD ${pct(learned.dd_pct)}`,
        need: "WR ≥ 48% · Sharpe ≥ 0.35 · DD ≤ 8%",
      };
    case "shadow_this_run":
      return { current: yn(learned.shadow_this_run), need: "this clock, not audit scan" };
    case "promotion_gate_this_run":
      return {
        current: `${Math.round(asNumber(learned.promotion_criteria_passed) ?? 0)}/4`,
        need: "PromotionGate.evaluate this run",
      };
    case "constitution_0":
      return {
        current: asNumber(learned.risk_events) ? `${learned.risk_events} events` : "0",
        need: "no risk / VaR / kill / REAL",
      };
    case "recovery_ok":
      return { current: yn(learned.recovery_ok), need: "resume same tape" };
    default:
      return { current: "—", need: id.replace(/_/g, " ") };
  }
}

function toneFor(id: string, met: boolean, learned: Record<string, unknown>): ConditionTone {
  if (met) return "ok";
  if (id === "n_G>=150") {
    return resolveConditionTone({
      value: asNumber(learned.n_g),
      target: 150,
      direction: "higher",
      criticalGap: 100,
    });
  }
  return resolveBooleanConditionTone(false);
}

export function buildProvingGroundChecklist(
  view: ProvingGroundProgressView | null,
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
    stageTitle: "Driving test",
    stageIndex: null,
    stageTotal: null,
    passCriteriaId: "proving_ground_and_adr_0052",
    mission: "Cert OOS 48%/0.35/8% + this-run shadow + PromotionGate 4/4. Not REAL.",
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
