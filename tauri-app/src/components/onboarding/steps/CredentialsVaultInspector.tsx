/** Col 3 — channel inspector: toolbar, scroll body, seal CTA. */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function CredentialsVaultInspector({
  envPath,
  bootstrapping,
  setupReviewActive,
  fabricGreen,
  onBackToGenesis,
  importing,
  onImportAll,
  hasAdminApiKeyInEnv,
  syncingKey,
  onSyncAdminKey,
  children,
  canContinue,
  saving,
  ntInstalled,
  onContinue,
  className,
}: {
  envPath?: string;
  bootstrapping?: boolean;
  setupReviewActive?: boolean;
  fabricGreen: boolean;
  onBackToGenesis?: () => void;
  importing: boolean;
  onImportAll: () => void;
  hasAdminApiKeyInEnv?: boolean;
  syncingKey: boolean;
  onSyncAdminKey: () => void;
  children: ReactNode;
  canContinue: boolean;
  saving?: boolean;
  ntInstalled: boolean | null;
  onContinue: () => void;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "credentials-vault-inspector credentials-vault-panel lumina-glass lumina-glass--overlay",
        className,
      )}
      aria-label="Operator vault inspector"
    >
      <div className="credentials-vault-panel__toolbar">
        <div className="min-w-0">
          <p className="credentials-vault-panel__toolbar-title">Operator vault</p>
          <p className="mt-0.5 font-mono text-[0.5rem] tracking-wide text-white/30 uppercase">
            Fabric primary
            {bootstrapping ? " · bootstrapping…" : ""}
          </p>
          {envPath ? (
            <p
              className="mt-0.5 truncate font-mono text-[0.5rem] tracking-wide text-white/25"
              title={envPath}
            >
              {envPath}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
          {setupReviewActive && onBackToGenesis && fabricGreen ? (
            <button
              type="button"
              className="onboarding-btn-secondary rounded-md px-2.5 py-1 font-mono text-[0.55rem] tracking-wider uppercase"
              onClick={() => onBackToGenesis()}
              title="Return to Neural Genesis (host+proof ready)"
            >
              Genesis
            </button>
          ) : null}
          <button
            type="button"
            className="onboarding-btn-secondary rounded-md px-2.5 py-1 font-mono text-[0.55rem] tracking-wider uppercase"
            disabled={importing}
            onClick={() => onImportAll()}
          >
            {importing ? "…" : "Import .env"}
          </button>
          {hasAdminApiKeyInEnv ? (
            <button
              type="button"
              className="onboarding-btn-secondary rounded-md px-2.5 py-1 font-mono text-[0.55rem] tracking-wider uppercase"
              disabled={syncingKey}
              onClick={() => onSyncAdminKey()}
            >
              {syncingKey ? "…" : "Sync key"}
            </button>
          ) : null}
        </div>
      </div>

      <div className="credentials-vault-inspector__body">{children}</div>

      <div className="credentials-vault-cta-bar">
        <button
          type="button"
          className="onboarding-cta"
          disabled={!canContinue || saving || ntInstalled === false}
          onClick={onContinue}
          title={
            fabricGreen
              ? "Seal vault and continue"
              : "Need live Fabric host + dual-plane proof before Genesis"
          }
        >
          {saving ? "Sealing…" : "Save & seal"}
        </button>
        {!fabricGreen ? (
          <p className="credentials-vault-seal-hint">
            Critical: Fabric host up + proof GREEN (not paper cert alone)
          </p>
        ) : (
          <p
            className="credentials-vault-seal-hint"
            style={{
              color: "color-mix(in srgb, var(--status-ok-fg) 90%, white)",
            }}
          >
            Fabric host+proof OK · Genesis unlocked
          </p>
        )}
      </div>
    </section>
  );
}
