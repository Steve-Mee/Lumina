/** Phase Hub AND-gate board — same engine proofs as living missions, idle ≠ fail. */
import { phaseStartIncomplete, proofLabel } from "@/components/maturity/phaseHubFormat";
import { buildApprenticeshipChecklist } from "@/lib/apprenticeship/apprenticeshipChecklist";
import { buildAwakeningChecklist } from "@/lib/awakening/awakeningChecklist";
import type { StagePassChecklist, StagePassRequirement } from "@/lib/birth/birthStagePassChecklist";
import type { MaturityHubPayload } from "@/lib/maturationClient";
import { buildPlaygroundChecklist } from "@/lib/playground/playgroundChecklist";
import { buildProvingGroundChecklist } from "@/lib/provingGround/provingGroundChecklist";

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function mapBlockerToGate(code: string): string | null {
  const raw = String(code || "").trim();
  if (!raw) return null;
  if (raw.startsWith("n_B=") || raw === "n_B>=500") return "n_B>=500";
  if (raw.startsWith("n_P=") || raw === "n_P>=150") return "n_P>=150";
  if (raw.startsWith("n_A=") || raw === "n_A>=150") return "n_A>=150";
  if (raw.startsWith("n_G=") || raw === "n_G>=150") return "n_G>=150";
  if (raw.startsWith("occupancy")) return "occupancy_in_band";
  if (raw.startsWith("median_loss") || raw === "process_r") return "process_r";
  if (
    raw === "baseline_book_missing" ||
    raw.includes("baseline_book") ||
    raw === "parent_replay_missing"
  ) {
    return "baseline_book";
  }
  if (raw.includes("constitution")) return "constitution_clear";
  if (raw.includes("baseline_not_the_plant") || raw.includes("weight_sha")) return "baseline_is_plant";
  if (raw.startsWith("stable_class") || raw.startsWith("sharpe=") || raw.startsWith("dd=")) {
    return "STABLE";
  }
  if (raw.includes("twin")) return "twin_watch";
  if (raw.includes("recovery")) return "recovery_ok";
  if (raw.includes("regime")) return "regime_visibility";
  if (raw.includes("freeze")) return "birth_freeze_intact";
  if (raw.includes("policy_only") || raw.includes("skill_not_policy")) return "policy_only";
  if (raw.includes("green_days") || raw.startsWith("n_D=")) return "green_days>=5";
  return null;
}

function extraMissingRows(
  missing: string[],
  list: StagePassChecklist,
): StagePassRequirement[] {
  const known = new Set(list.requirements.map((row) => row.id));
  return missing
    .map((code) => String(code))
    .filter((code) => code && !known.has(code) && !mapBlockerToGate(code))
    .map((code) => ({
      id: code,
      label: proofLabel(code),
      current: "open",
      need: "engine blocker",
      tone: "warn" as const,
      met: false,
      kind: "gate" as const,
    }));
}

function idleCurrent(row: StagePassRequirement, hub: MaturityHubPayload | null): string {
  if (row.id === "birth_freeze_intact" && hub?.birth_exit_exited && !row.met) {
    return "Birth plant frozen";
  }
  return row.current;
}

function genericChecklist(
  focus: string,
  missing: string[],
  passNow: boolean,
): StagePassChecklist {
  const requirements: StagePassRequirement[] = missing.map((code) => ({
    id: code,
    label: proofLabel(code),
    current: passNow ? "met" : "open",
    need: "required to leave this phase",
    tone: passNow ? "ok" : "default",
    met: passNow,
    kind: "gate",
  }));
  return {
    stageTitle: focus.replace(/_/g, " "),
    stageIndex: null,
    stageTotal: null,
    passCriteriaId: `${focus}_hub_gates`,
    mission: "Engine AND gates for the focus phase.",
    requirements,
    metCount: requirements.filter((row) => row.met).length,
    totalCount: requirements.length,
    allMet: passNow && missing.length === 0,
    skillMetCount: 0,
    skillTotalCount: 0,
    overallTone: passNow ? "ok" : "default",
    passMode: "process",
  };
}

export function hubExamAttempted(hub: MaturityHubPayload | null): boolean {
  if (!hub) return false;
  if (hub.runner_active || hub.active_phase) return true;
  if (phaseStartIncomplete(hub)) return true;
  if (hub.exit_eval?.ok) return true;
  const status = String(hub.focus_status || "");
  if (status === "failed" || status === "completed" || status === "running") return true;
  const learned = hub.focus_learned ?? {};
  const nB = asNumber(learned.n_b);
  const nP = asNumber(learned.n_p);
  const nA = asNumber(learned.n_a);
  const green = asNumber(learned.green_days);
  return (nB != null && nB > 0) || (nP != null && nP > 0) || (nA != null && nA > 0) || (green != null && green > 0);
}

export function resolveHubChecklist(hub: MaturityHubPayload | null): StagePassChecklist {
  const focus = hub?.focus_phase || hub?.next_phase || "awakening";
  const missing = hub?.exit_eval?.ok ? [] : [...(hub?.exit_eval?.missing ?? [])];
  const learned = hub?.focus_learned ?? {};
  const passNow = Boolean(hub?.exit_eval?.ok);
  const running = Boolean(hub?.runner_active || hub?.active_phase);
  const view = {
    pass_now: passNow,
    missing,
    learned,
    runner_active: running,
  };
  let list: StagePassChecklist;
  if (focus === "awakening") list = buildAwakeningChecklist(view);
  else if (focus === "playground") list = buildPlaygroundChecklist(view);
  else if (focus === "apprenticeship") list = buildApprenticeshipChecklist(view);
  else if (focus === "proving_ground") list = buildProvingGroundChecklist(view);
  else list = genericChecklist(focus, missing, passNow);

  const extras = extraMissingRows(missing, list);
  if (extras.length > 0) {
    list = {
      ...list,
      requirements: [...list.requirements, ...extras],
      totalCount: list.totalCount + extras.length,
      allMet: false,
    };
  }

  const idle = !hubExamAttempted(hub) && !passNow;
  if (idle) {
    list = {
      ...list,
      overallTone: "default",
      requirements: list.requirements.map((row) =>
        row.met
          ? row
          : {
              ...row,
              tone: "default",
              current: idleCurrent(row, hub),
              need:
                row.id === "birth_freeze_intact" && hub?.birth_exit_exited
                  ? "verified while the exam runs"
                  : row.need,
            },
      ),
    };
  }
  return list;
}

export function hubExamStatusLine(
  hub: MaturityHubPayload | null,
  opts: { running: boolean; retry: boolean },
): string {
  const focus = hub?.focus_phase || hub?.next_phase || "";
  const next = hub?.next_phase ?? null;
  const progress = hub?.progress_message?.trim() || "";
  if (opts.running) {
    return progress || `${proofPhase(focus)} clock is live. Exam AND-gates live on the ${proofPhase(focus)} mission.`;
  }
  if (hub?.exit_eval?.ok) {
    const nxt = next && next !== focus ? ` Next is ${proofPhase(next)}.` : "";
    return `${proofPhase(focus)} proofs are complete.${nxt} REAL stays human-gated.`;
  }
  if (opts.retry) {
    return `${proofPhase(focus)} did not pass. Open the ${proofPhase(focus)} mission for engine blockers. Floors stay fail-closed.`;
  }
  if (focus === "awakening") {
    return "Awakening has not started. Idle 0 / — / INCONCLUSIVE is not a failed exam. Start opens the exam contract.";
  }
  if (focus === "playground") {
    return "Playground has not started. School gate is five consecutive green session days. Idle zeros are not a fail.";
  }
  if (focus === "apprenticeship") {
    return "Apprenticeship has not started. This is the trading exam. Idle zeros are not a fail.";
  }
  if (focus === "proving_ground") {
    return "Proving Ground has not started. Cert 48% / 0.35 / 8% + this-clock shadow + PromotionGate. Idle zeros are not a fail.";
  }
  return progress || hub?.phase_specs?.[focus]?.human_goal || "Focus phase AND gates. REAL stays human-gated.";
}

function proofPhase(id: string): string {
  if (id === "awakening") return "Awakening";
  if (id === "playground") return "Playground";
  if (id === "apprenticeship") return "Apprenticeship";
  if (id === "proving_ground") return "Proving Ground";
  if (id === "birth") return "Birth";
  if (id === "real") return "REAL";
  return id ? id.replace(/_/g, " ") : "This phase";
}
