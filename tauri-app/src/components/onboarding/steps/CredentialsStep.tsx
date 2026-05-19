import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import type { OnboardingDraft } from "@/store/onboardingStore";

interface CredentialsStepProps {
  draft: OnboardingDraft;
  missing: string[];
  onChange: (credentials: OnboardingDraft["credentials"]) => void;
  onContinue: () => void;
}

function generateJwt(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").slice(0, 32);
}

export function CredentialsStep({ draft, missing, onChange, onContinue }: CredentialsStepProps) {
  const creds = draft.credentials;

  const canContinue =
    creds.LUMINA_JWT_SECRET_KEY.trim() &&
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

      <Button
        className="onboarding-cta mt-8 w-full py-5"
        disabled={!canContinue}
        onClick={onContinue}
      >
        Continue
      </Button>
    </motion.div>
  );
}
