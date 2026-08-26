/** Fabric + LINK inspector panel (token, diagnostic, emergency toggle). */
import {
  StatusIcon,
  VaultField,
} from "@/components/onboarding/steps/CredentialsVaultPrimitives";
import { fieldFillState } from "@/components/onboarding/steps/credentialsVaultState";
import { HelpTip } from "@/components/ui/HelpTip";
import { generateFabricToken } from "@/lib/credentialGenerators";
import { launchNinjaTrader } from "@/lib/ninjaTraderClient";
import type { FabricConnectionTestReport, FabricHealResult } from "@/lib/setupClient";
import { distressPanelClass, warnOverlayBodyClass, warnOverlayTitleClass } from "@/lib/modePresentation";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { cn } from "@/lib/utils";

type Creds = OnboardingDraft["credentials"];

export function CredentialsVaultFabricPanel({
  creds,
  present = {},
  onChange,
  fabricReport,
  fabricGreen,
  fabricCertified,
  setFabricCertified,
  testingFabric,
  repairingFabric,
  healResult,
  emergencyFeed,
  setEmergencyFeed,
  onSelectDataChannel,
  runFabricTest,
  runFabricRepair,
  ntInstalled,
  highlightDiagnostic = false,
}: {
  creds: Creds;
  present?: Record<string, boolean>;
  onChange: (credentials: Creds) => void;
  fabricReport: FabricConnectionTestReport | null;
  fabricGreen: boolean;
  fabricCertified: boolean;
  setFabricCertified: (v: boolean) => void;
  testingFabric: boolean;
  repairingFabric: boolean;
  healResult: FabricHealResult | null;
  emergencyFeed: boolean;
  setEmergencyFeed: (v: boolean) => void;
  onSelectDataChannel?: () => void;
  runFabricTest: () => void | Promise<void>;
  runFabricRepair: () => void | Promise<void | FabricHealResult | null>;
  ntInstalled: boolean | null;
  highlightDiagnostic?: boolean;
}) {
  return (
    <div className="credentials-vault-channel-panel" data-panel="fabric">
      <VaultField
        label="Fabric token"
        hint="Shared Brain ↔ NT8 secret · auto-installed"
        tip="Primary execution link. Lumina can generate and install this for you."
        fieldState={fieldFillState(
          creds.LUMINA_FABRIC_TOKEN,
          present.LUMINA_FABRIC_TOKEN,
        )}
      >
        <div className="flex gap-2">
          <input
            className="onboarding-field font-mono text-[13px]"
            type="password"
            value={creds.LUMINA_FABRIC_TOKEN}
            onChange={(e) => {
              onChange({ ...creds, LUMINA_FABRIC_TOKEN: e.target.value });
              setFabricCertified(false);
            }}
            autoComplete="off"
          />
          <button
            type="button"
            className="onboarding-btn-outline shrink-0 rounded-md px-2.5 font-mono text-[0.6rem] uppercase tracking-wider"
            onClick={() => {
              onChange({
                ...creds,
                LUMINA_FABRIC_TOKEN: generateFabricToken(),
              });
              setFabricCertified(false);
            }}
          >
            Generate
          </button>
        </div>
      </VaultField>

      <div
        id="credentials-vault-fabric-diag"
        className={cn(
          "credentials-vault-diag",
          highlightDiagnostic && "ring-1 ring-cyan-400/30",
        )}
      >
        <div className="credentials-vault-diag__head">
          <div className="flex items-center gap-1.5">
            <p className="credentials-vault-diag__title">Fabric diagnostic</p>
            <HelpTip text="Genesis needs live host + dual-plane proof (orders + NT history). Primary color is LIVE status — not paper certificate alone. Use Repair if host is RED." />
          </div>
          {fabricReport || fabricCertified || fabricGreen ? (
            <span
              className={cn(
                "rounded-full px-2 py-0.5 font-mono text-[0.55rem] font-bold tracking-wider uppercase",
                fabricGreen &&
                  "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/35",
                !fabricGreen &&
                  (fabricCertified || fabricReport?.overall === "green") &&
                  "bg-amber-500/15 text-amber-100 ring-1 ring-amber-400/35",
                !fabricGreen &&
                  fabricReport?.overall === "amber" &&
                  "bg-amber-500/15 text-amber-100 ring-1 ring-amber-400/35",
                !fabricGreen &&
                  fabricReport?.overall === "red" &&
                  "bg-red-500/15 text-red-100 ring-1 ring-red-400/35",
              )}
            >
              {fabricGreen
                ? "live green"
                : fabricCertified || fabricReport?.overall === "green"
                  ? "proof ok"
                  : fabricReport?.overall ?? "—"}
            </span>
          ) : (
            <span className="font-mono text-[0.55rem] tracking-wider text-white/30 uppercase">
              required
            </span>
          )}
        </div>
        <div className="credentials-vault-diag__actions">
          <button
            type="button"
            className="onboarding-cta w-full rounded-md py-2.5 text-[0.65rem]"
            disabled={testingFabric || repairingFabric || ntInstalled === false}
            onClick={() => void runFabricTest()}
          >
            {testingFabric ? "Probing channels…" : "Test connection"}
          </button>
          {(!fabricGreen ||
            fabricReport?.overall === "red" ||
            fabricReport?.overall === "amber") &&
          ntInstalled !== false ? (
            <button
              type="button"
              className="credentials-vault-diag__btn-repair onboarding-cta w-full rounded-md py-2.5 text-[0.65rem]"
              disabled={repairingFabric || testingFabric}
              onClick={() => void runFabricRepair()}
            >
              {repairingFabric
                ? "Repairing… (NinjaTrader may restart)"
                : "Repair NinjaTrader connection"}
            </button>
          ) : null}
          {ntInstalled === true ? (
            <button
              type="button"
              className="onboarding-btn-secondary w-full rounded-md py-2 font-mono text-[0.55rem] tracking-wider uppercase"
              disabled={repairingFabric || testingFabric}
              onClick={() => void launchNinjaTrader()}
            >
              Launch / restart NinjaTrader
            </button>
          ) : null}
        </div>
        {healResult?.steps?.length ? (
          <ul className="credentials-vault-diag__list mt-2">
            {healResult.steps.map((s) => (
              <li key={s.id} className="credentials-vault-diag__row">
                <StatusIcon
                  status={
                    s.status === "pass"
                      ? "pass"
                      : s.status === "warn" || s.status === "skip"
                        ? "warn"
                        : "fail"
                  }
                />
                <div className="min-w-0 flex-1">
                  <p className="credentials-vault-diag__row-title">{s.title}</p>
                  <p className="credentials-vault-diag__row-msg">
                    {s.user_message || s.message}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
        {healResult?.needs_user?.length ? (
          <div className={cn("mt-2 rounded-md border px-2.5 py-2", distressPanelClass("warn"))}>
            <p className={cn("font-mono text-[0.55rem] tracking-wider uppercase", warnOverlayTitleClass())}>
              {healResult.needs_user[0].title}
            </p>
            <p className={cn("mt-1 text-[11px] leading-snug", warnOverlayBodyClass())}>
              {healResult.needs_user[0].body}
            </p>
          </div>
        ) : null}
        {fabricReport ? (
          <>
            <p className="mt-2 font-mono text-[0.55rem] tracking-wide text-white/35">
              {fabricReport.target} · {fabricReport.duration_ms}ms
            </p>
            <ul className="credentials-vault-diag__list">
              {fabricReport.checks.map((c) => (
                <li key={c.id} className="credentials-vault-diag__row">
                  <StatusIcon status={c.status} />
                  <div className="min-w-0 flex-1">
                    <p className="credentials-vault-diag__row-title">{c.title}</p>
                    <p className="credentials-vault-diag__row-msg">{c.message}</p>
                  </div>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </div>

      <label className="credentials-vault-emergency">
        <input
          type="checkbox"
          checked={emergencyFeed}
          onChange={(e) => {
            const on = e.target.checked;
            setEmergencyFeed(on);
            if (on) onSelectDataChannel?.();
          }}
        />
        <span>
          <span className="flex items-center gap-1 font-medium text-white/80">
            Emergency market-data fallback (CrossTrade)
            <HelpTip text="Optional. Only if Fabric is down later. Not required for Genesis. Reveals the Data channel when enabled." />
          </span>
          <span className="mt-0.5 block text-[11px] text-white/40">
            Unchecked by default · Fabric remains primary
          </span>
        </span>
      </label>
    </div>
  );
}
