import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/ninjaTraderClient", () => ({
  isNinjaTraderRunning: vi.fn(),
  launchNinjaTrader: vi.fn(),
}));

vi.mock("@/lib/setupClient", () => ({
  fetchFabricLinkStatus: vi.fn(),
  postFabricBootstrap: vi.fn(),
  postFabricConnectionTest: vi.fn(),
}));

import { isNinjaTraderRunning } from "@/lib/ninjaTraderClient";
import {
  fetchFabricLinkStatus,
  postFabricBootstrap,
  postFabricConnectionTest,
} from "@/lib/setupClient";
import {
  ensureFabricGreen,
  runSystemsGoAfterBackend,
} from "@/lib/startupSystemsOrchestrator";

describe("startupSystemsOrchestrator", () => {
  beforeEach(() => {
    vi.mocked(isNinjaTraderRunning).mockReset();
    vi.mocked(fetchFabricLinkStatus).mockReset();
    vi.mocked(postFabricBootstrap).mockReset();
    vi.mocked(postFabricConnectionTest).mockReset();
  });

  it("does not kill NinjaTrader (source guard)", async () => {
    const fs = await import("node:fs");
    const src = fs.readFileSync(
      new URL("./startupSystemsOrchestrator.ts", import.meta.url),
      "utf8",
    );
    expect(src).not.toContain("closeNinjaTrader");
    expect(src).not.toContain("taskkill");
    expect(src).not.toContain("close_ninjatrader");
  });

  it("returns need_nt when process is down and not degraded", async () => {
    vi.mocked(isNinjaTraderRunning).mockResolvedValue(false);
    const result = await runSystemsGoAfterBackend({
      hooks: {
        isCancelled: () => false,
        onProgress: () => undefined,
        appSurface: "birth",
      },
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.reason).toBe("need_nt");
  });

  it("waits for fabric green when NT is up (no early exit on process alone)", async () => {
    vi.mocked(isNinjaTraderRunning).mockResolvedValue(true);
    vi.mocked(postFabricBootstrap).mockResolvedValue({
      fabric_link_green: false,
      fabric_link_reason: "pending",
    } as never);
    vi.mocked(fetchFabricLinkStatus)
      .mockResolvedValueOnce({ green: false, reason: "warming", certificate: null, halt: null })
      .mockResolvedValue({ green: true, reason: "ok", certificate: null, halt: null });
    vi.mocked(postFabricConnectionTest).mockResolvedValue({
      overall: "red",
      certified: false,
    } as never);

    const result = await ensureFabricGreen({
      isCancelled: () => false,
      timeoutMs: 5_000,
      pollMs: 50,
    });
    expect(result.green).toBe(true);
  });

  it("completes systems go when fabric green and birth hydrate ok", async () => {
    vi.mocked(isNinjaTraderRunning).mockResolvedValue(true);
    vi.mocked(postFabricBootstrap).mockResolvedValue({
      fabric_link_green: true,
      fabric_link_reason: "proof",
    } as never);
    // Paper bootstrap cert alone is not live GREEN — status poll is SSOT.
    vi.mocked(fetchFabricLinkStatus).mockResolvedValue({
      green: true,
      host_ready: true,
      gate_birth_ok: true,
      level: "GREEN",
      meaning: "Lumina Brain connected",
      reason: "LIVE_GREEN",
      proof: { certified: true, badge_ok: true },
      certificate: { overall: "green" },
      halt: null,
    });
    const hydrate = vi.fn().mockResolvedValue(true);
    const result = await runSystemsGoAfterBackend({
      hooks: {
        isCancelled: () => false,
        onProgress: () => undefined,
        appSurface: "birth",
        hydrateBirthSession: hydrate,
      },
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.fabric.green).toBe(true);
      expect(result.degraded).toBe(false);
    }
    expect(hydrate).toHaveBeenCalledOnce();
  });

  it("degraded continue does not re-poll Fabric for 50s", async () => {
    vi.mocked(isNinjaTraderRunning).mockResolvedValue(true);
    const result = await runSystemsGoAfterBackend({
      degraded: true,
      hooks: {
        isCancelled: () => false,
        onProgress: () => undefined,
        appSurface: "hub",
      },
    });
    expect(result.ok).toBe(true);
    expect(postFabricBootstrap).not.toHaveBeenCalled();
    expect(fetchFabricLinkStatus).not.toHaveBeenCalled();
    if (result.ok) {
      expect(result.degraded).toBe(true);
      expect(result.fabric.green).toBe(false);
    }
  });

  it("birth hydrate failure stays on cover (need_birth_retry)", async () => {
    vi.mocked(isNinjaTraderRunning).mockResolvedValue(true);
    vi.mocked(postFabricBootstrap).mockResolvedValue({
      fabric_link_green: true,
      fabric_link_reason: "proof",
    } as never);
    vi.mocked(fetchFabricLinkStatus).mockResolvedValue({
      green: true,
      host_ready: true,
      gate_birth_ok: true,
      level: "GREEN",
      reason: "LIVE_GREEN",
      certificate: null,
      halt: null,
    });
    const result = await runSystemsGoAfterBackend({
      hooks: {
        isCancelled: () => false,
        onProgress: () => undefined,
        appSurface: "birth",
        hydrateBirthSession: async () => false,
      },
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.reason).toBe("need_birth_retry");
  });

  it("paper cert alone does not complete Systems Go without host_ready", async () => {
    vi.mocked(postFabricBootstrap).mockResolvedValue({
      fabric_link_green: true,
      fabric_link_reason: "certificate",
    } as never);
    vi.mocked(fetchFabricLinkStatus).mockResolvedValue({
      green: false,
      host_ready: false,
      gate_birth_ok: false,
      level: "RED",
      meaning: "Bridge not running",
      reason: "FABRIC_HOST_DOWN",
      proof: { certified: true },
      certificate: { overall: "green" },
      halt: null,
    });
    vi.mocked(postFabricConnectionTest).mockResolvedValue({
      overall: "red",
      certified: false,
    } as never);
    const result = await ensureFabricGreen({
      isCancelled: () => false,
      timeoutMs: 400,
      pollMs: 50,
    });
    expect(result.green).toBe(false);
    expect(result.hostReady).toBeFalsy();
  });

  it("AUTH_FAILED surfaces token remediation (not generic SAFE heartbeats)", async () => {
    vi.mocked(postFabricBootstrap).mockResolvedValue({
      fabric_link_green: false,
      fabric_link_reason: "HOST_READY_AMBER",
    } as never);
    vi.mocked(fetchFabricLinkStatus).mockResolvedValue({
      green: false,
      host_ready: true,
      gate_birth_ok: false,
      level: "AMBER",
      meaning: "Safe mode - waiting for Lumina Brain heartbeats",
      reason: "HOST_READY_AMBER",
      live: {
        auth_ok: false,
        last_error_code: "AUTH_FAILED",
        last_error: "Invalid fabric token",
      },
      proof: { certified: false },
      certificate: null,
      halt: null,
    });
    vi.mocked(postFabricConnectionTest).mockResolvedValue({
      overall: "red",
      certified: false,
    } as never);
    const result = await ensureFabricGreen({
      isCancelled: () => false,
      timeoutMs: 8_000,
      pollMs: 50,
    });
    expect(result.green).toBe(false);
    expect(result.hostReady).toBe(true);
    expect(result.reason).toMatch(/token/i);
    expect(result.reason).not.toMatch(/heartbeats/i);
  });
});

