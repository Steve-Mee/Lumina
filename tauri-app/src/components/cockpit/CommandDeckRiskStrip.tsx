import { useMemo } from "react";

import { BirthKpiTile, type BirthKpiTone } from "@/components/birth/BirthKpiTile";
import {
  deriveCitadelWallsFromInputs,
  tierLabel,
  type IntegrityTier,
  type WallMetric,
} from "@/lib/riskCitadelMetrics";
import {
  selectCurrentMode,
  selectFortress,
  selectLiveMetrics,
  selectRiskLevel,
  useCoreStore,
} from "@/store/coreStore";

function toneFor(tier: IntegrityTier): BirthKpiTone {
  if (tier === "green") return "success";
  if (tier === "orange") return "accent";
  return "warn";
}

function WallTile({ wall }: { wall: WallMetric }) {
  return (
    <BirthKpiTile
      label={wall.label}
      value={`${Math.round(wall.integrity)}%`}
      detail={wall.isStandby ? "standby" : tierLabel(wall.tier)}
      tone={toneFor(wall.tier)}
    />
  );
}

export function CommandDeckRiskStrip() {
  const mode = useCoreStore(selectCurrentMode);
  const liveMetrics = useCoreStore(selectLiveMetrics);
  const riskLevel = useCoreStore(selectRiskLevel);
  const fortress = useCoreStore(selectFortress);
  const walls = useMemo(
    () => deriveCitadelWallsFromInputs({ liveMetrics, riskLevel, fortress }),
    [liveMetrics, riskLevel, fortress],
  );

  return (
    <div
      className="command-deck-ops__risk shrink-0"
      data-mode={mode}
      data-tour="risk-citadel"
      aria-label="Risk walls"
    >
      {walls.map((wall) => (
        <WallTile key={wall.id} wall={wall} />
      ))}
    </div>
  );
}
