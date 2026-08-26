import type { BirthProgressPayload } from "@/lib/birthClient";

import { isBirthCurriculumScorecardActive } from "@/lib/birth/birthActiveProgress";
import {
  extractAdaptationFields,
  extractScorecardProgressExtras,
} from "@/lib/birth/birthStageScorecardAdaptation";
import { inferPassCriteriaFromStage } from "@/lib/birth/birthStageScorecardCriteria";
import { humanizeEdgescoreBlockerDetail } from "@/lib/birth/birthStageScorecardEdgescore";
import {
  metricPctForCriteria,
  resolveAdaptationCycling,
  resolveScorecardHealth,
} from "@/lib/birth/birthStageScorecardHealth";
import type { StageScorecardModel } from "@/lib/birth/birthStageScorecardTypes";
import { normalizeToken, parseProgressTimestamp } from "@/lib/birth/birthModelUtils";
import { extractSimProgress } from "@/lib/birth/birthProgressExtract";

export type { StageScorecardHealth, StageScorecardModel } from "@/lib/birth/birthStageScorecardTypes";
export {
  isRawEdgescorePassReason,
  humanizeEdgescoreBlockerDetail,
  presentBlockerDetail,
} from "@/lib/birth/birthStageScorecardEdgescore";

/** Engine `stage_pass_now` is the only green light. Volume-only is never pass. */
export function isStageGoalMet(scorecard: StageScorecardModel): boolean {
  if (scorecard.blockerDetail) return false;
  return scorecard.stagePassNow === true;
}

export function extractStageScorecard(
  progress: BirthProgressPayload | undefined,
  nowMs: number = Date.now(),
): StageScorecardModel | null {
  // Elon gate: never show Stage 1/5 cards during historical load / enrich / ticks_ready.
  // curriculum_stage is often pre-stamped before curriculum actually starts.
  if (!isBirthCurriculumScorecardActive(progress)) {
    return null;
  }

  const curriculumStage = String(progress?.curriculum_stage ?? "").trim();
  const phase = normalizeToken(progress?.phase);
  const isCurriculum =
    Boolean(curriculumStage) &&
    !["completed", "practice_completed"].includes(phase);
  const isPolishOrOos = phase === "ppo_polish" || phase === "oos_evaluation";
  if (!isCurriculum && !isPolishOrOos) {
    return null;
  }

  const sim = extractSimProgress(progress);
  const inferred = curriculumStage
    ? inferPassCriteriaFromStage(curriculumStage, sim.target || 100)
    : null;

  const curriculumIndex = Number(
    progress?.curriculum_index ?? inferred?.curriculumIndex ?? 0,
  );
  const curriculumTotal = Number(progress?.curriculum_total ?? 5);
  const displayName =
    String(progress?.stage_display_name ?? "").trim() ||
    inferred?.displayName ||
    curriculumStage.replace(/_/g, " ");
  const stageLabel =
    curriculumIndex > 0 && curriculumIndex <= curriculumTotal
      ? `Stage ${curriculumIndex}/${curriculumTotal} · ${displayName}`
      : displayName;

  const passCriteriaId = String(
    progress?.pass_criteria_id ?? inferred?.id ?? "closed_loop",
  );
  const goalLabelRaw =
    String(progress?.pass_criteria_label ?? "").trim() ||
    inferred?.goalLabel ||
    "";
  const goalLabel =
    goalLabelRaw
      .replace(/\u00b7/g, "|")
      .replace(/\u2014/g, "-")
      .replace(/\u2265/g, ">=")
      .replace(/\s*\|\s*/g, " | ")
      .trim() ||
    `>=${sim.target} trades | median loss R | occupancy | edge vs first-touch`;

  let metricValue: number | null = null;
  let metricLabel = String(
    progress?.pass_metric_label ?? inferred?.metricLabel ?? "Median loss R",
  );
  // EdgeScore pass is composite — never treat hygiene 0.35 as an EdgeScore score target.
  const metricTarget =
    passCriteriaId === "trend_edgescore" ||
    passCriteriaId === "range_edgescore" ||
    passCriteriaId === "mixed_edgescore"
      ? null
      : progress?.pass_metric_target != null
        ? Number(progress.pass_metric_target)
        : inferred?.metricTarget ?? null;
  const metricMin =
    progress?.pass_metric_min != null
      ? Number(progress.pass_metric_min)
      : inferred?.metricMin ?? null;
  const metricMax =
    progress?.pass_metric_max != null
      ? Number(progress.pass_metric_max)
      : inferred?.metricMax ?? null;

  if (
    passCriteriaId === "trend_edgescore" ||
    passCriteriaId === "range_edgescore" ||
    passCriteriaId === "mixed_edgescore"
  ) {
    if (progress?.edgescore != null && Number.isFinite(Number(progress.edgescore))) {
      metricValue = Number(progress.edgescore);
      metricLabel = "EdgeScore";
    } else if (progress?.stage_winrate != null && Number.isFinite(Number(progress.stage_winrate))) {
      // Fallback hygiene WR until edgescore arrives in progress.
      metricValue = Number(progress.stage_winrate);
      metricLabel = "Hygiene WR";
    } else if (
      progress?.stage_wins !== undefined &&
      progress?.stage_wins !== null &&
      sim.done > 0
    ) {
      metricValue = Number(progress.stage_wins) / sim.done;
      metricLabel = "Hygiene WR";
    }
  } else if (passCriteriaId === "trend_winrate") {
    if (progress?.stage_winrate != null && Number.isFinite(Number(progress.stage_winrate))) {
      metricValue = Number(progress.stage_winrate);
    } else if (
      progress?.stage_wins !== undefined &&
      progress?.stage_wins !== null &&
      sim.done > 0
    ) {
      metricValue = Number(progress.stage_wins) / sim.done;
    }
  } else if (passCriteriaId === "range_hold_ratio") {
    metricValue =
      progress?.stage_hold_ratio != null
        ? Number(progress.stage_hold_ratio)
        : progress?.hold_ratio != null
          ? Number(progress.hold_ratio)
          : null;
  } else if (passCriteriaId === "range_roundtrip") {
    metricValue =
      progress?.stage_range_flat_ratio != null
        ? Number(progress.stage_range_flat_ratio)
        : progress?.stage_hold_ratio != null
          ? Number(progress.stage_hold_ratio)
          : progress?.hold_ratio != null
            ? Number(progress.hold_ratio)
            : null;
  } else if (passCriteriaId === "mixed_constitution") {
    const sessionViolations = progress?.constitution_violations_session;
    metricValue = Number(
      sessionViolations != null && Number.isFinite(Number(sessionViolations))
        ? sessionViolations
        : progress?.constitution_violations ?? 0,
    );
    metricLabel = "Violations (session)";
  } else if (passCriteriaId === "mixed_foundation") {
    // Raptor v7/v8: Mixed winrate is lifetime stage WR (not rolling).
    if (progress?.stage_winrate != null && Number.isFinite(Number(progress.stage_winrate))) {
      metricValue = Number(progress.stage_winrate);
    } else if (
      progress?.stage_wins !== undefined &&
      progress?.stage_wins !== null &&
      sim.done > 0
    ) {
      metricValue = Number(progress.stage_wins) / sim.done;
    }
    metricLabel = "Mixed winrate (lifetime)";
  } else if (passCriteriaId === "selectivity") {
    if (progress?.occupancy != null && Number.isFinite(Number(progress.occupancy))) {
      metricValue = Number(progress.occupancy);
    } else if (
      progress?.stage_range_flat_ratio != null &&
      Number.isFinite(Number(progress.stage_range_flat_ratio))
    ) {
      metricValue = Number(progress.stage_range_flat_ratio);
    }
  } else if (
    passCriteriaId === "mixed_regimes" ||
    passCriteriaId === "viable_plant" ||
    passCriteriaId === "probe_handoff"
  ) {
    if (
      progress?.edge_vs_first_touch != null &&
      Number.isFinite(Number(progress.edge_vs_first_touch))
    ) {
      metricValue = Number(progress.edge_vs_first_touch);
    }
  } else if (passCriteriaId === "closed_loop") {
    if (progress?.median_loss_r != null && Number.isFinite(Number(progress.median_loss_r))) {
      metricValue = Number(progress.median_loss_r);
    }
  }

  const stageHoldRatio =
    progress?.stage_hold_ratio != null && Number.isFinite(Number(progress.stage_hold_ratio))
      ? Number(progress.stage_hold_ratio)
      : progress?.hold_ratio != null && Number.isFinite(Number(progress.hold_ratio))
        ? Number(progress.hold_ratio)
        : null;
  // Stage-2/3 occupancy: position flat band. Stage-3 uses 25–75% mixed.
  const isOccupancyActivity =
    passCriteriaId === "range_edgescore" ||
    passCriteriaId === "range_hold_ratio" ||
    passCriteriaId === "range_roundtrip" ||
    passCriteriaId === "mixed_edgescore" ||
    passCriteriaId === "mixed_foundation" ||
    passCriteriaId === "selectivity" ||
    passCriteriaId === "mixed_regimes" ||
    passCriteriaId === "viable_plant" ||
    passCriteriaId === "probe_handoff";
  const isStage3Occupancy =
    passCriteriaId === "mixed_edgescore" ||
    passCriteriaId === "mixed_foundation" ||
    passCriteriaId === "mixed_regimes" ||
    passCriteriaId === "viable_plant" ||
    passCriteriaId === "probe_handoff";
  const stageRangeFlatRatio = isOccupancyActivity
    ? progress?.stage_range_flat_ratio != null &&
      Number.isFinite(Number(progress.stage_range_flat_ratio))
      ? Number(progress.stage_range_flat_ratio)
      : stageHoldRatio
    : null;
  const stageRangeFlatMin = isOccupancyActivity ? (isStage3Occupancy ? 0.25 : 0.3) : null;
  const stageRangeFlatMax = isOccupancyActivity ? (isStage3Occupancy ? 0.75 : 0.7) : null;
  const stageHoldMax = null;

  const ts = parseProgressTimestamp(progress);
  const heartbeatSec = ts != null ? Math.max(0, Math.round((nowMs - ts) / 1000)) : null;
  const { health, healthHint } = resolveScorecardHealth(progress, heartbeatSec);
  const adaptationCycling = resolveAdaptationCycling(progress, heartbeatSec);
  const manifestDaysRaw = progress?.data_manifest?.days_loaded;
  const dataManifestDaysLoaded =
    manifestDaysRaw != null && Number.isFinite(Number(manifestDaysRaw))
      ? Math.max(0, Number(manifestDaysRaw))
      : null;

  const tradesTargetMet = sim.target > 0 && sim.done >= sim.target;
  let blockerLabel: string | null = null;
  let blockerDetail: string | null = null;
  if (tradesTargetMet) {
    const blockerMetric = String(progress?.stage_blocker_metric ?? "").trim();
    const passReason = String(progress?.pass_reason ?? "").trim();
    if (passReason) {
      blockerDetail = humanizeEdgescoreBlockerDetail(progress, passReason);
      blockerLabel = "Blocking metric";
    } else if (
      (passCriteriaId === "trend_edgescore" ||
        passCriteriaId === "range_edgescore" ||
        passCriteriaId === "mixed_edgescore") &&
      metricValue != null
    ) {
      // Frontend fallback only when entropy life-support is visibly failing.
      const entropyMissing =
        progress?.entropy_alive === false &&
        (progress?.policy_entropy == null || !Number.isFinite(progress.policy_entropy));
      const entropyDead =
        progress?.entropy_alive === false &&
        progress?.policy_entropy != null &&
        Number.isFinite(progress.policy_entropy);
      if (entropyMissing || entropyDead) {
        blockerLabel = "EdgeScore";
        blockerDetail = entropyMissing
          ? `Entropy missing | EdgeScore ${(metricValue * 100).toFixed(0)}%`
          : `Entropy dead | EdgeScore ${(metricValue * 100).toFixed(0)}%`;
      }
    } else if (passCriteriaId === "trend_winrate" && metricValue != null && metricTarget != null) {
      if (metricValue < metricTarget) {
        blockerLabel = "Winrate";
        blockerDetail = `${(metricValue * 100).toFixed(0)}% - need ${(metricTarget * 100).toFixed(0)}%`;
      }
    } else if (blockerMetric) {
      blockerLabel = blockerMetric.replace(/_/g, " ");
      if (progress?.stage_blocker_value != null) {
        blockerDetail = String(progress.stage_blocker_value);
      }
    }
  }

  return {
    stageLabel,
    goalLabel,
    tradesDone: sim.done,
    tradesRequired: sim.target,
    tradesPct: sim.pct,
    metricLabel,
    metricValue,
    metricTarget,
    metricMin,
    metricMax,
    metricPct: metricPctForCriteria(
      passCriteriaId,
      metricValue,
      metricTarget,
      metricMin,
      metricMax,
    ),
    passCriteriaId,
    subPhase: String(progress?.sub_phase ?? progress?.phase ?? ""),
    subPhaseLabel:
      String(progress?.sub_phase_label ?? "").trim() ||
      String(progress?.phase ?? "").replace(/_/g, " "),
    patternsMined: Number(progress?.patterns_mined ?? 0),
    learningAttempt: Number(progress?.learning_attempt ?? 0),
    explorationActive: Boolean(progress?.exploration_active),
    stageWallRemainingSec:
      progress?.stage_wall_remaining_sec != null
        ? Math.max(0, Number(progress.stage_wall_remaining_sec))
        : null,
    stageRangeRoundTrips:
      progress?.stage_range_round_trips != null
        ? Math.max(0, Number(progress.stage_range_round_trips))
        : null,
    heartbeatSec,
    health,
    healthHint,
    isCurriculum,
    blockerLabel,
    blockerDetail,
    provisionalPass: Boolean(progress?.provisional_pass),
    stagePassNow: Boolean(progress?.stage_pass_now),
    medianLossR:
      progress?.median_loss_r != null && Number.isFinite(Number(progress.median_loss_r))
        ? Number(progress.median_loss_r)
        : null,
    meanR:
      progress?.mean_r != null && Number.isFinite(Number(progress.mean_r))
        ? Number(progress.mean_r)
        : null,
    occupancy:
      progress?.occupancy != null && Number.isFinite(Number(progress.occupancy))
        ? Number(progress.occupancy)
        : null,
    edgeVsFirstTouch:
      progress?.edge_vs_first_touch != null &&
      Number.isFinite(Number(progress.edge_vs_first_touch))
        ? Number(progress.edge_vs_first_touch)
        : null,
    ...extractAdaptationFields(progress),
    ...extractScorecardProgressExtras(progress, {
      adaptationCycling,
      dataManifestDaysLoaded,
      stageHoldRatio,
      stageHoldMax,
      stageRangeFlatRatio,
      stageRangeFlatMin,
      stageRangeFlatMax,
    }),
  };
}
