/**
 * Stage pass checklist — HUD must match engine `evaluate_foundation_pass`.
 *
 * Gates are process-R, occupancy, settlement, first-touch edge — never WR 20/35/40.
 * Rolling WR is diagnostic only. If HUD ≠ engine, HUD is wrong.
 */

import type { BirthProgressPayload } from "@/lib/birthClient";
import type { StageScorecardModel } from "@/lib/birth/birthStageScorecardTypes";
import {
  resolveBooleanConditionTone,
  resolveConditionTone,
  type ConditionTone,
} from "@/lib/conditionTone";

/** gate = must clear to pass stage; skill = diagnostic / later maturation */
export type StageRequirementKind = "gate" | "skill";

/** Compound instrument rows (Life / Roll / Windows) — stacked in narrow cards. */
export interface StagePassStat {
  key: string;
  value: string;
  note?: string;
}

export interface StagePassRequirement {
  id: string;
  label: string;
  /** Current readout, e.g. "46%" or "alive" */
  current: string;
  /** Target readout, e.g. "≥ 35%" or "30–70%" */
  need: string;
  tone: ConditionTone;
  met: boolean;
  kind: StageRequirementKind;
  /** When set, the card stacks these instead of the long `current` string. */
  stats?: StagePassStat[];
}

export interface StagePassChecklist {
  stageTitle: string;
  stageIndex: number | null;
  stageTotal: number | null;
  passCriteriaId: string;
  /** Short mission line */
  mission: string;
  requirements: StagePassRequirement[];
  /** Gate rows only */
  metCount: number;
  totalCount: number;
  allMet: boolean;
  /** Skill diagnostics met/total (optional operator awareness) */
  skillMetCount: number;
  skillTotalCount: number;
  /** Overall card tone from worst open *gate* only */
  overallTone: ConditionTone;
  passMode: "process" | "skill";
}

function pct(v: number | null | undefined, digits = 0): string {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  return `${(Number(v) * 100).toFixed(digits)}%`;
}

function num(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  return Number(v).toLocaleString();
}

function worstTone(tones: ConditionTone[]): ConditionTone {
  if (tones.includes("danger")) return "danger";
  if (tones.includes("warn")) return "warn";
  if (tones.every((t) => t === "ok") && tones.length > 0) return "ok";
  return "default";
}

/** Never paint a gate green unless it actually passed (PID 33628 sticky durable). */
function gateTone(met: boolean, scored: ConditionTone): ConditionTone {
  if (met) return "ok";
  if (scored === "ok" || scored === "default") return "warn";
  return scored;
}

function skillTone(met: boolean): ConditionTone {
  return met ? "ok" : "accent";
}

function volumeReq(
  scorecard: StageScorecardModel,
  progress?: BirthProgressPayload,
): StagePassRequirement {
  const done = scorecard.tradesDone ?? progress?.stage_trades ?? 0;
  const gate =
    scorecard.stagePassGateTrades ??
    progress?.stage_pass_gate_trades ??
    scorecard.tradesRequired ??
    0;
  const met = gate <= 0 || done >= gate;
  const tone = resolveConditionTone({
    value: done,
    target: gate > 0 ? gate : null,
    direction: "higher",
    improving: !met && done > 0 ? true : null,
    criticalGap: Math.max(1, gate * 0.5),
  });
  return {
    id: "volume",
    label: "Stage volume",
    current: gate > 0 ? `${num(done)} / ${num(gate)}` : num(done),
    need: gate > 0 ? `≥ ${num(gate)} trades` : "any trades",
    tone: gateTone(met, tone),
    met,
    kind: "gate",
  };
}

function hygieneSkillReq(
  scorecard: StageScorecardModel,
  opts: { skillFloor: number; recommended?: number | null },
): StagePassRequirement {
  const { skillFloor, recommended } = opts;
  const value = scorecard.hygieneWrEffective ?? scorecard.hygieneWrLifetime;
  const met = value != null && value >= skillFloor;
  const rec =
    recommended != null && Number.isFinite(recommended)
      ? ` · rec ${pct(recommended, 0)}`
      : "";
  return {
    id: "hygiene_skill",
    label: "Skill WR (later)",
    current: pct(value, 1),
    need: `≥ ${pct(skillFloor, 0)} pro floor${rec}`,
    tone: skillTone(met),
    met,
    kind: "skill",
  };
}


/** Match backend evaluate_settlement_honesty / settlement_progress_fields. */
function settlementShareFromProgress(
  progress?: BirthProgressPayload,
): number | null {
  const direct = progress?.stage_settlement_share;
  if (direct != null && Number.isFinite(Number(direct)) && Number(direct) >= 0) {
    return Number(direct);
  }
  const stop = Number(progress?.stage_closes_stop_cum ?? 0);
  const target = Number(progress?.stage_closes_target_cum ?? 0);
  const timeStop = Number(progress?.stage_closes_time_stop_cum ?? 0);
  const flatten = Number(progress?.stage_closes_flatten_cum ?? 0);
  const unknown = Number(progress?.stage_closes_unknown_cum ?? 0);
  if (![stop, target, timeStop, flatten, unknown].every((n) => Number.isFinite(n))) {
    return null;
  }
  const decisive = Math.max(0, stop) + Math.max(0, target) + Math.max(0, timeStop);
  const total = decisive + Math.max(0, flatten) + Math.max(0, unknown);
  if (total <= 0) return null;
  return decisive / total;
}

function settlementReq(progress?: BirthProgressPayload): StagePassRequirement {
  const share = settlementShareFromProgress(progress);
  const target = 0.7;
  const met = share != null && share >= target;
  const tone = resolveConditionTone({
    value: share,
    target,
    direction: "higher",
    criticalGap: 0.2,
  });
  return {
    id: "settlement",
    label: "Settlement honesty",
    current: pct(share, 0),
    need: "≥ 70% stop/target/time-stop",
    tone,
    met,
    kind: "gate",
  };
}

function entropyReq(progress?: BirthProgressPayload): StagePassRequirement {
  const alive = progress?.entropy_alive;
  const entropy = progress?.policy_entropy;
  const missing =
    alive === false && (entropy == null || !Number.isFinite(Number(entropy)));
  const met = alive === true;
  let tone = resolveBooleanConditionTone(alive);
  if (missing) tone = "warn";
  return {
    id: "entropy",
    label: "Entropy",
    current:
      missing
        ? "missing"
        : alive === false
          ? "dead"
          : alive === true
            ? entropy != null && Number.isFinite(Number(entropy))
              ? `alive (H=${Number(entropy).toFixed(2)})`
              : "alive"
            : "—",
    need: "alive (exploring)",
    tone,
    met,
    kind: "gate",
  };
}

function constitutionReq(progress?: BirthProgressPayload): StagePassRequirement {
  const v = Number(progress?.constitution_violations ?? 0);
  const met = v <= 0;
  return {
    id: "constitution",
    label: "Constitution",
    current: met ? "0 fatal" : `${v} violation(s)`,
    need: "0 fatal",
    tone: met ? "ok" : "danger",
    met,
    kind: "gate",
  };
}

function finiteOrNull(
  ...candidates: Array<number | null | undefined>
): number | null {
  for (const v of candidates) {
    if (v != null && Number.isFinite(Number(v))) return Number(v);
  }
  return null;
}

function processRReq(
  scorecard: StageScorecardModel,
  progress?: BirthProgressPayload,
): StagePassRequirement {
  const v = finiteOrNull(scorecard.medianLossR, progress?.median_loss_r);
  const maxR = 1.5;
  const met = v != null && v <= maxR + 1e-12;
  const tone = resolveConditionTone({
    value: v,
    target: maxR,
    direction: "lower",
    criticalGap: 0.5,
  });
  return {
    id: "process_r",
    label: "Process-R (median loss)",
    current: v == null ? "—" : `${v.toFixed(2)}R`,
    need: `≤ ${maxR}R`,
    tone: gateTone(met, tone),
    met,
    kind: "gate",
  };
}

function occupancyReq(
  scorecard: StageScorecardModel,
  progress?: BirthProgressPayload,
  lo = 0.3,
  hi = 0.7,
): StagePassRequirement {
  const occ = finiteOrNull(
    scorecard.occupancy,
    progress?.occupancy,
    scorecard.stageRangeFlatRatio,
  );
  const min = scorecard.stageRangeFlatMin ?? lo;
  const max = scorecard.stageRangeFlatMax ?? hi;
  const met = occ != null && occ >= min - 1e-12 && occ <= max + 1e-12;
  const tone = resolveConditionTone({
    value: occ,
    min,
    max,
    direction: "band",
    criticalGap: 0.15,
  });
  return {
    id: "occupancy",
    label: "Occupancy",
    current: pct(occ, 0),
    need: `${pct(min, 0)}–${pct(max, 0)} flat`,
    tone: gateTone(met, tone),
    met,
    kind: "gate",
  };
}

function edgeReq(
  scorecard: StageScorecardModel,
  progress: BirthProgressPayload | undefined,
  floor: number,
  label: string,
): StagePassRequirement {
  const v = finiteOrNull(scorecard.edgeVsFirstTouch, progress?.edge_vs_first_touch);
  const met = v != null && v + 1e-12 >= floor;
  const tone = resolveConditionTone({
    value: v,
    target: floor,
    direction: "higher",
    criticalGap: 0.05,
  });
  const pp = v == null ? "—" : `${(v * 100).toFixed(1)}pp`;
  return {
    id: "edge",
    label,
    current: pp,
    need: `≥ ${(floor * 100).toFixed(0)}pp vs first-touch`,
    tone: gateTone(met, tone),
    met,
    kind: "gate",
  };
}

function netRrReq(progress?: BirthProgressPayload): StagePassRequirement {
  const v = finiteOrNull(
    progress?.geometry_net_rr,
    progress?.geometry_net_rr_after_cost,
  );
  const floor = 0.8;
  const met = v != null && v + 1e-12 >= floor;
  const tone = resolveConditionTone({
    value: v,
    target: floor,
    direction: "higher",
    criticalGap: 0.2,
  });
  return {
    id: "net_rr",
    label: "Geometry net RR",
    current: v == null ? "—" : v.toFixed(2),
    need: `≥ ${floor.toFixed(2)}`,
    tone: gateTone(met, tone),
    met,
    kind: "gate",
  };
}

function meanRVsMechReq(
  scorecard: StageScorecardModel,
  progress?: BirthProgressPayload,
): StagePassRequirement {
  const meanR = finiteOrNull(scorecard.meanR, progress?.mean_r);
  const eMech = finiteOrNull(progress?.e_mech);
  const slack = 0.1;
  const met =
    meanR != null && eMech != null && meanR + 1e-12 >= eMech - slack;
  const need = eMech == null ? "E_mech − 0.10" : `≥ ${(eMech - slack).toFixed(2)}R`;
  return {
    id: "mean_r",
    label: "Mean R vs mechanical",
    current: meanR == null ? "—" : `${meanR.toFixed(2)}R`,
    need,
    tone: met ? "ok" : meanR == null || eMech == null ? "warn" : "danger",
    met,
    kind: "gate",
  };
}

function roundTripsReq(
  scorecard: StageScorecardModel,
  progress?: BirthProgressPayload,
): StagePassRequirement {
  const done = finiteOrNull(
    scorecard.stageRangeRoundTrips,
    progress?.stage_range_round_trips,
  );
  const gate = scorecard.stagePassGateTrades ?? scorecard.tradesRequired ?? 250;
  const need = Math.max(3, Math.floor(gate / 10));
  const met = done != null && done >= need;
  return {
    id: "round_trips",
    label: "Round-trips",
    current: done == null ? "—" : num(done),
    need: `≥ ${num(need)}`,
    tone: met ? "ok" : "warn",
    met,
    kind: "gate",
  };
}

function sharpeReq(progress?: BirthProgressPayload): StagePassRequirement {
  const v = finiteOrNull(progress?.oos_sharpe);
  const floor = -2;
  const met = v != null && v > floor;
  return {
    id: "oos_sharpe",
    label: "Holdout Sharpe",
    current: v == null ? "—" : v.toFixed(2),
    need: `> ${floor}`,
    tone: met ? "ok" : v == null ? "warn" : "danger",
    met,
    kind: "gate",
  };
}

function ddReq(progress?: BirthProgressPayload): StagePassRequirement {
  const v = finiteOrNull(progress?.oos_dd_pct);
  const maxDd = 25;
  const met = v != null && v <= maxDd + 1e-12;
  return {
    id: "oos_dd",
    label: "Holdout drawdown",
    current: v == null ? "—" : `${v.toFixed(1)}%`,
    need: `≤ ${maxDd}% on $50k`,
    tone: met ? "ok" : v == null ? "warn" : "danger",
    met,
    kind: "gate",
  };
}

type FoundationFamily = "s1" | "s2" | "s3" | "s4" | "s5";

function foundationFamily(id: string): FoundationFamily | null {
  if (id === "closed_loop" || id === "trend_edgescore" || id === "trend_winrate") {
    return "s1";
  }
  if (
    id === "selectivity" ||
    id === "range_edgescore" ||
    id === "range_hold_ratio" ||
    id === "range_roundtrip"
  ) {
    return "s2";
  }
  if (id === "mixed_regimes" || id === "mixed_edgescore" || id === "mixed_foundation") {
    return "s3";
  }
  if (id === "viable_plant") return "s4";
  if (id === "probe_handoff") return "s5";
  return null;
}

function missionForFamily(family: FoundationFamily): string {
  switch (family) {
    case "s1":
      return "Closed loop — volume, median loss R ≤ 1.5, settlement ≥70%, entropy alive, constitution 0, net RR ≥ 0.80. WR is not a pass gate.";
    case "s2":
      return "Selectivity — volume, occupancy 30–70%, round-trips, settlement, constitution 0, median loss R ≤ 1.5. WR is not a pass gate.";
    case "s3":
      return "Mixed regimes — volume, occupancy 25–75%, settlement, constitution 0, median loss R ≤ 1.5, edge ≥ −5pp vs first-touch.";
    case "s4":
      return "Viable plant — skill WR ≥ first-touch AND mean R ≥ E_mech−0.10, occupancy 25–75%, process-R.";
    case "s5":
      return "Probe & handoff — holdout edge ≥ −3pp, Sharpe > −2, DD ≤ 25% on $50k. Fitness vector is the exit checksum.";
  }
}

/**
 * Build the pass checklist for the current curriculum stage.
 * Returns null when there is no scored stage goal (polish-only / empty).
 */
export function buildStagePassChecklist(
  scorecard: StageScorecardModel | null | undefined,
  progress?: BirthProgressPayload,
): StagePassChecklist | null {
  if (!scorecard) return null;
  const id = String(scorecard.passCriteriaId ?? "");
  if (!id || id === "polish_complete") return null;

  const family = foundationFamily(id);
  if (family == null) return null;

  const requirements: StagePassRequirement[] = [volumeReq(scorecard, progress)];
  if (family === "s1") {
    requirements.push(processRReq(scorecard, progress));
    requirements.push(settlementReq(progress));
    requirements.push(entropyReq(progress));
    requirements.push(constitutionReq(progress));
    requirements.push(netRrReq(progress));
  } else if (family === "s2") {
    requirements.push(occupancyReq(scorecard, progress, 0.3, 0.7));
    requirements.push(roundTripsReq(scorecard, progress));
    requirements.push(settlementReq(progress));
    requirements.push(constitutionReq(progress));
    requirements.push(processRReq(scorecard, progress));
  } else if (family === "s3") {
    requirements.push(occupancyReq(scorecard, progress, 0.25, 0.75));
    requirements.push(settlementReq(progress));
    requirements.push(constitutionReq(progress));
    requirements.push(processRReq(scorecard, progress));
    requirements.push(edgeReq(scorecard, progress, -0.05, "Edge vs first-touch"));
  } else if (family === "s4") {
    requirements.push(occupancyReq(scorecard, progress, 0.25, 0.75));
    requirements.push(settlementReq(progress));
    requirements.push(constitutionReq(progress));
    requirements.push(processRReq(scorecard, progress));
    requirements.push(edgeReq(scorecard, progress, 0, "Skill ≥ first-touch"));
    requirements.push(meanRVsMechReq(scorecard, progress));
  } else {
    requirements.push(occupancyReq(scorecard, progress, 0.25, 0.75));
    requirements.push(processRReq(scorecard, progress));
    requirements.push(edgeReq(scorecard, progress, -0.03, "Holdout edge"));
    requirements.push(sharpeReq(progress));
    requirements.push(ddReq(progress));
  }

  requirements.push(
    hygieneSkillReq(scorecard, {
      skillFloor: 0.35,
      recommended: scorecard.stage1WinrateRecommended ?? 0.45,
    }),
  );

  const gates = requirements.filter((r) => r.kind === "gate");
  const skills = requirements.filter((r) => r.kind === "skill");
  const metCount = gates.filter((r) => r.met).length;
  const totalCount = gates.length;
  const allMet = totalCount > 0 && metCount === totalCount;
  const skillMetCount = skills.filter((r) => r.met).length;
  const skillTotalCount = skills.length;
  const openGateTones = gates.filter((r) => !r.met).map((r) => r.tone);
  const overallTone: ConditionTone = allMet
    ? "ok"
    : worstTone(openGateTones.length ? openGateTones : gates.map((r) => r.tone));

  const stageIndex =
    scorecard.stageLabel.match(/Stage\s+(\d+)/i)?.[1] != null
      ? Number(scorecard.stageLabel.match(/Stage\s+(\d+)/i)?.[1])
      : null;

  return {
    stageTitle: scorecard.stageLabel,
    stageIndex,
    stageTotal: 5,
    passCriteriaId: id,
    mission: missionForFamily(family),
    requirements,
    metCount,
    totalCount,
    allMet,
    skillMetCount,
    skillTotalCount,
    overallTone,
    passMode: family === "s4" || family === "s5" ? "skill" : "process",
  };
}
