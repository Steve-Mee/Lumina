/**
 * Playground AND checklist — HUD green ⇔ engine proofs (ADR-0050).
 */
import type { StagePassChecklist, StagePassRequirement } from "@/lib/birth/birthStagePassChecklist";
import {
  resolveBooleanConditionTone,
  resolveConditionTone,
  type ConditionTone,
} from "@/lib/conditionTone";

const GATES: readonly { id: string; label: string }[] = [
  { id: "birth_freeze_intact", label: "Birth freeze" },
  { id: "awakening_child_loaded", label: "First Watch baseline" },
  { id: "sim_envelope_sealed", label: "SIM envelope" },
  { id: "deck_live", label: "Command Deck live" },
  { id: "mode_sim_fail_closed", label: "SIM mode" },
  { id: "policy_only", label: "Policy-only skill" },
  { id: "green_days>=5", label: "5 groene sessiedagen" },
  { id: "envelope_not_breached", label: "Envelope intact" },
];

export interface PlaygroundSenseBrief {
  pass_now?: boolean;
  headline?: string;
  waiting?: string;
  clock?: string;
  market?: string;
  paper?: string;
  venue?: string;
  alerts?: string[];
  tone?: "live" | "wait" | "alert" | "idle";
  lines?: string[];
}

export interface PlaygroundProgressView {
  pass_now?: boolean;
  missing?: string[];
  learned?: Record<string, unknown>;
  runner_active?: boolean;
  progress?: Record<string, unknown>;
  sense?: PlaygroundSenseBrief;
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

function yn(value: unknown): string {
  if (value === true) return "yes";
  if (value === false) return "no";
  return "—";
}

function proofsOf(learned: Record<string, unknown>): Set<string> {
  const raw = learned.exit_proofs ?? learned.proofs;
  if (!Array.isArray(raw)) return new Set();
  return new Set(raw.map((item) => String(item)));
}

function currentFor(id: string, learned: Record<string, unknown>): { current: string; need: string } {
  switch (id) {
    case "birth_freeze_intact":
      return { current: yn(learned.freeze_ok), need: "Birth artefacts read-only" };
    case "awakening_child_loaded":
      return {
        current: yn(Boolean(learned.child_sha) && learned.child_sha === learned.awakening_child_sha),
        need: "loaded zip = sealed baseline (may be Birth plant)",
      };
    case "sim_envelope_sealed":
      return { current: yn(learned.envelope_sealed), need: "operator sealed" };
    case "deck_live":
      return { current: yn(learned.deck_live), need: "open Command Deck" };
    case "mode_sim_fail_closed":
      return { current: String(learned.mode || "—"), need: "sim or sim_real_guard" };
    case "first_honest_fill":
      return { current: yn(learned.first_fill), need: "orderpath fill" };
    case "policy_only":
      return { current: yn(learned.policy_only), need: "policy closes only" };
    case "green_days>=5":
      return {
        current: `${Math.round(asNumber(learned.green_days) ?? 0)}`,
        need: "5 aaneengesloten groene sessiedagen",
      };
    case "n_P>=150":
      return { current: `${Math.round(asNumber(learned.n_p) ?? 0).toLocaleString("en-US")}`, need: "≥ 150 policy closes" };
    case "occupancy_in_band":
      return { current: pct(learned.occupancy), need: "25–75%" };
    case "process_r":
      return { current: asNumber(learned.median_loss_r)?.toFixed(2) ?? "—", need: "median loss R ≤ 1.5" };
    case "economic_viability":
      return {
        current: `${pct(learned.skill_wr)} / BE ${pct(learned.breakeven_wr)} · R ${asNumber(learned.mean_r)?.toFixed(2) ?? "—"}`,
        need: "WR ≥ live BE and mean R ≥ 0",
      };
    case "envelope_not_breached":
      return { current: yn(learned.envelope_breached !== true), need: "open risk held · verlies stopt de school niet" };
    default:
      return { current: "—", need: id.replace(/_/g, " ") };
  }
}

export function buildPlaygroundChecklist(view: PlaygroundProgressView | null): StagePassChecklist {
  const learned = view?.learned ?? {};
  const proofs = proofsOf(learned);
  const missing = new Set((view?.missing ?? []).map((item) => String(item)));
  const requirements: StagePassRequirement[] = GATES.map((gate) => {
    const met = proofs.has(gate.id) && !missing.has(gate.id);
    const { current, need } = currentFor(gate.id, learned);
    let tone: ConditionTone = met ? "ok" : resolveBooleanConditionTone(false);
    if (!met && gate.id === "n_P>=150") {
      tone = resolveConditionTone({
        value: asNumber(learned.n_p),
        target: 150,
        direction: "higher",
        criticalGap: 100,
      });
    }
    if (!met && gate.id === "occupancy_in_band") {
      tone = resolveConditionTone({
        value: asNumber(learned.occupancy),
        min: 0.25,
        max: 0.75,
        direction: "band",
      });
    }
    return { id: gate.id, label: gate.label, current, need, tone, met, kind: "gate" };
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
    stageTitle: "First steps",
    stageIndex: null,
    stageTotal: null,
    passCriteriaId: "playground_and_adr_0050",
    mission: "Leerschool in SIM. Poort: 5 groene sessiedagen. WR en mean R zijn het examen daarna. Geen REAL.",
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
