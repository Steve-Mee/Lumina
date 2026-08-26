/** Status strip + NT install block for Credentials vault (Tauri UI god split). */
import {
  StatusChip,
  type ChipState,
} from "@/components/onboarding/steps/CredentialsVaultPrimitives";

export function CredentialsVaultStatusStrip({
  secState,
  fabricState,
  linkState,
  twinState,
  alertsState,
  dataState,
  emergencyFeed,
}: {
  secState: ChipState;
  fabricState: ChipState;
  linkState: ChipState;
  twinState?: ChipState;
  alertsState: ChipState;
  dataState: ChipState;
  emergencyFeed: boolean;
}) {
  return (
    <div className="credentials-vault-status-strip" role="status" aria-label="Channel status">
      <StatusChip
        label="SECURITY"
        state={secState}
        tip="JWT + Admin API key. Partial if only one is set."
      />
      <StatusChip
        label="FABRIC"
        state={fabricState}
        tip="Fabric token present for Brain ↔ NT8."
      />
      <StatusChip
        label="LINK"
        state={linkState}
        tip="Fabric diagnostic result. Must be GREEN to seal and enter Genesis."
      />
      <StatusChip
        label="TWIN"
        state={twinState ?? "idle"}
        tip="Twin base training (your judgment DNA). Required before Birth can start."
      />
      <StatusChip
        label="ALERTS"
        state={alertsState}
        tip="Telegram bot + chat for milestones and problems. Optional but recommended."
      />
      {emergencyFeed ? (
        <StatusChip
          label="DATA"
          state={dataState}
          tip="Emergency CrossTrade feed. Only used if you opted in."
        />
      ) : null}
    </div>
  );
}

export function CredentialsVaultNtBlock({
  ntChecking,
  openNtInstall,
  onRecheck,
}: {
  ntChecking: boolean;
  openNtInstall: () => void;
  onRecheck: () => void;
}) {
  return (
    <div className="credentials-vault-nt-block mb-2 shrink-0">
      <p className="credentials-vault-nt-block__title">NinjaTrader 8 required</p>
      <p className="credentials-vault-nt-block__body">
        Install NinjaTrader 8, then re-check. Lumina deploys the Fabric AddOn automatically.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="onboarding-cta rounded-md px-3 py-2 text-[0.65rem]"
          onClick={openNtInstall}
        >
          Install NinjaTrader
        </button>
        <button
          type="button"
          className="onboarding-btn-secondary rounded-md px-3 py-2 font-mono text-[0.55rem] uppercase tracking-wider"
          disabled={ntChecking}
          onClick={onRecheck}
        >
          {ntChecking ? "Checking…" : "I installed it — re-check"}
        </button>
      </div>
    </div>
  );
}
