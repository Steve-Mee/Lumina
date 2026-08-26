import { describe, expect, it } from "vitest";

import {
  BIRTH_BARS_PER_TRADING_DAY,
  clampMaxRealDays,
  estimateFirstBootRealDays,
  exceedsMaxRealDaysWindow,
  FIRST_BOOT_DEFAULT_MAX_REAL_DAYS,
  FIRST_BOOT_EST_TRADES_PER_REAL_DAY,
  FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS,
  FIRST_BOOT_MAX_REAL_DAYS,
  FIRST_BOOT_MIN_REAL_DAYS,
  FOUNDATION_HISTORY_MAX_DAYS,
  FOUNDATION_HISTORY_START_DAYS,
  historicalBarCapDays,
  HISTORICAL_BAR_LIMIT_SAFETY_CAP,
  isHighLoadEstimate,
  resolveDefaultMaxRealDays,
} from "@/lib/firstBootSizing";

describe("firstBootSizing", () => {
  it("mirrors Python estimate_first_boot_real_days parity cases (duration only)", () => {
    expect(FIRST_BOOT_EST_TRADES_PER_REAL_DAY).toBe(450);
    expect(estimateFirstBootRealDays(25_000)).toBe(56);
    expect(estimateFirstBootRealDays(100_000)).toBe(223);
    expect(estimateFirstBootRealDays(300_000)).toBe(667);
    expect(estimateFirstBootRealDays(500_000)).toBe(1112);
    expect(estimateFirstBootRealDays(1_000_000)).toBe(2223);
    expect(estimateFirstBootRealDays(2_000_000)).toBe(4445);
  });

  it("resolveDefaultMaxRealDays is Foundation ceiling, independent of trades", () => {
    expect(FIRST_BOOT_MIN_REAL_DAYS).toBe(FOUNDATION_HISTORY_START_DAYS);
    expect(FIRST_BOOT_DEFAULT_MAX_REAL_DAYS).toBe(FOUNDATION_HISTORY_MAX_DAYS);
    expect(resolveDefaultMaxRealDays(5_000)).toBe(365);
    expect(resolveDefaultMaxRealDays(25_000)).toBe(365);
    expect(resolveDefaultMaxRealDays(100_000)).toBe(365);
  });

  it("25k trades still start at 90d; clamp refuses 56 as Birth start", () => {
    expect(FOUNDATION_HISTORY_START_DAYS).toBe(90);
    expect(clampMaxRealDays(56)).toBe(90);
    expect(clampMaxRealDays(365)).toBe(365);
  });

  it("exceedsMaxRealDaysWindow and high-load band match Python helpers", () => {
    expect(exceedsMaxRealDaysWindow(400, 90)).toBe(true);
    expect(exceedsMaxRealDaysWindow(80, 90)).toBe(false);
    expect(FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS).toBe(700);
    expect(isHighLoadEstimate(701)).toBe(true);
    expect(isHighLoadEstimate(700)).toBe(false);
  });

  it("historicalBarCapDays reflects bar safety cap", () => {
    expect(historicalBarCapDays()).toBe(
      Math.floor(HISTORICAL_BAR_LIMIT_SAFETY_CAP / BIRTH_BARS_PER_TRADING_DAY),
    );
    expect(FIRST_BOOT_MAX_REAL_DAYS).toBe(3650);
  });
});
