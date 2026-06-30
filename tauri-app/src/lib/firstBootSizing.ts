/** Mirrors lumina_core.first_boot_ui sizing SSOT (keep in sync with Python). */

export const FIRST_BOOT_EST_TRADES_PER_REAL_DAY = 450;
export const FIRST_BOOT_MIN_REAL_DAYS = 30;
export const FIRST_BOOT_MAX_REAL_DAYS = 3650;
export const FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS = 700;
export const BIRTH_BARS_PER_TRADING_DAY = 390;
export const HISTORICAL_BAR_LIMIT_SAFETY_CAP = 500_000;

export function estimateFirstBootRealDays(trainingTrades: number): number {
  return Math.ceil(Math.max(1, trainingTrades) / FIRST_BOOT_EST_TRADES_PER_REAL_DAY);
}

export function resolveDefaultMaxRealDays(trainingTrades: number): number {
  return Math.max(FIRST_BOOT_MIN_REAL_DAYS, estimateFirstBootRealDays(trainingTrades));
}

export function clampMaxRealDays(value: number): number {
  return Math.max(FIRST_BOOT_MIN_REAL_DAYS, Math.min(FIRST_BOOT_MAX_REAL_DAYS, Math.round(value)));
}

export function exceedsMaxRealDaysWindow(estimatedDays: number, maxRealDays: number): boolean {
  return estimatedDays > maxRealDays;
}

export function isHighLoadEstimate(
  estimatedDays: number,
  threshold: number = FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS,
): boolean {
  return estimatedDays > threshold;
}

/** Calendar days before historical bar fetch hits the 500k safety cap. */
export function historicalBarCapDays(): number {
  return Math.floor(HISTORICAL_BAR_LIMIT_SAFETY_CAP / BIRTH_BARS_PER_TRADING_DAY);
}

export function linkMaxRealDaysToTrainingTrades(trainingTrades: number): number {
  return resolveDefaultMaxRealDays(trainingTrades);
}

export function syncMaxRealDaysForTrainingTrades(
  trainingTrades: number,
  currentMaxRealDays: number,
): number {
  const estimated = resolveDefaultMaxRealDays(trainingTrades);
  return clampMaxRealDays(Math.max(currentMaxRealDays, estimated));
}
