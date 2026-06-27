import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { generateTauriSigningKey } from "@/lib/setupClient";
import { persistMonitoringApiKey } from "@/lib/monitoringClient";
import {
  credentialsReadyInDraft,
  credentialsReadyInEnv,
} from "@/lib/credentialsPrefill";
import { luminaSurfaceMutedClass } from "@/lib/glassGlowTaxonomy";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { distressPanelClass } from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

interface CredentialsStepProps {
  draft: OnboardingDraft;
  missing: string[];
  present?: Record<string, boolean>;
  envPath?: string;
  hasAdminApiKeyInEnv?: boolean;
  wizardRequired?: boolean;
  skipReason?: "env_configured" | "setup_complete" | null;
  saving?: boolean;
  onChange: (credentials: OnboardingDraft["credentials"]) => void;
  onContinue: () => void;
  onImportFromEnv: () => Promise<boolean>;
}

function generateJwt(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").slice(0, 32);
}

export function CredentialsStep({
  draft,
  missing,
  present = {},
  envPath,
  hasAdminApiKeyInEnv,
  wizardRequired = true,
  skipReason,
  saving,
  onChange,
  onContinue,
  onImportFromEnv,
}: CredentialsStepProps) {
  const creds = draft.credentials;
  const [syncingKey, setSyncingKey] = useState(false);
  const [importing, setImporting] = useState(false);

  const alreadyConfigured =
    !wizardRequired || (missing.length === 0 && credentialsReadyInEnv(present));

  const canContinue =
    alreadyConfigured ||
    credentialsReadyInDraft(creds) ||
    credentialsReadyInEnv(present);

  const handleSyncAdminKey = async () => {
    setSyncingKey(true);
    try {
      const ok = await onImportFromEnv();
      if (ok && draft.credentials.LUMINA_ADMIN_API_KEY.trim()) {
        toast.success("Deck connected to backend admin key");
      } else if (ok) {
        toast.success("Credentials imported from .env");
      } else {
        toast.error("Could not read credentials from backend .env");
      }
    } finally {
      setSyncingKey(false);
    }
  };

  const handleImportAll = async () => {
    setImporting(true);
    try {
      const ok = await onImportFromEnv();
      if (ok) {
        toast.success("Credentials imported from .env");
      } else {
        toast.error("Import failed — is the backend running on port 8000?");
      }
    } finally {
      setImporting(false);
    }
  };

  const missingHints = useMemo(() => {
    if (alreadyConfigured) return [];
    return missing.map((key) => {
      const inEnv = present[key] === true;
      const inForm = Boolean(creds[key as keyof typeof creds]?.trim());
      if (inEnv && !inForm) {
        return { key, message: `Found in .env — click Import from .env`, tone: "info" as const };
      }
      return {
        key,
        message: envPath
          ? `Add ${key} to ${envPath}`
          : `Add ${key} to your workspace .env file`,
        tone: "warn" as const,
      };
    });
  }, [missing, present, creds, envPath, alreadyConfigured]);

  const skipMessage =
    skipReason === "setup_complete"
      ? "Setup was already completed. Change credentials later in Admin."
      : "Required credentials are already in your workspace .env. Change them later in Admin.";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto w-full max-w-xl p-2 md:p-4"
    >
      <h2 className="mb-2 text-lg font-semibold">Connection Credentials</h2>

      {alreadyConfigured ? (
        <>
          <p className="onboarding-muted mb-4 text-sm">{skipMessage}</p>
          {envPath ? (
            <p className="onboarding-muted mb-6 font-mono text-[10px] break-all">{envPath}</p>
          ) : null}
          <button
            type="button"
            className="onboarding-cta w-full py-5"
            disabled={saving}
            onClick={onContinue}
          >
            {saving ? "Continuing…" : "Continue"}
          </button>
        </>
      ) : (
        <>
          <p className="onboarding-muted mb-2 text-sm">
            Required for Crosstrade data and backend security. Stored locally in{" "}
            <span className="font-mono text-cyan-200/80">.env</span>.
          </p>
          {envPath ? (
            <p className="onboarding-muted mb-4 font-mono text-[10px] break-all">{envPath}</p>
          ) : null}

          {missingHints.length > 0 ? (
            <ul className={cn("mb-4 space-y-2 rounded-lg px-3 py-2 text-xs", distressPanelClass())}>
              {missingHints.map((item) => (
                <li
                  key={item.key}
                  className={cn(
                    item.tone === "info" ? "text-cyan-200/90" : "text-amber-200/90",
                  )}
                >
                  <span className="font-mono">{item.key}</span>: {item.message}
                </li>
              ))}
            </ul>
          ) : null}

          <div className="mb-4 flex flex-wrap gap-2">
            <button
              type="button"
              className="onboarding-btn-secondary"
              disabled={importing}
              onClick={() => void handleImportAll()}
            >
              {importing ? "Importing…" : "Import from .env"}
            </button>
            {hasAdminApiKeyInEnv ? (
              <button
                type="button"
                className="onboarding-btn-secondary"
                disabled={syncingKey}
                onClick={() => void handleSyncAdminKey()}
              >
                {syncingKey ? "Syncing…" : "Use key from backend"}
              </button>
            ) : null}
          </div>

          <div className="space-y-4">
            <div>
              <label className="onboarding-muted mb-1 block text-xs uppercase">JWT Secret</label>
              <div className="flex gap-2">
                <input
                  className="onboarding-field font-mono"
                  type="password"
                  value={creds.LUMINA_JWT_SECRET_KEY}
                  onChange={(e) => onChange({ ...creds, LUMINA_JWT_SECRET_KEY: e.target.value })}
                />
                <button
                  type="button"
                  className="onboarding-btn-outline shrink-0"
                  onClick={() => onChange({ ...creds, LUMINA_JWT_SECRET_KEY: generateJwt() })}
                >
                  Generate
                </button>
              </div>
            </div>
            <div>
              <label className="onboarding-muted mb-1 block text-xs uppercase">
                Dashboard Admin API Key
              </label>
              <input
                className="onboarding-field font-mono"
                type="password"
                value={creds.LUMINA_ADMIN_API_KEY}
                onChange={(e) => {
                  onChange({ ...creds, LUMINA_ADMIN_API_KEY: e.target.value });
                  if (e.target.value.trim()) {
                    persistMonitoringApiKey(e.target.value);
                  }
                }}
                placeholder="Same value as LUMINA_ADMIN_API_KEY in .env"
              />
              <p className="onboarding-muted mt-1 text-[10px]">
                Powers engine controls, monitoring, and evolution approvals in the command deck.
              </p>
            </div>
            <div>
              <label className="onboarding-muted mb-1 block text-xs uppercase">Crosstrade Token</label>
              <input
                className="onboarding-field font-mono"
                type="password"
                value={creds.CROSSTRADE_TOKEN}
                onChange={(e) => onChange({ ...creds, CROSSTRADE_TOKEN: e.target.value })}
              />
            </div>
            <div>
              <label className="onboarding-muted mb-1 block text-xs uppercase">Crosstrade Account</label>
              <input
                className="onboarding-field"
                value={creds.CROSSTRADE_ACCOUNT}
                onChange={(e) => onChange({ ...creds, CROSSTRADE_ACCOUNT: e.target.value })}
              />
            </div>
          </div>

          <details className={luminaSurfaceMutedClass("mt-6 rounded-lg border border-white/10 p-3 text-sm")}>
            <summary className="onboarding-muted cursor-pointer font-medium">Optional integrations</summary>
            <div className="mt-3 space-y-3">
              <div>
                <label className="onboarding-muted mb-1 block text-xs uppercase">xAI API key</label>
                <input
                  className="onboarding-field font-mono"
                  type="password"
                  value={creds.XAI_API_KEY}
                  onChange={(e) => onChange({ ...creds, XAI_API_KEY: e.target.value })}
                />
              </div>
              <div>
                <label className="onboarding-muted mb-1 block text-xs uppercase">Telegram bot token</label>
                <input
                  className="onboarding-field font-mono"
                  type="password"
                  value={creds.TELEGRAM_BOT_TOKEN}
                  onChange={(e) => onChange({ ...creds, TELEGRAM_BOT_TOKEN: e.target.value })}
                />
              </div>
              <div>
                <label className="onboarding-muted mb-1 block text-xs uppercase">Telegram chat id</label>
                <input
                  className="onboarding-field"
                  value={creds.TELEGRAM_CHAT_ID}
                  onChange={(e) => onChange({ ...creds, TELEGRAM_CHAT_ID: e.target.value })}
                />
              </div>
            </div>
          </details>

          <details className={luminaSurfaceMutedClass("mt-4 rounded-lg border border-white/10 p-3 text-sm")}>
            <summary className="onboarding-muted cursor-pointer font-medium">
              Desktop updater signing (optional)
            </summary>
            <p className="onboarding-muted mt-2 text-xs">
              Generate Tauri minisign keys for release builds. Requires Node.js/npm on this machine.
            </p>
            <button
              type="button"
              className="onboarding-btn-outline mt-3"
              onClick={() =>
                void generateTauriSigningKey(false)
                  .then((r) => toast.success(r.message || "Signing key generated"))
                  .catch((e) => toast.error(e instanceof Error ? e.message : "Signing key failed"))
              }
            >
              Generate signing key
            </button>
          </details>

          <button
            type="button"
            className="onboarding-cta mt-8 w-full py-5"
            disabled={!canContinue || saving}
            onClick={onContinue}
          >
            {saving ? "Saving…" : "Save & Continue"}
          </button>
        </>
      )}
    </motion.div>
  );
}
