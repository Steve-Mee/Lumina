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
    const normalized = reason.replace(/\u00b7/g, "|").replace(/\u2014/g, "-").replace(/\u2265/g, ">=");
    const life =
      progress?.hygiene_wr_lifetime != null && Number.isFinite(progress.hygiene_wr_lifetime)
        ? Number(progress.hygiene_wr_lifetime)
        : null;
    const roll =
      progress?.hygiene_wr_rolling != null && Number.isFinite(progress.hygiene_wr_rolling)
        ? Number(progress.hygiene_wr_rolling)
        : progress?.rolling_winrate_500 != null && Number.isFinite(progress.rolling_winrate_500)
          ? Number(progress.rolling_winrate_500)
          : null;
    const looksLikeClearedExpectancy =
      /expectancy/i.test(normalized) &&
      /need\s*>=?\s*-15%/i.test(normalized) &&
      /now\s+4\d%/i.test(normalized);
    if (
      looksLikeClearedExpectancy &&
      life != null &&
      life + 1e-12 < 0.3 &&
      roll != null &&
      roll + 1e-12 >= 0.35
    ) {
      return (
        `Durable lifetime WR ${(life * 100).toFixed(1)}% < 30% ` +
        `(rolling ${(roll * 100).toFixed(0)}% does not pass alone) | EdgeScore ` +
        (progress?.edgescore != null && Number.isFinite(progress.edgescore)
          ? `${(Number(progress.edgescore) * 100).toFixed(0)}%`
          : "—")
      );
    }
    return normalized;
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
        : "diag";
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

/** Compact fail-gate readout — never dump the raw engine sentence into the card. */
export type BlockerPresentation = {
  title: string;
  value: string;
  hint: string;
  raw: string;
};

function joinHint(parts: Array<string | null | undefined>): string {
  return parts
    .map((part) => String(part ?? "").replace(/\bsrc=\S+/gi, "").replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join(" · ");
}

export function presentBlockerDetail(raw: string): BlockerPresentation {
  const text = String(raw ?? "").trim();
  const parts = text.split("|").map((part) => part.trim()).filter(Boolean);
  const main = parts[0] ?? text;
  const extras = parts.slice(1);
  const edge = extras.find((part) => /^edgescore\b/i.test(part));

  const expectancy = main.match(
    /^Expectancy\s+([+\-−]?\d+(?:\.\d+)?%)\s*(?:\((.*)\))?\s*$/i,
  );
  if (expectancy) {
    const inner = expectancy[2] ?? "";
    const need = inner.match(/need\s*>=?\s*([+\-]?\d+(?:\.\d+)?%)/i)?.[1];
    const wrNow = inner.match(/now\s+(\d+(?:\.\d+)?%)/i)?.[1];
    const wrFloor = inner.match(/WR\s*>=?\s*(\d+(?:\.\d+)?%)/i)?.[1];
    return {
      title: "Expectancy",
      value: expectancy[1].replace("−", "-"),
      hint:
        joinHint([
          need ? `need ≥ ${need}` : null,
          wrNow ? `WR ${wrNow}${wrFloor ? ` (need ≥ ${wrFloor})` : ""}` : null,
          edge,
        ]) || "Primary fail gate",
      raw: text,
    };
  }

  const durable = main.match(/^Durable lifetime WR\s+(\d+(?:\.\d+)?%)\s*(.*)$/i);
  if (durable) {
    const rest = durable[2].replace(/[()]/g, " ").replace(/\s+/g, " ").trim();
    return {
      title: "Durable lifetime WR",
      value: durable[1],
      hint: joinHint([rest || null, edge]) || "Primary fail gate",
      raw: text,
    };
  }

  if (/^Hygiene WR\b/i.test(main)) {
    const life = main.match(/lifetime\s+(\d+(?:\.\d+)?%)/i)?.[1];
    const roll = main.match(/rolling\s+(\d+(?:\.\d+)?%)/i)?.[1];
    const need = main.match(/need\s*>=?\s*(\d+(?:\.\d+)?%)/i)?.[1];
    const delayed = /rolling counts after/i.test(main);
    return {
      title: "Hygiene WR",
      value: life ?? "—",
      hint:
        joinHint([
          roll ? `roll ${roll}` : null,
          need ? `need ≥ ${need}` : null,
          delayed ? "rolling after 400" : null,
          edge,
        ]) || "Primary fail gate",
      raw: text,
    };
  }

  const entropy = main.match(/^Entropy\s+(.+)$/i);
  if (entropy) {
    const h = entropy[1].match(/\(H=[^)]+\)/)?.[0];
    return {
      title: "Entropy",
      value: entropy[1].replace(/\(H=[^)]+\)/, "").trim() || entropy[1],
      hint: joinHint([h, edge]) || "Primary fail gate",
      raw: text,
    };
  }

  const hold = main.match(/^Hold\s+(\d+(?:\.\d+)?%)\s*(.*)$/i);
  if (hold) {
    return {
      title: "Hold",
      value: hold[1],
      hint: joinHint([hold[2] || null, edge]) || "Primary fail gate",
      raw: text,
    };
  }

  const winrate = main.match(/^(\d+(?:\.\d+)?%)\s*-\s*need\s+(\d+(?:\.\d+)?%)$/i);
  if (winrate) {
    return {
      title: "Winrate",
      value: winrate[1],
      hint: joinHint([`need ≥ ${winrate[2]}`, edge]) || "Primary fail gate",
      raw: text,
    };
  }

  if (main.length <= 32 && extras.length === 0) {
    return { title: "Fail gate", value: main, hint: "Primary fail gate", raw: text };
  }

  return {
    title: "Fail gate",
    value: edge?.replace(/^EdgeScore\s+/i, "") || "blocked",
    hint: joinHint([main, ...extras.filter((part) => part !== edge)]) || "Primary fail gate",
    raw: text,
  };
}
