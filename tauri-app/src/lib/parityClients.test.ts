import { describe, expect, it } from "vitest";

import { defaultBotConfigDraft, toBotConfigPayload } from "@/lib/botConfigDraft";

describe("botConfigDraft preferences", () => {
  it("includes runtime preferences in payload", () => {
    const draft = defaultBotConfigDraft();
    const payload = toBotConfigPayload(draft);
    expect(payload.preferences?.instrument).toBe("MES");
    expect(payload.preferences?.voice_enabled).toBe(true);
    expect(payload.preferences?.dashboard_enabled).toBe(true);
    expect(payload.preferences?.runtime_trace).toBe(true);
    expect(payload.preferences?.runtime_trace_interval_sec).toBe(2);
    expect(payload.preferences?.latency_sla_ms).toBe(300);
  });
});

describe("runtimeClient paths", () => {
  it("defines stop-all and training control paths", async () => {
    const mod = await import("@/lib/runtimeClient");
    expect(typeof mod.stopAllActivities).toBe("function");
    expect(typeof mod.pauseTraining).toBe("function");
    expect(typeof mod.resumeTraining).toBe("function");
    expect(typeof mod.goLiveReal).toBe("function");
    expect(typeof mod.pauseTradingSafely).toBe("function");
  });
});

describe("opsClient monitoring parity", () => {
  it("exports diagnostics and admin snapshot fetchers", async () => {
    const mod = await import("@/lib/opsClient");
    expect(typeof mod.fetchMonitoringDiagnostics).toBe("function");
    expect(typeof mod.fetchAdminSetupSnapshot).toBe("function");
    expect(typeof mod.fetchReactDashboardStatus).toBe("function");
  });
});

describe("opsClient reconciliation", () => {
  it("exports fetchReconciliationStatus", async () => {
    const mod = await import("@/lib/opsClient");
    expect(typeof mod.fetchReconciliationStatus).toBe("function");
  });
});
