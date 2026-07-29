import type { BirthProgressPayload } from "@/lib/birthClient";

/** True when pass_reason is a raw EdgeScore debug dump, not operator copy. */
export function isRawEdgescorePassReason(passReason: string): boolean {
  const raw = passReason.toLowerCase();
  return raw.includes("edgescore=") || raw.includes("blockers=") || raw.includes("s2_edgescore=");
}

/** Build a percent-based EdgeScore blocker line from structured progress fields. */
export function humanizeEdgescoreBlockerDetail(
  progress: BirthProgressPayload | undefined,
  passReason: string,
): string {
  const reason = String(passReason ?? "").trim();
  if (!reason) return "";
  if (!isRawEdgescorePassReason(reason)) {
    // Normalize any remaining unicode separators to ASCII for HUD stability.
    return reason.replace(/\u00b7/g, "|").replace(/\u2014/g, "-").replace(/\u2265/g, ">=");
  }

  const edge =
    progress?.edgescore != null && Number.isFinite(progress.edgescore)
      ? `${(Number(progress.edgescore) * 100).toFixed(0)}%`
      : null;
  const wr =
    progress?.stage_winrate != null && Number.isFinite(progress.stage_winrate)
      ? `${(Number(progress.stage_winrate) * 100).toFixed(0)}%`
      : null;
  const hold =
    progress?.stage_hold_ratio != null && Number.isFinite(progress.stage_hold_ratio)
      ? `${(Number(progress.stage_hold_ratio) * 100).toFixed(0)}%`
      : null;
  const expRaw = progress?.expectancy_proxy;
  const expValid =
    expRaw != null && Number.isFinite(expRaw) && Math.abs(Number(expRaw)) <= 0.55;
  const exp = expValid ? `${(Number(expRaw) * 100).toFixed(0)}%` : null;
  const entropyMissing =
    progress?.entropy_alive === false &&
    (progress?.policy_entropy == null || !Number.isFinite(progress.policy_entropy));
  const entropyDead =
    progress?.entropy_alive === false &&
    progress?.policy_entropy != null &&
    Number.isFinite(progress.policy_entropy);

  const parts: string[] = [];
  if (reason.toLowerCase().includes("expectancy") && exp != null) {
    parts.push(`Expectancy ${exp} (need >= -15%)`);
  } else if (entropyMissing) {
    parts.push("Entropy missing");
  } else if (entropyDead) {
    parts.push(`Entropy dead (H=${Number(progress?.policy_entropy).toFixed(3)})`);
  } else if (reason.toLowerCase().includes("hygiene")) {
    const floor =
      progress?.hygiene_wr_floor != null && Number.isFinite(progress.hygiene_wr_floor)
        ? `${(Number(progress.hygiene_wr_floor) * 100).toFixed(0)}%`
        : "35%";
    const life =
      progress?.hygiene_wr_lifetime != null && Number.isFinite(progress.hygiene_wr_lifetime)
        ? `${(Number(progress.hygiene_wr_lifetime) * 100).toFixed(0)}%`
        : wr;
    const roll =
      progress?.hygiene_wr_rolling != null && Number.isFinite(progress.hygiene_wr_rolling)
        ? `${(Number(progress.hygiene_wr_rolling) * 100).toFixed(0)}%`
        : progress?.rolling_winrate_500 != null &&
            Number.isFinite(progress.rolling_winrate_500)
          ? `${(Number(progress.rolling_winrate_500) * 100).toFixed(0)}%`
          : null;
    if (life != null && roll != null) {
      const eligibleNote =
        progress?.rolling_wr_eligible === false ? "; rolling counts after 400" : "";
      parts.push(`Hygiene WR lifetime ${life} / rolling ${roll} (need >= ${floor}${eligibleNote})`);
    } else if (life != null) {
      parts.push(`Hygiene WR lifetime ${life} (need >= ${floor})`);
    } else if (wr != null) {
      parts.push(`Hygiene WR ${wr} (need >= ${floor})`);
    } else {
      parts.push(`Hygiene WR below floor (need >= ${floor})`);
    }
  } else if (reason.toLowerCase().includes("hold") && hold != null) {
    parts.push(`Hold ${hold} outside activity band`);
  } else {
    parts.push("EdgeScore criteria incomplete");
  }
  if (wr != null) parts.push(`WR ${wr}`);
  if (hold != null) parts.push(`hold ${hold}`);
  if (edge != null) parts.push(`EdgeScore ${edge}`);
  return parts.join(" | ");
}
