/**
 * Cold-start NinjaTrader wait gate — launch + poll only (Code Red: never kill).
 */
import {
  isNinjaTraderRunning,
  launchNinjaTrader,
} from "@/lib/ninjaTraderClient";
import { probeFabricLinkLight } from "@/lib/startupFabricProbe";

export type NtWaitPhase = "idle" | "launching" | "process" | "fabric" | "done" | "failed";

export type NtWaitResult = "ready" | "process_only" | "failed" | "already_running";

export type WaitForNinjaTraderOptions = {
  /** Call launch_ninjatrader first. */
  launch: boolean;
  processTimeoutMs?: number;
  fabricTimeoutMs?: number;
  pollMs?: number;
  onProgress?: (phase: NtWaitPhase, detail: string) => void;
  /** Abort check (e.g. unmount). */
  isCancelled?: () => boolean;
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    globalThis.setTimeout(resolve, ms);
  });
}

/**
 * Wait until NinjaTrader.exe is running, then best-effort soft Fabric green.
 * Never closes or kills NT.
 */
export async function waitForNinjaTraderReady(
  opts: WaitForNinjaTraderOptions,
): Promise<NtWaitResult> {
  const processTimeoutMs = opts.processTimeoutMs ?? 90_000;
  const fabricTimeoutMs = opts.fabricTimeoutMs ?? 60_000;
  const pollMs = opts.pollMs ?? 1000;
  const onProgress = opts.onProgress ?? (() => undefined);
  const cancelled = opts.isCancelled ?? (() => false);

  if (await isNinjaTraderRunning()) {
    onProgress("fabric", "NinjaTrader already running — probing Fabric…");
    const fabric = await waitFabricSoft(fabricTimeoutMs, pollMs, cancelled, onProgress);
    return fabric ? "ready" : "already_running";
  }

  if (opts.launch) {
    onProgress("launching", "Starting NinjaTrader…");
    const launched = await launchNinjaTrader();
    if (cancelled()) return "failed";
    if (!launched.launched && !launched.installed) {
      onProgress(
        "failed",
        launched.error?.trim() || "NinjaTrader is not installed on this machine",
      );
      return "failed";
    }
    if (!launched.launched && launched.error) {
      onProgress("failed", launched.error);
      return "failed";
    }
  }

  onProgress("process", "Waiting for NinjaTrader process…");
  const processDeadline = Date.now() + processTimeoutMs;
  while (Date.now() < processDeadline) {
    if (cancelled()) return "failed";
    if (await isNinjaTraderRunning()) {
      onProgress("fabric", "Process up — waiting for Fabric host…");
      const fabric = await waitFabricSoft(fabricTimeoutMs, pollMs, cancelled, onProgress);
      onProgress("done", fabric ? "NinjaTrader + Fabric ready" : "Process up · Fabric still settling");
      return fabric ? "ready" : "process_only";
    }
    await sleep(pollMs);
  }

  onProgress("failed", "Timed out waiting for NinjaTrader.exe");
  return "failed";
}

async function waitFabricSoft(
  timeoutMs: number,
  pollMs: number,
  cancelled: () => boolean,
  onProgress: (phase: NtWaitPhase, detail: string) => void,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (cancelled()) return false;
    const probe = await probeFabricLinkLight();
    if (probe.green === true) {
      onProgress("done", probe.reason || "Fabric GREEN");
      return true;
    }
    onProgress(
      "fabric",
      probe.reason || "Fabric not GREEN yet — datafeed Connected + New → LUMINA",
    );
    await sleep(pollMs);
  }
  return false;
}
