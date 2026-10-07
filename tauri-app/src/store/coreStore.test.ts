import { describe, expect, it } from "vitest";

import { useCoreStore } from "@/store/coreStore";

describe("coreStore barBook", () => {
  it("stores bar_book from a telemetry frame and clears it on reset", () => {
    useCoreStore.getState().resetCoreState();
    useCoreStore.getState().applyTelemetryFrame({
      type: "telemetry",
      seq: 1,
      ts: "2026-10-02T12:00:00Z",
      payload: {
        mode: "sim",
        equity: 100000,
        regime: "RANGE",
        risk_level: "NORMAL",
        active_mutations: [],
        source_ts: "2026-10-02T12:00:00Z",
        bar_book: {
          complete: false,
          lock_new_entries: true,
          reason: "unexplained",
          missing_count: 2,
          message: "locked",
        },
      },
    });
    expect(useCoreStore.getState().barBook?.lock_new_entries).toBe(true);
    expect(useCoreStore.getState().barBook?.missing_count).toBe(2);
    useCoreStore.getState().resetCoreState();
    expect(useCoreStore.getState().barBook).toBeNull();
  });
});
