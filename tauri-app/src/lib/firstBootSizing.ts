/** Mirrors lumina_core.first_boot_ui + foundation_history SSOT (keep in sync with Python). */

export const FIRST_BOOT_EST_TRADES_PER_REAL_DAY = 450;
export const FOUNDATION_HISTORY_START_DAYS = 90;
export const FOUNDATION_HISTORY_MAX_DAYS = 365;
export const FIRST_BOOT_MIN_REAL_DAYS = FOUNDATION_HISTORY_START_DAYS;
export const FIRST_BOOT_DEFAULT_MAX_REAL_DAYS = FOUNDATION_HISTORY_MAX_DAYS;
export const FIRST_BOOT_MAX_REAL_DAYS = 3650;
export const FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS = 700;
export const BIRTH_BARS_PER_TRADING_DAY = 390;
export const HISTORICAL_BAR_LIMIT_SAFETY_CAP = 500_000;

/** Wall-clock session-day estimate at ~450 trades/day. Not a history sizer. */
export function estimateFirstBootRealDays(trainingTrades: number): number {
  return Math.ceil(Math.max(1, trainingTrades) / FIRST_BOOT_EST_TRADES_PER_REAL_DAY);
}

/** Expand ceiling SSOT. Independent of the trade budget. */
export function resolveDefaultMaxRealDays(_trainingTrades?: number): number {
  return FOUNDATION_HISTORY_MAX_DAYS;
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

/** History depth is Foundation physics, not trades/450. */
export function foundationHistoryStartDays(): number {
  return FOUNDATION_HISTORY_START_DAYS;
}
