import type { BirthProgressPayload } from "@/lib/birthClient";

import { isBirthProgressPayloadActive } from "@/lib/birth/birthActiveProgress";
import { normalizeToken, parseProgressTimestamp } from "@/lib/birth/birthModelUtils";
import { extractStageScorecard } from "@/lib/birth/birthStageScorecard";

export interface BirthSessionHudModel {
  sessionStartedAtMs: number | null;
  sessionStartedLabel: string;
  patternsMined: number;
  learningAttempt: number;
  elapsedSec: number | null;
  preCurriculum: boolean;
  subPhaseLabel: string;
}

export function resolveBirthSessionStartedAtMs(
  progress: BirthProgressPayload | undefined,
): number | null {
  if (!progress) return null;
  const direct = Number(progress.birth_start_time ?? 0);
  if (direct > 0) {
    return direct > 1e12 ? direct : direct * 1000;
  }
  const ts = parseProgressTimestamp(progress);
  const elapsed = Number(progress.elapsed_sec ?? NaN);
  if (ts != null && Number.isFinite(elapsed) && elapsed > 0) {
    return ts - elapsed * 1000;
  }
  return null;
}

export function resolveLiveBirthElapsedSec(
  progress: BirthProgressPayload | undefined,
  statusElapsedSeconds?: number,
  nowMs: number = Date.now(),
): number | null {
  if (!progress) {
    return statusElapsedSeconds != null && statusElapsedSeconds >= 0
      ? Math.floor(statusElapsedSeconds)
      : null;
  }

  const startMs = resolveBirthSessionStartedAtMs(progress);
  const progressElapsed = Number(progress.elapsed_sec ?? NaN);
  const serverElapsed = Math.max(
    Number.isFinite(progressElapsed) && progressElapsed >= 0 ? progressElapsed : 0,
    statusElapsedSeconds != null && statusElapsedSeconds >= 0
      ? Math.floor(statusElapsedSeconds)
      : 0,
  );

  if (startMs != null) {
    const liveElapsed = Math.max(0, Math.floor((nowMs - startMs) / 1000));
    return Math.max(serverElapsed, liveElapsed);
  }

  return serverElapsed > 0 ? serverElapsed : null;
}

export function formatBirthSessionStartedLabel(startMs: number | null): string {
  if (startMs == null) return "syncing…";
  return new Intl.DateTimeFormat("nl-NL", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(startMs));
}


function resolveSessionSubPhaseLabel(progress: BirthProgressPayload): string {
  const explicit = String(progress.sub_phase_label ?? "").trim();
  if (explicit) return explicit;
  const phase = normalizeToken(progress.phase);
  if (phase === "loading_history") return "Historical data load";
  if (phase === "enriching_news") return "News enrichment";
  if (phase === "enriching_regimes") return "Regime map";
  if (phase === "train_holdout_split") return "Train/holdout split";
  if (phase === "holdout_preflight" || phase === "holdout_preflight_expansion") {
    return "Holdout preflight";
  }
  if (phase === "policy_init" || phase === "ticks_ready") return "Policy init";
  const message = String(progress.message ?? "").trim();
  if (message) return message.length > 96 ? `${message.slice(0, 93)}…` : message;
  return String(progress.phase ?? progress.stage ?? "Birth preparation").replace(/_/g, " ");
}

export function extractBirthSessionHud(
  progress: BirthProgressPayload | undefined,
): BirthSessionHudModel | null {
  if (!isBirthProgressPayloadActive(progress) || !progress) {
    return null;
  }
  const scorecard = extractStageScorecard(progress);
  const curriculumStage = String(progress.curriculum_stage ?? "").trim();
  const startMs = resolveBirthSessionStartedAtMs(progress);
  const elapsedRaw = Number(progress.elapsed_sec ?? NaN);
  const patternsFromProgress = Math.max(0, Number(progress.patterns_mined ?? 0));
  const patternsFromScorecard = Math.max(0, Number(scorecard?.patternsMined ?? 0));
  const attemptFromProgress = Math.max(0, Number(progress.learning_attempt ?? 0));
  const attemptFromScorecard = Math.max(0, Number(scorecard?.learningAttempt ?? 0));
  return {
    sessionStartedAtMs: startMs,
    sessionStartedLabel: formatBirthSessionStartedLabel(startMs),
    patternsMined: Math.max(patternsFromProgress, patternsFromScorecard),
    learningAttempt: Math.max(attemptFromProgress, attemptFromScorecard),
    elapsedSec: Number.isFinite(elapsedRaw) && elapsedRaw >= 0 ? elapsedRaw : null,
    preCurriculum: !curriculumStage,
    subPhaseLabel: resolveSessionSubPhaseLabel(progress),
  };
}
