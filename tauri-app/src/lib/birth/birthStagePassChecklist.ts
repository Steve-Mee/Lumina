/**
 * Single-source stage pass checklist — gates vs skill diagnostics.
 *
 * Birth survival (ADR-0036): stage pass uses survival floors (e.g. WR ≥20%,
 * expectancy ≥ −50%). Skill floors (WR ≥35%, expectancy ≥ −15%) are maturation
 * targets — shown as "skill later", never as red fail gates.
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
  passMode: "survival" | "skill";
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

/** Survival Birth mode for stage-1 EdgeScore (backend birth_survival_pass_enabled). */
function isSurvivalStage1(id: string, scorecard: StageScorecardModel): boolean {
  if (id !== "trend_edgescore" && id !== "trend_winrate") return false;
  // Backend progress hygiene_wr_floor is survival 0.20 when survival mode is on.
  const floor = scorecard.hygieneWrFloor;
  if (floor != null && Number.isFinite(floor) && floor <= 0.25 + 1e-9) return true;
  // Default Birth: survival unless explicitly skill-gated elsewhere.
  return true;
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
    tone: met ? "ok" : tone === "default" ? "warn" : tone,
    met,
    kind: "gate",
  };
}

function hygieneGateReq(
  scorecard: StageScorecardModel,
  opts: { floor: number; label: string; id: string },
): StagePassRequirement {
  const { floor, label, id } = opts;
  const value = scorecard.hygieneWrEffective ?? scorecard.hygieneWrLifetime;
  const slope = scorecard.winrateTrendSlope;
  const met = value != null && value >= floor;
  const tone = resolveConditionTone({
    value,
    target: floor,
    direction: "higher",
    improving: slope == null ? null : slope > 0.00005,
    criticalGap: 0.08,
  });
  return {
    id,
    label,
    current: pct(value, 1),
    need: `≥ ${pct(floor, 0)} (life or roll)`,
    tone,
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

function holdBandReq(
  scorecard: StageScorecardModel,
  progress?: BirthProgressPayload,
): StagePassRequirement {
  const hold =
    scorecard.stageHoldRatio ??
    (progress?.stage_hold_ratio != null
      ? Number(progress.stage_hold_ratio)
      : progress?.hold_ratio != null
        ? Number(progress.hold_ratio)
        : null);
  const min = 0.05;
  const max = 0.85;
  const met = hold != null && hold >= min && hold <= max;
  const tone = resolveConditionTone({
    value: hold,
    min,
    max,
    direction: "band",
    criticalGap: 0.1,
  });
  return {
    id: "hold_band",
    label: "Hold band",
    current: pct(hold, 1),
    need: `${pct(min, 0)}–${pct(max, 0)} hold`,
    tone,
    met,
    kind: "gate",
  };
}

function flatBandReq(scorecard: StageScorecardModel): StagePassRequirement {
  const flat = scorecard.stageRangeFlatRatio;
  const min = scorecard.stageRangeFlatMin ?? 0.3;
  const max = scorecard.stageRangeFlatMax ?? 0.7;
  const met = flat != null && flat >= min && flat <= max;
  const tone = resolveConditionTone({
    value: flat,
    min,
    max,
    direction: "band",
    criticalGap: 0.15,
  });
  return {
    id: "flat_band",
    label: "Position flat",
    current: pct(flat, 1),
    need: `${pct(min, 0)}–${pct(max, 0)} flat`,
    tone,
    met,
    kind: "gate",
  };
}

function holdCapReq(scorecard: StageScorecardModel): StagePassRequirement {
  const hold = scorecard.stageHoldRatio;
  const max = scorecard.stageHoldMax ?? 0.7;
  const met = hold != null && hold <= max;
  const tone = resolveConditionTone({
    value: hold,
    max,
    direction: "lower",
    criticalGap: 0.15,
  });
  return {
    id: "hold_cap",
    label: "Hold ratio",
    current: pct(hold, 1),
    need: `≤ ${pct(max, 0)}`,
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

function expectancyGateReq(
  progress: BirthProgressPayload | undefined,
  opts: { floor: number; id: string; label: string },
): StagePassRequirement {
  const { floor, id, label } = opts;
  const value =
    progress?.expectancy_proxy != null && Number.isFinite(Number(progress.expectancy_proxy))
      ? Number(progress.expectancy_proxy)
      : null;
  const met = value != null && value >= floor;
  const tone = resolveConditionTone({
    value,
    target: floor,
    direction: "higher",
    criticalGap: 0.1,
  });
  const sign = value != null && value > 0 ? "+" : "";
  return {
    id,
    label,
    current: value == null ? "—" : `${sign}${(value * 100).toFixed(0)}%`,
    need: `≥ ${(floor * 100).toFixed(0)}% (WR−50%)`,
    tone,
    met,
    kind: "gate",
  };
}

function expectancySkillReq(progress?: BirthProgressPayload): StagePassRequirement {
  const value =
    progress?.expectancy_proxy != null && Number.isFinite(Number(progress.expectancy_proxy))
      ? Number(progress.expectancy_proxy)
      : null;
  const skillFloor = -0.15;
  const met = value != null && value >= skillFloor;
  const sign = value != null && value > 0 ? "+" : "";
  return {
    id: "expectancy_skill",
    label: "Skill expectancy (later)",
    current: value == null ? "—" : `${sign}${(value * 100).toFixed(0)}%`,
    need: `≥ ${(skillFloor * 100).toFixed(0)}% pro floor`,
    tone: skillTone(met),
    met,
    kind: "skill",
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

function missionForCriteria(id: string, survival: boolean): string {
  switch (id) {
    case "range_edgescore":
    case "range_hold_ratio":
    case "range_roundtrip":
      return "Range patience — clear volume, stay in the flat band, keep entropy alive. WR skill floors come later.";
    case "mixed_edgescore":
    case "mixed_foundation":
      return "Mixed regimes — volume, hygiene WR, hold under cap, entropy & expectancy healthy.";
    case "trend_edgescore":
    case "trend_winrate":
    default:
      return survival
        ? "Trend survival — volume, survival WR, hold band, entropy, survival expectancy. Pro skill targets are diagnostic only."
        : "Trend stage — volume, hygiene WR, hold band, entropy, expectancy skill floors.";
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

  const survivalS1 = isSurvivalStage1(id, scorecard);
  const requirements: StagePassRequirement[] = [];

  requirements.push(volumeReq(scorecard, progress));

  if (
    id === "trend_edgescore" ||
    id === "trend_winrate" ||
    id === "mixed_edgescore" ||
    id === "mixed_foundation"
  ) {
    if (survivalS1) {
      // Gate = survival floor (progress hygieneWrFloor often 0.20).
      const gateFloor =
        scorecard.hygieneWrFloor != null && scorecard.hygieneWrFloor <= 0.25
          ? scorecard.hygieneWrFloor
          : 0.2;
      requirements.push(
        hygieneGateReq(scorecard, {
          floor: gateFloor,
          label: "Survival WR",
          id: "hygiene",
        }),
      );
      requirements.push(
        hygieneSkillReq(scorecard, {
          skillFloor: 0.35,
          recommended: scorecard.stage1WinrateRecommended ?? 0.45,
        }),
      );
    } else {
      const floor = scorecard.hygieneWrFloor ?? 0.35;
      requirements.push(
        hygieneGateReq(scorecard, {
          floor,
          label: "Hygiene WR",
          id: "hygiene",
        }),
      );
    }
  }

  if (id === "trend_edgescore" || id === "trend_winrate") {
    requirements.push(holdBandReq(scorecard, progress));
  }

  if (id === "range_edgescore" || id === "range_hold_ratio" || id === "range_roundtrip") {
    requirements.push(flatBandReq(scorecard));
  }

  if (id === "mixed_edgescore" || id === "mixed_foundation") {
    requirements.push(holdCapReq(scorecard));
  }

  if (
    id === "trend_edgescore" ||
    id === "range_edgescore" ||
    id === "mixed_edgescore" ||
    id === "mixed_foundation" ||
    id === "trend_winrate"
  ) {
    requirements.push(entropyReq(progress));
    if (survivalS1) {
      requirements.push(
        expectancyGateReq(progress, {
          floor: -0.5,
          id: "expectancy",
          label: "Survival expectancy",
        }),
      );
      requirements.push(expectancySkillReq(progress));
    } else {
      // Range / mixed / non-survival trend: expectancy gate at skill floor (−15%).
      // (range_hold_ratio / range_roundtrip are handled via range_edgescore path only.)
      requirements.push(
        expectancyGateReq(progress, {
          floor: -0.15,
          id: "expectancy",
          label: "Expectancy",
        }),
      );
    }
    requirements.push(constitutionReq(progress));
  }

  if (requirements.length === 0) return null;

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
    stageTotal: 3,
    passCriteriaId: id,
    mission: missionForCriteria(id, survivalS1),
    requirements,
    metCount,
    totalCount,
    allMet,
    skillMetCount,
    skillTotalCount,
    overallTone,
    passMode: survivalS1 ? "survival" : "skill",
  };
}
