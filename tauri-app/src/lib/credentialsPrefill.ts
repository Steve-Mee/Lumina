import type { OnboardingDraft } from "@/store/onboardingStore";

/** Keys required to pass the credentials wizard step (first boot). */
export const REQUIRED_WIZARD_CREDENTIAL_KEYS = [
  "LUMINA_JWT_SECRET_KEY",
  "CROSSTRADE_TOKEN",
  "CROSSTRADE_ACCOUNT",
  "LUMINA_ADMIN_API_KEY",
] as const;

export const CREDENTIAL_ENV_KEYS = [
  "LUMINA_JWT_SECRET_KEY",
  "CROSSTRADE_TOKEN",
  "CROSSTRADE_ACCOUNT",
  "LUMINA_ADMIN_API_KEY",
  "XAI_API_KEY",
  "TELEGRAM_BOT_TOKEN",
  "TELEGRAM_CHAT_ID",
] as const;

export type CredentialEnvKey = (typeof CREDENTIAL_ENV_KEYS)[number];

export interface DeckCredentialsPrefillResponse {
  env_path: string;
  present: Partial<Record<CredentialEnvKey, boolean>>;
  credentials: Partial<Record<CredentialEnvKey, string>>;
}

export function credentialsReadyInEnv(present: Record<string, boolean> = {}): boolean {
  return REQUIRED_WIZARD_CREDENTIAL_KEYS.every((key) => present[key] === true);
}

export function credentialsReadyInDraft(
  creds: OnboardingDraft["credentials"],
): boolean {
  return REQUIRED_WIZARD_CREDENTIAL_KEYS.every((key) => Boolean(creds[key]?.trim()));
}

/** Merge .env values into draft without overwriting operator edits. */
export function mergeCredentialsIntoDraft(
  draft: OnboardingDraft["credentials"],
  prefill: Partial<Record<CredentialEnvKey, string>>,
): OnboardingDraft["credentials"] {
  const next = { ...draft };
  for (const key of CREDENTIAL_ENV_KEYS) {
    const incoming = prefill[key]?.trim();
    if (incoming && !next[key].trim()) {
      next[key] = incoming;
    }
  }
  return next;
}
