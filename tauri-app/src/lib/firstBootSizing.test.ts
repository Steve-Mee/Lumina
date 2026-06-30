import { describe, expect, it } from "vitest";

import {
  BIRTH_BARS_PER_TRADING_DAY,
  estimateFirstBootRealDays,
  exceedsMaxRealDaysWindow,
  FIRST_BOOT_EST_TRADES_PER_REAL_DAY,
  FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS,
  FIRST_BOOT_MAX_REAL_DAYS,
  FIRST_BOOT_MIN_REAL_DAYS,
  historicalBarCapDays,
  HISTORICAL_BAR_LIMIT_SAFETY_CAP,
  isHighLoadEstimate,
  linkMaxRealDaysToTrainingTrades,
  resolveDefaultMaxRealDays,
  syncMaxRealDaysForTrainingTrades,
} from "@/lib/firstBootSizing";

describe("firstBootSizing", () => {
  it("mirrors Python estimate_first_boot_real_days parity cases", () => {
    expect(FIRST_BOOT_EST_TRADES_PER_REAL_DAY).toBe(450);
    expect(estimateFirstBootRealDays(25_000)).toBe(56);
    expect(estimateFirstBootRealDays(100_000)).toBe(223);
    expect(estimateFirstBootRealDays(300_000)).toBe(667);
    expect(estimateFirstBootRealDays(500_000)).toBe(1112);
    expect(estimateFirstBootRealDays(1_000_000)).toBe(2223);
    expect(estimateFirstBootRealDays(2_000_000)).toBe(4445);
  });

  it("resolveDefaultMaxRealDays applies floor of 30 days", () => {
    expect(resolveDefaultMaxRealDays(5_000)).toBe(FIRST_BOOT_MIN_REAL_DAYS);
    expect(resolveDefaultMaxRealDays(25_000)).toBe(56);
    expect(resolveDefaultMaxRealDays(100_000)).toBe(223);
  });

  it("linkMaxRealDaysToTrainingTrades tracks estimate for slider coupling", () => {
    expect(linkMaxRealDaysToTrainingTrades(5_000)).toBe(30);
    expect(linkMaxRealDaysToTrainingTrades(25_000)).toBe(56);
    expect(linkMaxRealDaysToTrainingTrades(500_000)).toBe(1112);
  });

  it("syncMaxRealDaysForTrainingTrades bumps up but never below estimate", () => {
    expect(syncMaxRealDaysForTrainingTrades(25_000, 56)).toBe(56);
    expect(syncMaxRealDaysForTrainingTrades(25_000, 30)).toBe(56);
    expect(syncMaxRealDaysForTrainingTrades(500_000, 56)).toBe(1112);
    expect(syncMaxRealDaysForTrainingTrades(500_000, 1500)).toBe(1500);
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
