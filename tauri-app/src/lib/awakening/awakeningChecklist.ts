/**
 * Awakening AND checklist — HUD green ⇔ engine proofs.
 * Never paint a gate from hub copy; only from pass_now / exit_proofs / blockers.
 */
import type { StagePassChecklist, StagePassRequirement } from "@/lib/birth/birthStagePassChecklist";
import {
  resolveBooleanConditionTone,
  resolveConditionTone,
  type ConditionTone,
} from "@/lib/conditionTone";

const GATES: readonly { id: string; label: string }[] = [
  { id: "birth_freeze_intact", label: "Birth freeze" },
  { id: "policy_only", label: "Policy-only skill" },
  { id: "n_B>=500", label: "n_B ≥ 500" },
  { id: "occupancy_in_band", label: "Occupancy exam band" },
  { id: "process_r", label: "Process-R" },
  { id: "prefer_better_edge", label: "Prefer-better edge" },
  { id: "prefer_better_mean_r", label: "Prefer-better mean R" },
  { id: "evolution_proof_passed", label: "Evolution proof" },
  { id: "STABLE", label: "STABLE" },
  { id: "no_substitution", label: "No substitution" },
  { id: "twin_watch", label: "Twin watch of this run" },
  { id: "recovery_ok", label: "Recovery without cheat" },
  { id: "regime_visibility", label: "Regime visibility" },
];

export interface AwakeningProgressView {
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
    case "birth_freeze_intact":
      return { current: yn(learned.freeze_ok), need: "Birth artefacts read-only" };
    case "policy_only":
      return { current: yn(learned.policy_only), need: "policy closes only" };
    case "recovery_ok":
      return { current: yn(learned.recovery_ok), need: "stall→retry, freeze held" };
    case "no_substitution": {
      const child = typeof learned.child_sha === "string" ? learned.child_sha : "";
      const init = typeof learned.init_sha === "string" ? learned.init_sha : "";
      const same = Boolean(child) && child === init;
      return {
        current: !child || !init ? "—" : same ? "child = parent" : "child ≠ parent",
        need: "child sha ≠ frozen π*",
      };
    }
    case "n_B>=500":
      return {
        current: `${Math.round(asNumber(learned.n_b) ?? 0).toLocaleString("en-US")}`,
        need: "≥ 500 policy closes",
      };
    case "occupancy_in_band":
      return { current: pct(learned.occupancy), need: "25–75%" };
    case "process_r":
      return {
        current: asNumber(learned.median_loss_r)?.toFixed(2) ?? "—",
        need: "median loss R ≤ 1.5",
      };
    case "prefer_better_edge":
      return { current: pct(learned.edge), need: "edge ≥ 0" };
    case "prefer_better_mean_r":
      return {
        current: asNumber(learned.mean_r)?.toFixed(2) ?? "—",
        need: `≥ Birth ${asNumber(learned.birth_mean_r)?.toFixed(2) ?? "—"}`,
      };
    case "evolution_proof_passed":
      return {
        current: pct(learned.lift),
        need: "lift ≥ 5pp or OOS ≥ 45%",
      };
    case "STABLE":
      return {
        current: typeof learned.stable_class === "string" ? learned.stable_class : "INCONCLUSIVE",
        need: "Sharpe > −2 · DD ≤ 25%",
      };
    case "twin_watch":
      return {
        current: `${Math.round(asNumber(learned.twin_watch_n) ?? 0)}`,
        need: "Twin-source watch ≥ 1",
      };
    case "regime_visibility": {
      const observed = Array.isArray(learned.regime_observed)
        ? learned.regime_observed.map(String)
        : [];
      return {
        current: observed.length > 0 ? observed.join(" · ") : "none observed",
        need: "≥ 1 slice observed",
      };
    }
    default:
      return { current: "—", need: id.replace(/_/g, " ") };
  }
}

function toneFor(id: string, met: boolean, learned: Record<string, unknown>): ConditionTone {
  if (met) return "ok";
  if (id === "n_B>=500") {
    return resolveConditionTone({
      value: asNumber(learned.n_b),
      target: 500,
      direction: "higher",
      criticalGap: 400,
    });
  }
  if (id === "occupancy_in_band") {
    return resolveConditionTone({
      value: asNumber(learned.occupancy),
      min: 0.25,
      max: 0.75,
      direction: "band",
    });
  }
  return resolveBooleanConditionTone(false);
}

export function buildAwakeningChecklist(view: AwakeningProgressView | null): StagePassChecklist {
  const learned = view?.learned ?? {};
  const proofs = proofsOf(learned);
  const missing = new Set((view?.missing ?? []).map((item) => String(item)));
  const requirements: StagePassRequirement[] = GATES.map((gate) => {
    const met = proofs.has(gate.id) && !missing.has(gate.id);
    const { current, need } = currentFor(gate.id, learned);
    const tone = toneFor(gate.id, met, learned);
    return {
      id: gate.id,
      label: gate.label,
      current,
      need,
      tone,
      met,
      kind: "gate",
    };
  });
  const metCount = requirements.filter((row) => row.met).length;
  const extraMissing = (view?.missing ?? []).length > 0;
  const allMet =
    Boolean(view?.pass_now) && metCount === requirements.length && !extraMissing;
  const tones = requirements.map((row) => row.tone);
  let overallTone: ConditionTone = "default";
  if (tones.includes("danger") || extraMissing) overallTone = "danger";
  else if (tones.includes("warn")) overallTone = "warn";
  else if (allMet) overallTone = "ok";
  return {
    stageTitle: "Eyes open",
    stageIndex: null,
    stageTotal: null,
    passCriteriaId: "awakening_and_adr_0049",
    mission: "Prefer better than frozen π*. STABLE + n_B≥500. Not REAL.",
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
