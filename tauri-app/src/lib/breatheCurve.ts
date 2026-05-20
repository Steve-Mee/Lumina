import type { TradingMode } from "@/store/coreStore";

/** Shared organism breathe timing (seconds per full cycle). */
export const ORGANISM_BREATHE_CYCLE_SIM_SEC = 9;
export const ORGANISM_BREATHE_CYCLE_REAL_SEC = 11;

/** Backward-compat alias — SIM default. */
export const ORGANISM_BREATHE_CYCLE_SEC = ORGANISM_BREATHE_CYCLE_SIM_SEC;

export function getOrganismBreatheCycleSec(mode: TradingMode): number {
  return mode === "REAL" ? ORGANISM_BREATHE_CYCLE_REAL_SEC : ORGANISM_BREATHE_CYCLE_SIM_SEC;
}

/** Normalized phase 0..1 from elapsed time. */
export function breathePhaseFromTime(
  elapsedSec: number,
  cycleSec = ORGANISM_BREATHE_CYCLE_SEC,
): number {
  return (elapsedSec / cycleSec) % 1;
}

/**
 * Asymmetric breathe envelope: 60% inhale (ease-in), 40% exhale (ease-out).
 * Returns 0..1 suitable for scale/opacity modulation.
 */
export function asymmetricBreatheEnvelope(phase: number): number {
  const t = phase % 1;
  if (t < 0.6) {
    const inhale = t / 0.6;
    return inhale * inhale;
  }
  const exhale = (t - 0.6) / 0.4;
  return 1 - exhale * exhale * 0.88;
}

/** Map envelope to scale delta around 1.0 */
export function breatheScaleFromEnvelope(envelope: number, amplitude = 0.08): number {
  return 1 + (envelope - 0.5) * 2 * amplitude;
}

export interface OrganismClockState {
  phase: number;
  envelope: number;
  cycleSec: number;
}

/** Shared phase/envelope read for Three.js and the organism clock hook. */
export function readOrganismClock(
  elapsedSec: number,
  mode: TradingMode,
): OrganismClockState {
  const cycleSec = getOrganismBreatheCycleSec(mode);
  const phase = breathePhaseFromTime(elapsedSec, cycleSec);
  return {
    phase,
    envelope: asymmetricBreatheEnvelope(phase),
    cycleSec,
  };
}

/** Lub-dub style double peak for REAL vigilant heartbeat overlay. */
export function vigilantHeartbeatPulse(elapsedSec: number, cycleSec = 6): number {
  const t = (elapsedSec / cycleSec) % 1;
  const lub = Math.exp(-((t - 0.08) ** 2) / 0.004);
  const dub = Math.exp(-((t - 0.22) ** 2) / 0.002) * 0.55;
  return lub + dub;
}
