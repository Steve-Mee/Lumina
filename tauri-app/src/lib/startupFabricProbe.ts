/**
 * Light Fabric link probe for cold-start readiness (soft — never hard-gates hub).
 */
import { fetchFabricLinkStatus } from "@/lib/setupClient";

export type FabricProbeStatus = {
  /** idle = not started · running · done · error */
  phase: "idle" | "running" | "done" | "error";
  green: boolean | null;
  reason: string | null;
};

export const FABRIC_PROBE_IDLE: FabricProbeStatus = {
  phase: "idle",
  green: null,
  reason: null,
};

/**
 * One light GET /api/setup/fabric-link-status — no toast, no heal.
 * Failures become soft error (not green).
 */
export async function probeFabricLinkLight(): Promise<FabricProbeStatus> {
  try {
    const link = await fetchFabricLinkStatus();
    return {
      phase: "done",
      green: Boolean(link.green),
      reason: link.reason?.trim() || (link.green ? "GREEN" : "not green"),
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Fabric status unavailable";
    return {
      phase: "error",
      green: false,
      reason: message,
    };
  }
}
