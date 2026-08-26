import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/ninjaTraderClient", () => ({
  isNinjaTraderRunning: vi.fn(),
  launchNinjaTrader: vi.fn(),
}));

vi.mock("@/lib/startupFabricProbe", () => ({
  probeFabricLinkLight: vi.fn(),
}));

import {
  isNinjaTraderRunning,
  launchNinjaTrader,
} from "@/lib/ninjaTraderClient";
import { probeFabricLinkLight } from "@/lib/startupFabricProbe";
import { waitForNinjaTraderReady } from "@/lib/ninjaTraderStartupGate";

describe("waitForNinjaTraderReady", () => {
  beforeEach(() => {
    vi.mocked(isNinjaTraderRunning).mockReset();
    vi.mocked(launchNinjaTrader).mockReset();
    vi.mocked(probeFabricLinkLight).mockReset();
  });

  it("returns ready when already running and fabric green", async () => {
    vi.mocked(isNinjaTraderRunning).mockResolvedValue(true);
    vi.mocked(probeFabricLinkLight).mockResolvedValue({
      phase: "done",
      green: true,
      reason: "ok",
    });
    const result = await waitForNinjaTraderReady({
      launch: false,
      fabricTimeoutMs: 100,
      pollMs: 10,
    });
    expect(result).toBe("ready");
    expect(launchNinjaTrader).not.toHaveBeenCalled();
  });

  it("launches then waits for process (never kills)", async () => {
    vi.mocked(isNinjaTraderRunning)
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(false)
      .mockResolvedValue(true);
    vi.mocked(launchNinjaTrader).mockResolvedValue({
      launched: true,
      installed: true,
      exePath: "C:\\\\NT\\\\NinjaTrader.exe",
      error: null,
    });
    vi.mocked(probeFabricLinkLight).mockResolvedValue({
      phase: "done",
      green: false,
      reason: "settling",
    });
    const result = await waitForNinjaTraderReady({
      launch: true,
      processTimeoutMs: 500,
      fabricTimeoutMs: 50,
      pollMs: 20,
    });
    expect(launchNinjaTrader).toHaveBeenCalledOnce();
    expect(result).toBe("process_only");
  });

  it("gate source never closes NinjaTrader", async () => {
    const src = await import("node:fs").then((fs) =>
      fs.readFileSync(
        new URL("./ninjaTraderStartupGate.ts", import.meta.url),
        "utf8",
      ),
    );
    expect(src).not.toContain("closeNinjaTrader");
    expect(src).not.toContain("taskkill");
  });
});
