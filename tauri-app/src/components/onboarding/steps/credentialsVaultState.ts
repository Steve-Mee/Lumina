/** Pure chip/focus helpers for Credentials vault (Tauri UI god split). */
import type { ChipState } from "@/components/onboarding/steps/CredentialsVaultPrimitives";
import type { FabricConnectionTestReport } from "@/lib/setupClient";
import type { OnboardingDraft } from "@/store/onboardingStore";

type Creds = OnboardingDraft["credentials"];

/** Channel matrix ids (vault sections). */
export type VaultChannelId = "security" | "fabric" | "alerts" | "data" | "twin";

/** One card in the vault channel matrix (col 2). */
export type ChannelCardModel = {
  id: VaultChannelId;
  label: string;
  summary: string;
  state: ChipState;
  tip: string;
};

/** Field-level / action focus for mission master–detail. */
export type VaultFocusId =
  | "jwt"
  | "admin"
  | "fabric_token"
  | "diagnostic"
  | "telegram_bot"
  | "telegram_chat"
  | "crosstrade_token"
  | "crosstrade_account"
  | "nt_install"
  | "twin_base";

export type VaultFocusRow = {
  id: VaultFocusId;
  label: string;
  summary: string;
  state: ChipState;
  tip: string;
  section: "security" | "fabric" | "alerts" | "data" | "twin";
};

/** Twin base curriculum chip (Operator Vault foundation — ADR-0037). */
export function twinChipState(
  birthReady: boolean,
  completionPct?: number | null,
): ChipState {
  if (birthReady) return "ok";
  const pct = Number(completionPct ?? 0);
  if (pct > 0) return "partial";
  return "idle";
}

export function securityChipState(
  creds: Creds,
  present: Record<string, boolean>,
): ChipState {
  const jwt = Boolean(creds.LUMINA_JWT_SECRET_KEY.trim() || present.LUMINA_JWT_SECRET_KEY);
  const admin = Boolean(creds.LUMINA_ADMIN_API_KEY.trim() || present.LUMINA_ADMIN_API_KEY);
  if (jwt && admin) return "ok";
  if (jwt || admin) return "partial";
  return "idle";
}

export function fabricTokenChipState(
  creds: Creds,
  present: Record<string, boolean>,
): ChipState {
  return Boolean(creds.LUMINA_FABRIC_TOKEN.trim() || present.LUMINA_FABRIC_TOKEN)
    ? "ok"
    : "idle";
}

export function linkChipState(
  fabricGreen: boolean,
  fabricReport: FabricConnectionTestReport | null,
): ChipState {
  if (fabricGreen) return "ok";
  if (!fabricReport) return "idle";
  if (fabricReport.overall === "amber") return "partial";
  return "fail";
}

/** Live SSOT chip: GREEN=ok, AMBER/RESTARTING/host_ready=partial, RED=fail. */
export function linkChipStateFromLive(
  liveLevel: string | null | undefined,
  hostReady: boolean,
  fabricReport: FabricConnectionTestReport | null,
): ChipState {
  const level = String(liveLevel || "").toUpperCase();
  if (level === "GREEN") return "ok";
  if (level === "AMBER" || level === "RESTARTING" || hostReady) return "partial";
  if (level === "RED") return "fail";
  if (fabricReport?.overall === "green") return "partial"; // proof only, not live green
  if (fabricReport?.overall === "amber") return "partial";
  if (fabricReport?.overall === "red") return "fail";
  return "idle";
}

export function alertsChipState(
  creds: Creds,
  present: Record<string, boolean>,
): ChipState {
  const bot = Boolean(creds.TELEGRAM_BOT_TOKEN.trim() || present.TELEGRAM_BOT_TOKEN);
  const chat = Boolean(creds.TELEGRAM_CHAT_ID.trim() || present.TELEGRAM_CHAT_ID);
  if (bot && chat) return "ok";
  if (bot || chat) return "partial";
  return "idle";
}

export function dataChipState(emergencyFeed: boolean, creds: Creds): ChipState {
  if (!emergencyFeed) return "idle";
  const t = Boolean(creds.CROSSTRADE_TOKEN.trim());
  const a = Boolean(creds.CROSSTRADE_ACCOUNT.trim());
  if (t && a) return "ok";
  if (t || a) return "partial";
  return "idle";
}

export function vaultStageCaption(
  fabricGreen: boolean,
  secState: ChipState,
  fabricState: ChipState,
): string {
  if (fabricGreen) return "Link sealed · organism linked";
  if (secState !== "idle" || fabricState !== "idle") return "Channels awakening";
  return "Organism waiting · channels dark";
}

export function fieldFillState(value: string, present?: boolean): ChipState {
  if (value.trim() || present) return "ok";
  return "partial";
}

function setOrMissing(value: string, present?: boolean, required = true): string {
  if (value.trim() || present) return "Set";
  return required ? "Missing" : "Optional · empty";
}

export function linkSummary(
  fabricGreen: boolean,
  fabricReport: FabricConnectionTestReport | null,
  fabricCertified: boolean,
): string {
  // Legacy path — prefer linkSummaryLive when SSOT poll is available.
  if (fabricGreen) {
    if (fabricReport?.checks?.length) {
      const pass = fabricReport.checks.filter((c) => c.status === "pass").length;
      return `Live GREEN · ${pass}/${fabricReport.checks.length} checks`;
    }
    return "Live GREEN · Brain connected";
  }
  if (fabricCertified) {
    if (fabricReport?.checks?.length) {
      const pass = fabricReport.checks.filter((c) => c.status === "pass").length;
      return `Proof OK · ${pass}/${fabricReport.checks.length} · live not GREEN`;
    }
    return "Proof OK · live link not GREEN";
  }
  if (!fabricReport) return "Not tested · required";
  if (fabricReport.overall === "amber") return "AMBER · degraded";
  const fail = fabricReport.checks?.find((c) => c.status === "fail");
  if (fail?.title) return `RED · ${fail.title}`;
  return "RED · failed";
}

/** Dual-truth summary: live level + optional proof (never conflate). */
export function linkSummaryLive(opts: {
  liveLevel?: string | null;
  meaning?: string | null;
  hostReady?: boolean;
  proofCertified?: boolean;
  proofBadgeOk?: boolean;
  fabricReport?: FabricConnectionTestReport | null;
}): string {
  const level = String(opts.liveLevel || "").toUpperCase() || "—";
  const proof =
    opts.proofBadgeOk || opts.proofCertified
      ? opts.fabricReport?.checks?.length
        ? ` · proof ${opts.fabricReport.checks.filter((c) => c.status === "pass").length}/${opts.fabricReport.checks.length}`
        : " · proof OK"
      : opts.fabricReport?.overall === "green"
        ? " · proof (session)"
        : "";
  if (level === "GREEN") {
    return `Live GREEN${proof}`;
  }
  if (level === "AMBER") {
    return `Live AMBER${proof}${opts.meaning ? ` · ${opts.meaning}` : ""}`;
  }
  if (level === "RESTARTING") {
    return `Live RESTARTING · host recycling${proof}`;
  }
  if (level === "RED") {
    return `Live RED${proof}${opts.meaning ? ` · ${opts.meaning}` : ""}`;
  }
  if (opts.hostReady) return `Host up${proof}`;
  if (!opts.fabricReport) return "Not tested · required";
  return linkSummary(false, opts.fabricReport, Boolean(opts.proofCertified));
}

export type SealReadiness = {
  state: ChipState;
  title: string;
  body: string;
};

export function sealReadiness(opts: {
  fabricGreen: boolean;
  ntInstalled: boolean | null;
  secState: ChipState;
  fabricState: ChipState;
  canContinue: boolean;
  twinBirthReady?: boolean;
}): SealReadiness {
  if (opts.ntInstalled === false) {
    return {
      state: "fail",
      title: "Seal blocked",
      body: "Install NinjaTrader 8, then re-check.",
    };
  }
  if (!opts.fabricGreen) {
    return {
      state: opts.fabricState === "fail" ? "fail" : "partial",
      title: "Seal blocked",
      body: "Need live Fabric host + dual-plane proof (Test connection). Paper cert alone is not enough.",
    };
  }
  if (opts.twinBirthReady === false) {
    return {
      state: "partial",
      title: "Seal blocked",
      body: "Finish Twin base training (~10 min) before Genesis unlock.",
    };
  }
  if (opts.secState !== "ok" && opts.fabricState !== "ok") {
    return {
      state: "partial",
      title: "Almost ready",
      body: "Set security keys and confirm fabric token.",
    };
  }
  if (opts.canContinue) {
    return {
      state: "ok",
      title: "Ready to seal",
      body: "Fabric host+proof OK · Twin Birth-ready · Genesis unlocked.",
    };
  }
  return {
    state: "partial",
    title: "Seal pending",
    body: "Complete required fields, then Save & seal.",
  };
}

export function defaultVaultFocus(opts: {
  fabricGreen: boolean;
  ntInstalled: boolean | null;
  linkState: ChipState;
  twinBirthReady?: boolean;
}): VaultFocusId {
  if (opts.ntInstalled === false) return "nt_install";
  if (!opts.fabricGreen) {
    return opts.linkState === "fail" ? "diagnostic" : "fabric_token";
  }
  // After Fabric GREEN, Twin base is the next foundation block.
  if (opts.twinBirthReady === false) return "twin_base";
  return "jwt";
}

export function focusTitle(id: VaultFocusId): string {
  switch (id) {
    case "jwt":
      return "JWT secret";
    case "admin":
      return "Admin API key";
    case "fabric_token":
      return "Fabric token";
    case "diagnostic":
      return "Fabric diagnostic";
    case "telegram_bot":
      return "Telegram bot token";
    case "telegram_chat":
      return "Telegram chat id";
    case "crosstrade_token":
      return "Crosstrade token";
    case "crosstrade_account":
      return "Crosstrade account";
    case "nt_install":
      return "NinjaTrader install";
    case "twin_base":
      return "Twin base training";
    default:
      return "Detail";
  }
}

export function focusHint(id: VaultFocusId): string {
  switch (id) {
    case "jwt":
      return "Session signing · keep on this machine";
    case "admin":
      return "Deck controls · monitoring · approvals";
    case "fabric_token":
      return "Shared Brain ↔ NT8 secret · auto-installed";
    case "diagnostic":
      return "Test / repair results appear here after you run an action";
    case "telegram_bot":
      return "From @BotFather · optional alerts";
    case "telegram_chat":
      return "Private chat or group for operator alerts";
    case "crosstrade_token":
      return "Emergency feed only · not required for Genesis";
    case "crosstrade_account":
      return "Emergency feed account · optional";
    case "nt_install":
      return "NinjaTrader 8 is required for Fabric";
    case "twin_base":
      return "Operator judgment DNA · required before Birth";
    default:
      return "";
  }
}

/** Build compact focus rows for mission column (field rows only; diagnostic is a card). */
export function buildVaultFocusRows(opts: {
  creds: Creds;
  present: Record<string, boolean>;
  emergencyFeed: boolean;
  twinBirthReady?: boolean;
  twinCompletionPct?: number | null;
}): VaultFocusRow[] {
  const { creds, present, emergencyFeed } = opts;
  const twinReady = Boolean(opts.twinBirthReady);
  const twinPct = Number(opts.twinCompletionPct ?? 0);
  const rows: VaultFocusRow[] = [
    {
      id: "jwt",
      label: "JWT secret",
      summary: setOrMissing(creds.LUMINA_JWT_SECRET_KEY, present.LUMINA_JWT_SECRET_KEY),
      state: fieldFillState(creds.LUMINA_JWT_SECRET_KEY, present.LUMINA_JWT_SECRET_KEY),
      tip: "Session signing key",
      section: "security",
    },
    {
      id: "admin",
      label: "Admin API key",
      summary: setOrMissing(creds.LUMINA_ADMIN_API_KEY, present.LUMINA_ADMIN_API_KEY),
      state: fieldFillState(creds.LUMINA_ADMIN_API_KEY, present.LUMINA_ADMIN_API_KEY),
      tip: "Command deck + monitoring",
      section: "security",
    },
    {
      id: "fabric_token",
      label: "Fabric token",
      summary: setOrMissing(creds.LUMINA_FABRIC_TOKEN, present.LUMINA_FABRIC_TOKEN),
      state: fieldFillState(creds.LUMINA_FABRIC_TOKEN, present.LUMINA_FABRIC_TOKEN),
      tip: "Brain ↔ NT8 shared secret",
      section: "fabric",
    },
    {
      id: "twin_base",
      label: "Twin base training",
      summary: twinReady
        ? "Birth-ready"
        : twinPct > 0
          ? `${Math.round(twinPct)}% · in progress`
          : "Required · ~10 min",
      state: twinChipState(twinReady, twinPct),
      tip: "Your judgment DNA — required before Birth can start",
      section: "twin",
    },
    {
      id: "telegram_bot",
      label: "Telegram bot",
      summary: setOrMissing(creds.TELEGRAM_BOT_TOKEN, present.TELEGRAM_BOT_TOKEN, false),
      state: creds.TELEGRAM_BOT_TOKEN.trim() || present.TELEGRAM_BOT_TOKEN ? "ok" : "idle",
      tip: "Optional operator alerts",
      section: "alerts",
    },
    {
      id: "telegram_chat",
      label: "Telegram chat",
      summary: setOrMissing(creds.TELEGRAM_CHAT_ID, present.TELEGRAM_CHAT_ID, false),
      state: creds.TELEGRAM_CHAT_ID.trim() || present.TELEGRAM_CHAT_ID ? "ok" : "idle",
      tip: "Optional operator alerts",
      section: "alerts",
    },
  ];
  if (emergencyFeed) {
    rows.push(
      {
        id: "crosstrade_token",
        label: "Crosstrade token",
        summary: setOrMissing(creds.CROSSTRADE_TOKEN, undefined, false),
        state: creds.CROSSTRADE_TOKEN.trim() ? "ok" : "idle",
        tip: "Emergency fallback feed",
        section: "data",
      },
      {
        id: "crosstrade_account",
        label: "Crosstrade account",
        summary: setOrMissing(creds.CROSSTRADE_ACCOUNT, undefined, false),
        state: creds.CROSSTRADE_ACCOUNT.trim() ? "ok" : "idle",
        tip: "Emergency fallback feed",
        section: "data",
      },
    );
  }
  return rows;
}

export function diagnosticDisplayState(
  fabricGreen: boolean,
  fabricReport: FabricConnectionTestReport | null,
): ChipState {
  if (fabricGreen) return "ok";
  if (!fabricReport) return "partial";
  if (fabricReport.overall === "amber") return "partial";
  return "fail";
}

/** Build channel cards for the vault matrix (security / fabric / alerts / data). */
export function buildVaultChannelCards(opts: {
  secState: ChipState;
  fabricState: ChipState;
  linkState: ChipState;
  alertsState: ChipState;
  dataState: ChipState;
  emergencyFeed: boolean;
  fabricGreen: boolean;
  fabricReport: FabricConnectionTestReport | null;
  fabricCertified: boolean;
}): ChannelCardModel[] {
  const cards: ChannelCardModel[] = [
    {
      id: "security",
      label: "Security",
      summary:
        opts.secState === "ok"
          ? "JWT + admin set"
          : opts.secState === "partial"
            ? "Keys incomplete"
            : "Awaiting secrets",
      state: opts.secState,
      tip: "JWT secret and Admin API key for session + deck control",
    },
    {
      id: "fabric",
      label: "Fabric",
      summary: linkSummary(opts.fabricGreen, opts.fabricReport, opts.fabricCertified),
      state: opts.linkState === "idle" ? opts.fabricState : opts.linkState,
      tip: "Brain ↔ NinjaTrader 8 link · diagnostic must be GREEN",
    },
    {
      id: "alerts",
      label: "Alerts",
      summary:
        opts.alertsState === "ok"
          ? "Telegram ready"
          : opts.alertsState === "partial"
            ? "Telegram partial"
            : "Optional",
      state: opts.alertsState,
      tip: "Optional Telegram bot + chat for operator alerts",
    },
  ];
  if (opts.emergencyFeed) {
    cards.push({
      id: "data",
      label: "Data",
      summary:
        opts.dataState === "ok"
          ? "Emergency feed set"
          : opts.dataState === "partial"
            ? "Feed incomplete"
            : "Emergency only",
      state: opts.dataState,
      tip: "CrossTrade emergency market-data fallback",
    });
  }
  return cards;
}
