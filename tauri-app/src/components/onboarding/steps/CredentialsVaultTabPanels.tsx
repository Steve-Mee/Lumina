/** Vault channel detail panels for CredentialsStep (Tauri UI god split). */
import { toast } from "sonner";

import { CredentialsVaultFabricPanel } from "@/components/onboarding/steps/CredentialsVaultFabricPanel";
import { VaultField } from "@/components/onboarding/steps/CredentialsVaultPrimitives";
import { fieldFillState } from "@/components/onboarding/steps/credentialsVaultState";
import { generateAdminKey, generateJwt } from "@/lib/credentialGenerators";
import { persistMonitoringApiKey } from "@/lib/monitoringClient";
import type { FabricConnectionTestReport, FabricHealResult } from "@/lib/setupClient";
import type { OnboardingDraft } from "@/store/onboardingStore";

type Creds = OnboardingDraft["credentials"];

export type VaultInspectorPanel = "security" | "fabric" | "alerts" | "data";

export interface CredentialsVaultTabPanelsProps {
  panel: VaultInspectorPanel;
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
}

export function CredentialsVaultTabPanels({
  panel,
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
}: CredentialsVaultTabPanelsProps) {
  if (panel === "security") {
    return (
      <div className="credentials-vault-channel-panel" data-panel="security">
        <VaultField
          label="JWT secret"
          hint="Session signing · keep on this machine"
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

        <VaultField
          label="Admin API key"
          hint="Deck controls · monitoring · approvals"
          tip="Lets the Command Deck control the engine safely. Generate a new key if you do not have one."
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
      </div>
    );
  }

  if (panel === "alerts") {
    return (
      <div className="credentials-vault-channel-panel" data-panel="alerts">
        <div className="credentials-vault-field-card !border-transparent !bg-transparent !p-0 !shadow-none">
          <p className="credentials-vault-field-label">Alerts · Telegram</p>
          <p className="credentials-vault-field-hint">
            Milestones and problems (SAFE_MODE, Fabric halt) are sent here. Optional but
            recommended.
          </p>
        </div>
        <VaultField
          label="Bot token"
          tip="From Telegram @BotFather. Used only for operator notifications."
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
        <VaultField
          label="Chat id"
          tip="Your private chat or group id that should receive Lumina alerts."
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
      </div>
    );
  }

  if (panel === "data") {
    return (
      <div className="credentials-vault-channel-panel" data-panel="data">
        <div className="rounded-lg border border-violet-400/20 bg-violet-950/20 px-3 py-2">
          <p className="font-mono text-[0.55rem] tracking-[0.14em] text-violet-200/90 uppercase">
            Optional · emergency only
          </p>
          <p className="mt-1 text-[12px] leading-snug text-white/50">
            Used only when Fabric is unavailable and fallback is enabled. Not required for
            Genesis.
          </p>
        </div>
        <VaultField
          label="Crosstrade token (optional)"
          tip="Emergency feed token. Leave empty if you only use Fabric."
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
        <VaultField
          label="Crosstrade account (optional)"
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
      </div>
    );
  }

  return (
    <CredentialsVaultFabricPanel
      creds={creds}
      present={present}
      onChange={onChange}
      fabricReport={fabricReport}
      fabricGreen={fabricGreen}
      fabricCertified={fabricCertified}
      setFabricCertified={setFabricCertified}
      testingFabric={testingFabric}
      repairingFabric={repairingFabric}
      healResult={healResult}
      emergencyFeed={emergencyFeed}
      setEmergencyFeed={setEmergencyFeed}
      onSelectDataChannel={onSelectDataChannel}
      runFabricTest={runFabricTest}
      runFabricRepair={runFabricRepair}
      ntInstalled={ntInstalled}
      highlightDiagnostic={highlightDiagnostic}
    />
  );
}
