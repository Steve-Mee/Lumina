/** Compose Phase Hub KPI tiles. Lives outside phaseHubFormat to avoid import cycles. */
import { apprenticeshipCharterTiles } from "@/components/maturity/phaseHubApprenticeship";
import { awakeningCharterTiles } from "@/components/maturity/phaseHubAwakening";
import { playgroundCharterTiles } from "@/components/maturity/phaseHubPlayground";
import { provingGroundCharterTiles } from "@/components/maturity/phaseHubProvingGround";
import {
  hubCharterTiles,
  type HubCharterTile,
} from "@/components/maturity/phaseHubFormat";
import type { MaturityHubPayload } from "@/lib/maturationClient";

export function resolveHubCharterTiles(
  hub: MaturityHubPayload | null,
): HubCharterTile[] {
  const focus = hub?.focus_phase || hub?.next_phase || "";
  if (focus === "awakening") {
    return awakeningCharterTiles(hub);
  }
  if (focus === "playground") {
    return playgroundCharterTiles(hub);
  }
  if (focus === "apprenticeship") {
    return apprenticeshipCharterTiles(hub);
  }
  if (focus === "proving_ground") {
    return provingGroundCharterTiles(hub);
  }
  return hubCharterTiles(hub);
}
