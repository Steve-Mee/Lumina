import { motion } from "framer-motion";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { generateTauriSigningKey } from "@/lib/setupClient";
import type { OnboardingDraft } from "@/store/onboardingStore";
interface CredentialsStepProps {
  draft: OnboardingDraft;
  missing: string[];
  hasAdminApiKeyInEnv?: boolean;
  saving?: boolean;
  onChange: (credentials: OnboardingDraft["credentials"]) => void;
  onContinue: () => void;
}

function generateJwt(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").slice(0, 32);
}

export function CredentialsStep({
  draft,
  missing,
  hasAdminApiKeyInEnv,
  saving,
  onChange,
  onContinue,
}: CredentialsStepProps) {
  const creds = draft.credentials;

  const canContinue =
    creds.LUMINA_JWT_SECRET_KEY.trim() &&
    creds.LUMINA_ADMIN_API_KEY.trim() &&
    creds.CROSSTRADE_TOKEN.trim() &&
    creds.CROSSTRADE_ACCOUNT.trim();

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="onboarding-card mx-auto max-w-xl p-8"
    >
      <h2 className="mb-2 text-lg font-semibold">Connection Credentials</h2>
      <p className="mb-6 text-sm text-muted-foreground">
        Required for Crosstrade data and backend security. Stored locally in{" "}
        <span className="font-mono text-cyan-200/70">.env</span>.
      </p>

      {missing.length > 0 && (
        <p className="mb-4 text-xs text-amber-300/90">
          Missing: {missing.join(", ")}
        </p>
      )}

      {hasAdminApiKeyInEnv ? (
        <p className="mb-4 rounded-lg border border-emerald-500/25 bg-emerald-950/20 px-3 py-2 text-xs text-emerald-100/90">
          Admin key detected in <span className="font-mono">.env</span> — paste the same value below
          so the command deck can reach monitoring and runtime APIs.
        </p>
      ) : null}

      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-xs text-muted-foreground uppercase">JWT Secret</label>
          <div className="flex gap-2">
            <input
              className="onboarding-field font-mono"
              type="password"
              value={creds.LUMINA_JWT_SECRET_KEY}
              onChange={(e) => onChange({ ...creds, LUMINA_JWT_SECRET_KEY: e.target.value })}
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => onChange({ ...creds, LUMINA_JWT_SECRET_KEY: generateJwt() })}
            >
              Generate
            </Button>
          </div>
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted-foreground uppercase">
            Dashboard Admin API Key
          </label>
          <input
            className="onboarding-field font-mono"
            type="password"
            value={creds.LUMINA_ADMIN_API_KEY}
            onChange={(e) => onChange({ ...creds, LUMINA_ADMIN_API_KEY: e.target.value })}
            placeholder="Same value as LUMINA_ADMIN_API_KEY in .env"
          />
          <p className="mt-1 text-[10px] text-muted-foreground">
            Powers engine controls, monitoring, and evolution approvals in the command deck.
          </p>
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted-foreground uppercase">
            Crosstrade Token
          </label>
          <input
            className="onboarding-field font-mono"
            type="password"
            value={creds.CROSSTRADE_TOKEN}
            onChange={(e) => onChange({ ...creds, CROSSTRADE_TOKEN: e.target.value })}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted-foreground uppercase">
            Crosstrade Account
          </label>
          <input
            className="onboarding-field"
            value={creds.CROSSTRADE_ACCOUNT}
            onChange={(e) => onChange({ ...creds, CROSSTRADE_ACCOUNT: e.target.value })}
          />
        </div>
      </div>

      <details className="mt-6 rounded-lg border border-white/10 bg-black/20 p-3 text-sm">
        <summary className="cursor-pointer font-medium text-muted-foreground">
          Desktop updater signing (optional)
        </summary>
        <p className="mt-2 text-xs text-muted-foreground">
          Generate Tauri minisign keys for release builds. Requires Node.js/npm on this machine.
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={() =>
            void generateTauriSigningKey(false)
              .then((r) => toast.success(r.message || "Signing key generated"))
              .catch((e) => toast.error(e instanceof Error ? e.message : "Signing key failed"))
          }
        >
          Generate signing key
        </Button>
      </details>

      <Button        className="onboarding-cta mt-8 w-full py-5"
        disabled={!canContinue || saving}
        onClick={onContinue}
      >
        {saving ? "Saving…" : "Save & Continue"}
      </Button>
    </motion.div>
  );
}
