import { describe, expect, it } from "vitest";

import {
  parseBarBookTelemetry,
  parseTelemetryPayload,
} from "@/lib/coreLiveTelemetry";

describe("parseBarBookTelemetry", () => {
  it("treats a missing payload as unknown, not complete", () => {
    expect(parseBarBookTelemetry(null)).toBeNull();
    expect(parseBarBookTelemetry(undefined)).toBeNull();
    expect(parseBarBookTelemetry({})).toBeNull();
  });

  it("parses a locked NT bar book", () => {
    const book = parseBarBookTelemetry({
      complete: false,
      lock_new_entries: true,
      reason: "unexplained",
      missing_count: 3,
      message: "3 missing NT 1m bars",
    });
    expect(book).toEqual({
      complete: false,
      lock_new_entries: true,
      reason: "unexplained",
      missing_count: 3,
      message: "3 missing NT 1m bars",
    });
  });
});

describe("parseTelemetryPayload bar_book", () => {
  it("carries bar_book on the live payload", () => {
    const payload = parseTelemetryPayload({
      mode: "sim",
      equity: 100000,
      regime: "RANGE",
      risk_level: "NORMAL",
      active_mutations: [],
      source_ts: "2026-10-02T12:00:00Z",
      bar_book: {
        complete: true,
        lock_new_entries: false,
        reason: "",
        missing_count: 0,
        message: "",
      },
    });
    expect(payload?.bar_book?.complete).toBe(true);
    expect(payload?.bar_book?.lock_new_entries).toBe(false);
  });
});
