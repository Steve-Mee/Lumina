import type { BirthProgressPayload } from "@/lib/birthClient";

import type { StageScorecardHealth } from "@/lib/birth/birthStageScorecardTypes";

export const STALE_WORKING_SEC = 120;
const STALE_WARN_SEC = 600;

export function resolveAdaptationCycling(
  progress: BirthProgressPayload | undefined,
  heartbeatSec: number | null,
): boolean {
  if (!progress?.auto_recovery_active) return false;
  const tier = Math.max(0, Number(progress.adaptation_tier ?? 0));
  const maxTiers = Math.max(1, Number(progress.max_adaptation_tiers ?? 4));
  if (tier < maxTiers - 1) return false;
  if (heartbeatSec == null || heartbeatSec > STALE_WORKING_SEC) return false;
  // Raptor v13: do not flag cycling while sim is clearly producing trades.
  const tpm = Number(progress?.wall_clock_trades_per_min ?? 0);
  if (Number.isFinite(tpm) && tpm > 50) return false;
  const msg = String(progress?.message ?? progress?.sub_phase ?? "").toLowerCase();
  if (msg.includes("ppo batch") || msg.includes("ppo_training") || msg.includes("rollout")) {
    return false;
  }
  const evoRollouts = Number(progress?.plateau_evolution_rollouts_this_step ?? 0);
  if (Boolean(progress?.plateau_active) && evoRollouts > 0) return false;
  // Raptor v11: also flag when plateau is waiting for rollouts that never arrive.
  const awaitingRollouts = String(
    progress?.evolution_ladder_blocked_reason ?? "",
  )
    .toLowerCase()
    .startsWith("awaiting_rollouts");
  const plateauFrozen =
    Boolean(progress?.plateau_active) &&
    awaitingRollouts &&
    evoRollouts === 0;
  if (progress.is_advancing === true && !plateauFrozen) return false;
  return true;
}

export function resolveScorecardHealth(
  progress: BirthProgressPayload | undefined,
  heartbeatSec: number | null,
): { health: StageScorecardHealth; healthHint: string } {
  if (heartbeatSec == null) {
    return { health: "working", healthHint: "Waiting for progress update…" };
  }
  if (resolveAdaptationCycling(progress, heartbeatSec)) {
    return {
      health: "working",
      healthHint: "Recovery cycling — geen nieuwe trades",
    };
  }
  if (progress?.is_advancing === true && heartbeatSec <= STALE_WORKING_SEC) {
    return { health: "advancing", healthHint: "Progress advancing" };
  }
  if (heartbeatSec <= STALE_WORKING_SEC) {
    return {
      health: "working",
      healthHint: "Active — PPO batch may run silently (5–20 min is normal)",
    };
  }
  if (heartbeatSec <= STALE_WARN_SEC) {
    return {
      health: "working",
      healthHint: "No recent update — long PPO batch may still be running",
    };
  }
  return {
    health: "stale",
    healthHint: "Possible stall — check logs if metrics unchanged for 10+ min",
  };
}

export function metricPctForCriteria(
  passCriteriaId: string,
  metricValue: number | null,
  metricTarget: number | null,
  metricMin: number | null,
  metricMax: number | null,
): number {
  if (metricValue == null) return 0;
  // EdgeScore is already in [0,1]; do not normalize against hygiene 0.35.
  if (
    passCriteriaId === "trend_edgescore" ||
    passCriteriaId === "range_edgescore" ||
    passCriteriaId === "mixed_edgescore"
  ) {
    return Math.min(100, Math.max(0, metricValue * 100));
  }
  if (passCriteriaId === "trend_winrate" && metricTarget != null && metricTarget > 0) {
    return Math.min(100, (metricValue / metricTarget) * 100);
  }
  if (
    passCriteriaId === "range_edgescore" &&
    metricMin != null &&
    metricMax != null
  ) {
    if (metricValue >= metricMin && metricValue <= metricMax) return 100;
    return Math.min(100, Math.max(0, metricValue * 100));
  }
  if (passCriteriaId === "range_hold_ratio" && metricMin != null && metricMax != null) {
    if (metricValue >= metricMin && metricValue <= metricMax) return 100;
    if (metricValue < metricMin && metricMin > 0) {
      return Math.min(100, (metricValue / metricMin) * 100);
    }
    if (metricValue > metricMax && metricMax > 0) {
      return Math.max(0, 100 - ((metricValue - metricMax) / metricMax) * 100);
    }
  }
  if (passCriteriaId === "range_roundtrip" && metricMin != null && metricMax != null) {
    if (metricValue >= metricMin && metricValue <= metricMax) return 100;
    if (metricValue < metricMin && metricMin > 0) {
      return Math.min(100, (metricValue / metricMin) * 100);
    }
    if (metricValue > metricMax && metricMax > 0) {
      return Math.max(0, 100 - ((metricValue - metricMax) / metricMax) * 100);
    }
  }
  if (passCriteriaId === "mixed_constitution") {
    return metricValue <= 0 ? 100 : 0;
  }
  return 0;
}
