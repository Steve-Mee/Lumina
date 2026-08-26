/** Col 2 — Birth-style mission control: chips, focus rows, diagnostic actions, seal. */
import { CredentialsVaultStatusStrip } from "@/components/onboarding/steps/CredentialsVaultChrome";
import type { ChipState } from "@/components/onboarding/steps/CredentialsVaultPrimitives";
import type {
  SealReadiness,
  VaultFocusId,
  VaultFocusRow,
} from "@/components/onboarding/steps/credentialsVaultState";
import { cn } from "@/lib/utils";

export function CredentialsVaultMissionColumn({
  envPath,
  bootstrapping,
  setupReviewActive,
  fabricGreen,
  fabricReadyForSeal = false,
  liveLevel = null,
  onBackToGenesis,
  importing,
  onImportAll,
  hasAdminApiKeyInEnv,
  syncingKey,
  onSyncAdminKey,
  secState,
  fabricState,
  linkState,
  twinState,
  alertsState,
  dataState,
  emergencyFeed,
  setEmergencyFeed,
  rows,
  focus,
  onFocus,
  diagState,
  diagSummary,
  testingFabric,
  repairingFabric,
  ntInstalled,
  onTest,
  onRepair,
  onLaunchNt,
  readiness,
  canContinue,
  saving,
  onContinue,
  className,
}: {
  envPath?: string;
  bootstrapping?: boolean;
  setupReviewActive?: boolean;
  /** Live GREEN only (Brain connected). */
  fabricGreen: boolean;
  /** Host + dual-plane proof — seal/continue. */
  fabricReadyForSeal?: boolean;
  /** SSOT live level: RED | AMBER | GREEN | RESTARTING */
  liveLevel?: string | null;
  onBackToGenesis?: () => void;
  importing: boolean;
  onImportAll: () => void;
  hasAdminApiKeyInEnv?: boolean;
  syncingKey: boolean;
  onSyncAdminKey: () => void;
  secState: ChipState;
  fabricState: ChipState;
  linkState: ChipState;
  twinState: ChipState;
  alertsState: ChipState;
  dataState: ChipState;
  emergencyFeed: boolean;
  setEmergencyFeed: (v: boolean) => void;
  rows: VaultFocusRow[];
  focus: VaultFocusId;
  onFocus: (id: VaultFocusId) => void;
  diagState: ChipState;
  diagSummary: string;
  testingFabric: boolean;
  repairingFabric: boolean;
  ntInstalled: boolean | null;
  onTest: () => void;
  onRepair: () => void;
  onLaunchNt: () => void;
  readiness: SealReadiness;
  canContinue: boolean;
  saving?: boolean;
  onContinue: () => void;
  className?: string;
}) {
  const securityRows = rows.filter((r) => r.section === "security");
  const fabricRows = rows.filter((r) => r.section === "fabric");
  const twinRows = rows.filter((r) => r.section === "twin");
  const alertRows = rows.filter((r) => r.section === "alerts");
  const dataRows = rows.filter((r) => r.section === "data");

  const renderRow = (row: VaultFocusRow) => {
    const active = focus === row.id;
    return (
      <button
        key={row.id}
        type="button"
        className="credentials-vault-focus-row"
        data-state={row.state === "idle" ? undefined : row.state}
        data-active={active ? "true" : "false"}
        title={row.tip}
        onClick={() => onFocus(row.id)}
      >
        <span className="credentials-vault-focus-row__dot" aria-hidden />
        <span className="credentials-vault-focus-row__meta">
          <span className="credentials-vault-focus-row__label">{row.label}</span>
          <span className="credentials-vault-focus-row__summary">{row.summary}</span>
        </span>
      </button>
    );
  };

  return (
    <section
      className={cn(
        "credentials-vault-mission lumina-glass lumina-glass--overlay",
        className,
      )}
      aria-label="Operator vault mission control"
    >
      <header className="credentials-vault-mission__toolbar">
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
          {setupReviewActive && onBackToGenesis && fabricReadyForSeal ? (
            <button
              type="button"
              className="onboarding-btn-secondary rounded-md px-2.5 py-1 font-mono text-[0.55rem] tracking-wider uppercase"
              onClick={() => onBackToGenesis()}
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
      </header>

      <CredentialsVaultStatusStrip
        secState={secState}
        fabricState={fabricState}
        linkState={linkState}
        twinState={twinState}
        alertsState={alertsState}
        dataState={dataState}
        emergencyFeed={emergencyFeed}
      />

      <div className="credentials-vault-mission__body">
        <p className="credentials-vault-mission__section">Security</p>
        {securityRows.map(renderRow)}

        <p className="credentials-vault-mission__section">Fabric</p>
        {fabricRows.map(renderRow)}

        <div
          className="credentials-vault-diag-card"
          data-state={diagState === "idle" ? undefined : diagState}
          data-active={focus === "diagnostic" ? "true" : "false"}
          role="group"
          aria-label="Fabric diagnostic"
          onClick={() => onFocus("diagnostic")}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onFocus("diagnostic");
            }
          }}
        >
          <div className="credentials-vault-diag-card__head">
            <p className="credentials-vault-diag-card__title">Fabric diagnostic</p>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 font-mono text-[0.5rem] font-bold tracking-wider uppercase",
                String(liveLevel || "").toUpperCase() === "GREEN" &&
                  "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/35",
                (String(liveLevel || "").toUpperCase() === "AMBER" ||
                  String(liveLevel || "").toUpperCase() === "RESTARTING" ||
                  (!liveLevel && diagState === "partial")) &&
                  "bg-amber-500/15 text-amber-100 ring-1 ring-amber-400/35",
                (String(liveLevel || "").toUpperCase() === "RED" ||
                  (!liveLevel && diagState === "fail")) &&
                  "bg-red-500/15 text-red-100 ring-1 ring-red-400/35",
                !liveLevel &&
                  diagState !== "partial" &&
                  diagState !== "fail" &&
                  "text-white/35",
              )}
            >
              {liveLevel
                ? String(liveLevel).toLowerCase()
                : fabricGreen
                  ? "green"
                  : diagState === "fail"
                    ? "red"
                    : diagState === "partial"
                      ? "…"
                      : "—"}
            </span>
          </div>
          <p className="mb-2 font-mono text-[0.55rem] text-white/40">{diagSummary}</p>
          <div
            className="credentials-vault-diag-card__actions"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="onboarding-cta rounded-md py-2 text-[0.62rem]"
              disabled={testingFabric || repairingFabric || ntInstalled === false}
              onClick={() => {
                onFocus("diagnostic");
                onTest();
              }}
            >
              {testingFabric ? "Probing…" : "Test connection"}
            </button>
            {(!fabricReadyForSeal ||
              diagState === "fail" ||
              diagState === "partial" ||
              String(liveLevel || "").toUpperCase() === "RED") &&
            ntInstalled !== false ? (
              <button
                type="button"
                className="credentials-vault-diag__btn-repair onboarding-cta rounded-md py-2 text-[0.62rem]"
                disabled={repairingFabric || testingFabric}
                onClick={() => {
                  onFocus("diagnostic");
                  onRepair();
                }}
              >
                {repairingFabric ? "Repairing…" : "Repair connection"}
              </button>
            ) : null}
            {ntInstalled === true ? (
              <button
                type="button"
                className="onboarding-btn-secondary rounded-md py-1.5 font-mono text-[0.52rem] tracking-wider uppercase"
                disabled={repairingFabric || testingFabric}
                onClick={() => {
                  onFocus("diagnostic");
                  onLaunchNt();
                }}
              >
                Launch / restart NT
              </button>
            ) : null}
          </div>
        </div>

        <p className="credentials-vault-mission__section">Twin · required</p>
        {twinRows.map(renderRow)}

        <p className="credentials-vault-mission__section">Alerts · optional</p>
        {alertRows.map(renderRow)}

        <label className="credentials-vault-emergency mt-1">
          <input
            type="checkbox"
            checked={emergencyFeed}
            onChange={(e) => {
              const on = e.target.checked;
              setEmergencyFeed(on);
              if (on) onFocus("crosstrade_token");
            }}
          />
          <span>
            <span className="font-medium text-white/80">Emergency market-data fallback</span>
            <span className="mt-0.5 block text-[11px] text-white/40">
              CrossTrade · optional · not required for Genesis
            </span>
          </span>
        </label>
        {dataRows.map(renderRow)}
      </div>

      <div
        className="credentials-vault-mission__readiness"
        data-state={readiness.state === "idle" ? undefined : readiness.state}
        role="status"
      >
        <p className="credentials-vault-mission__readiness-title">{readiness.title}</p>
        <p className="credentials-vault-mission__readiness-body">{readiness.body}</p>
      </div>

      <div className="credentials-vault-cta-bar">
        <button
          type="button"
          className="onboarding-cta"
          disabled={!canContinue || saving || ntInstalled === false}
          onClick={onContinue}
          title={
            !fabricReadyForSeal
              ? "Need live host + dual-plane proof (Test connection) before Genesis"
              : twinState !== "ok"
                ? "Finish Twin base training before seal"
                : "Seal vault and continue"
          }
        >
          {saving ? "Sealing…" : "Save & seal"}
        </button>
        {!fabricReadyForSeal ? (
          <p className="credentials-vault-seal-hint">
            Critical: Fabric host up + proof GREEN (not paper cert alone)
          </p>
        ) : twinState !== "ok" ? (
          <p className="credentials-vault-seal-hint">
            Critical: Twin base training required before Birth can start
          </p>
        ) : (
          <p
            className="credentials-vault-seal-hint"
            style={{
              color: "color-mix(in srgb, var(--status-ok-fg) 90%, white)",
            }}
          >
            Fabric GREEN · Twin Birth-ready · Genesis unlocked
          </p>
        )}
      </div>
    </section>
  );
}
