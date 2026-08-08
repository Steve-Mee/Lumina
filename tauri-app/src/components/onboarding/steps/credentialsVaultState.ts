/** Pure chip-state helpers for Credentials vault (Tauri UI god split). */
import type { ChipState } from "@/components/onboarding/steps/CredentialsVaultPrimitives";
import type { FabricConnectionTestReport } from "@/lib/setupClient";
import type { OnboardingDraft } from "@/store/onboardingStore";

type Creds = OnboardingDraft["credentials"];

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
