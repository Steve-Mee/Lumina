/** Col 3 — single-focus detail: one field editor or diagnostic results. */
import { toast } from "sonner";

import { CredentialsVaultNtBlock } from "@/components/onboarding/steps/CredentialsVaultChrome";
import { CredentialsVaultDiagnosticResults } from "@/components/onboarding/steps/CredentialsVaultDiagnosticResults";
import { VaultField } from "@/components/onboarding/steps/CredentialsVaultPrimitives";
import { TwinBaseTrainingWizard } from "@/components/operations/TwinBaseTrainingWizard";
import {
  fieldFillState,
  focusHint,
  focusTitle,
  type VaultFocusId,
} from "@/components/onboarding/steps/credentialsVaultState";
import {
  generateAdminKey,
  generateFabricToken,
  generateJwt,
} from "@/lib/credentialGenerators";
import { persistMonitoringApiKey } from "@/lib/monitoringClient";
import type { FabricConnectionTestReport, FabricHealResult } from "@/lib/setupClient";
import type { TwinReadiness } from "@/lib/twinClient";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { cn } from "@/lib/utils";

type Creds = OnboardingDraft["credentials"];

export function CredentialsVaultDetailPanel({
  focus,
  creds,
  present = {},
  onChange,
  fabricReport,
  fabricGreen,
  fabricReadyForSeal,
  liveLevel,
  fabricCertified,
  setFabricCertified,
  healResult,
  testingFabric,
  repairingFabric,
  ntInstalled,
  ntChecking,
  openNtInstall,
  onRecheckNt,
  twinReadiness,
  onTwinCompleted,
  className,
}: {
  focus: VaultFocusId;
  creds: Creds;
  present?: Record<string, boolean>;
  onChange: (credentials: Creds) => void;
  fabricReport: FabricConnectionTestReport | null;
  /** Live GREEN only. */
  fabricGreen: boolean;
  fabricReadyForSeal?: boolean;
  liveLevel?: string | null;
  fabricCertified: boolean;
  setFabricCertified: (v: boolean) => void;
  healResult: FabricHealResult | null;
  testingFabric: boolean;
  repairingFabric: boolean;
  ntInstalled: boolean | null;
  ntChecking: boolean;
  openNtInstall: () => void;
  onRecheckNt: () => void;
  twinReadiness?: TwinReadiness | null;
  onTwinCompleted?: () => void;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "credentials-vault-detail lumina-glass lumina-glass--overlay",
        className,
      )}
      aria-label="Operator vault detail"
    >
      <header className="credentials-vault-detail__toolbar">
        <p className="credentials-vault-detail__title">{focusTitle(focus)}</p>
        <p className="credentials-vault-detail__hint">{focusHint(focus)}</p>
      </header>
      <div className="credentials-vault-detail__body">
        {focus === "nt_install" || ntInstalled === false ? (
          <CredentialsVaultNtBlock
            ntChecking={ntChecking}
            openNtInstall={openNtInstall}
            onRecheck={onRecheckNt}
          />
        ) : null}

        {focus === "jwt" ? (
          <VaultField
            label="JWT secret"
            tip="Protects backend sessions. Generate once; never share."
            fieldState={fieldFillState(
              creds.LUMINA_JWT_SECRET_KEY,
              present.LUMINA_JWT_SECRET_KEY,
            )}
          >
            <div className="flex gap-2">
              <input
                className="onboarding-field font-mono text-[13px]"
                type="password"
                value={creds.LUMINA_JWT_SECRET_KEY}
                onChange={(e) =>
                  onChange({ ...creds, LUMINA_JWT_SECRET_KEY: e.target.value })
                }
                autoComplete="off"
              />
              <button
                type="button"
                className="onboarding-btn-outline shrink-0 rounded-md px-2.5 font-mono text-[0.6rem] uppercase tracking-wider"
                onClick={() =>
                  onChange({ ...creds, LUMINA_JWT_SECRET_KEY: generateJwt() })
                }
              >
                Generate
              </button>
            </div>
          </VaultField>
        ) : null}

        {focus === "admin" ? (
          <VaultField
            label="Admin API key"
            tip="Lets the Command Deck control the engine safely."
            fieldState={fieldFillState(
              creds.LUMINA_ADMIN_API_KEY,
              present.LUMINA_ADMIN_API_KEY,
            )}
          >
            <div className="flex gap-2">
              <input
                className="onboarding-field font-mono text-[13px]"
                type="password"
                value={creds.LUMINA_ADMIN_API_KEY}
                onChange={(e) => {
                  onChange({ ...creds, LUMINA_ADMIN_API_KEY: e.target.value });
                  if (e.target.value.trim()) persistMonitoringApiKey(e.target.value);
                }}
                autoComplete="off"
              />
              <button
                type="button"
                className="onboarding-btn-outline shrink-0 rounded-md px-2.5 font-mono text-[0.6rem] uppercase tracking-wider"
                onClick={() => {
                  const key = generateAdminKey();
                  onChange({ ...creds, LUMINA_ADMIN_API_KEY: key });
                  persistMonitoringApiKey(key);
                  toast.success("Admin API key generated");
                }}
              >
                Generate
              </button>
            </div>
          </VaultField>
        ) : null}

        {focus === "fabric_token" ? (
          <VaultField
            label="Fabric token"
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
        ) : null}

        {focus === "telegram_bot" ? (
          <VaultField
            label="Bot token"
            tip="From Telegram @BotFather."
            fieldState={
              creds.TELEGRAM_BOT_TOKEN.trim() || present.TELEGRAM_BOT_TOKEN
                ? "ok"
                : "idle"
            }
          >
            <input
              className="onboarding-field font-mono text-[13px]"
              type="password"
              value={creds.TELEGRAM_BOT_TOKEN}
              onChange={(e) =>
                onChange({ ...creds, TELEGRAM_BOT_TOKEN: e.target.value })
              }
              autoComplete="off"
              placeholder="from @BotFather"
            />
          </VaultField>
        ) : null}

        {focus === "telegram_chat" ? (
          <VaultField
            label="Chat id"
            tip="Your private chat or group id."
            fieldState={
              creds.TELEGRAM_CHAT_ID.trim() || present.TELEGRAM_CHAT_ID
                ? "ok"
                : "idle"
            }
          >
            <input
              className="onboarding-field text-[13px]"
              value={creds.TELEGRAM_CHAT_ID}
              onChange={(e) =>
                onChange({ ...creds, TELEGRAM_CHAT_ID: e.target.value })
              }
              placeholder="your chat or group id"
            />
          </VaultField>
        ) : null}

        {focus === "crosstrade_token" ? (
          <VaultField
            label="Crosstrade token"
            tip="Emergency feed token."
            fieldState={creds.CROSSTRADE_TOKEN.trim() ? "ok" : "idle"}
          >
            <input
              className="onboarding-field font-mono text-[13px]"
              type="password"
              value={creds.CROSSTRADE_TOKEN}
              onChange={(e) =>
                onChange({ ...creds, CROSSTRADE_TOKEN: e.target.value })
              }
              autoComplete="off"
            />
          </VaultField>
        ) : null}

        {focus === "crosstrade_account" ? (
          <VaultField
            label="Crosstrade account"
            fieldState={creds.CROSSTRADE_ACCOUNT.trim() ? "ok" : "idle"}
          >
            <input
              className="onboarding-field text-[13px]"
              value={creds.CROSSTRADE_ACCOUNT}
              onChange={(e) =>
                onChange({ ...creds, CROSSTRADE_ACCOUNT: e.target.value })
              }
            />
          </VaultField>
        ) : null}

        {focus === "diagnostic" ? (
          <CredentialsVaultDiagnosticResults
            fabricReport={fabricReport}
            fabricGreen={fabricGreen}
            fabricReadyForSeal={fabricReadyForSeal}
            liveLevel={liveLevel}
            fabricCertified={fabricCertified}
            healResult={healResult}
            testingFabric={testingFabric}
            repairingFabric={repairingFabric}
          />
        ) : null}

        {focus === "twin_base" ? (
          <div className="credentials-vault-twin-panel space-y-2">
            <p className="font-mono text-[0.55rem] leading-relaxed text-white/45">
              Foundation block: train the Twin on <strong className="text-white/70">your</strong>{" "}
              risk DNA (forced-choice, ~10–12 min). Without this, Birth cannot start.
            </p>
            <TwinBaseTrainingWizard
              variant="vault"
              readiness={twinReadiness}
              onCompleted={() => {
                toast.success("Twin Birth-ready — seal vault to continue");
                onTwinCompleted?.();
              }}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
