/** Vault channel tab panels for CredentialsStep (Tauri UI god split). */
import { toast } from "sonner";

import {
  StatusIcon,
  VaultField,
} from "@/components/onboarding/steps/CredentialsVaultPrimitives";
import { HelpTip } from "@/components/ui/HelpTip";
import { TabsContent } from "@/components/ui/tabs";
import {
  generateAdminKey,
  generateFabricToken,
  generateJwt,
} from "@/lib/credentialGenerators";
import { launchNinjaTrader } from "@/lib/ninjaTraderClient";
import { persistMonitoringApiKey } from "@/lib/monitoringClient";
import type { FabricConnectionTestReport } from "@/lib/setupClient";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { cn } from "@/lib/utils";

type Creds = OnboardingDraft["credentials"];

export interface CredentialsVaultTabPanelsProps {
  creds: Creds;
  onChange: (credentials: Creds) => void;
  fabricReport: FabricConnectionTestReport | null;
  fabricGreen: boolean;
  fabricCertified: boolean;
  setFabricCertified: (v: boolean) => void;
  testingFabric: boolean;
  emergencyFeed: boolean;
  setEmergencyFeed: (v: boolean) => void;
  onSelectDataTab: () => void;
  runFabricTest: () => void | Promise<void>;
  ntInstalled: boolean | null;
}

export function CredentialsVaultTabPanels({
  creds,
  onChange,
  fabricReport,
  fabricGreen,
  fabricCertified,
  setFabricCertified,
  testingFabric,
  emergencyFeed,
  setEmergencyFeed,
  onSelectDataTab,
  runFabricTest,
  ntInstalled,
}: CredentialsVaultTabPanelsProps) {
  return (
    <>
                <TabsContent
                  value="security"
                  className="credentials-vault-tab-content mt-0 data-[state=inactive]:hidden"
                >
                  <VaultField
                    label="JWT secret"
                    hint="Session signing · keep on this machine"
                    tip="Protects backend sessions. Generate once; never share."
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
                </TabsContent>

                <TabsContent
                  value="alerts"
                  className="credentials-vault-tab-content mt-0 data-[state=inactive]:hidden"
                >
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
                </TabsContent>

                <TabsContent
                  value="fabric"
                  className="credentials-vault-tab-content mt-0 data-[state=inactive]:hidden"
                >
                  <VaultField
                    label="Fabric token"
                    hint="Shared Brain ↔ NT8 secret · auto-installed"
                    tip="Primary execution link. Lumina can generate and install this for you."
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

                  <div className="credentials-vault-diag">
                    <div className="credentials-vault-diag__head">
                      <div className="flex items-center gap-1.5">
                        <p className="credentials-vault-diag__title">Fabric diagnostic</p>
                        <HelpTip text="Critical: must be GREEN before Neural Genesis. Proves auth, place, flatten, and SAFE_MODE." />
                      </div>
                      {fabricReport || fabricCertified ? (
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 font-mono text-[0.55rem] font-bold tracking-wider uppercase",
                            fabricGreen &&
                              "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/35",
                            !fabricGreen &&
                              fabricReport?.overall === "amber" &&
                              "bg-amber-500/15 text-amber-100 ring-1 ring-amber-400/35",
                            !fabricGreen &&
                              fabricReport?.overall === "red" &&
                              "bg-red-500/15 text-red-100 ring-1 ring-red-400/35",
                          )}
                        >
                          {fabricGreen ? "green" : fabricReport?.overall ?? "—"}
                        </span>
                      ) : (
                        <span className="font-mono text-[0.55rem] tracking-wider text-white/30 uppercase">
                          required
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      className="onboarding-cta w-full rounded-md py-2.5 text-[0.65rem]"
                      disabled={testingFabric || ntInstalled === false}
                      onClick={() => void runFabricTest()}
                    >
                      {testingFabric ? "Probing channels…" : "Run fabric diagnostic"}
                    </button>
                    {ntInstalled === true ? (
                      <button
                        type="button"
                        className="onboarding-btn-secondary mt-2 w-full rounded-md py-1.5 font-mono text-[0.55rem] tracking-wider uppercase"
                        onClick={() => void launchNinjaTrader()}
                      >
                        Launch / restart NinjaTrader
                      </button>
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
                        if (on) onSelectDataTab();
                      }}
                    />
                    <span>
                      <span className="flex items-center gap-1 font-medium text-white/80">
                        Emergency market-data fallback (CrossTrade)
                        <HelpTip text="Optional. Only if Fabric is down later. Not required for Genesis. Reveals the Data tab when enabled." />
                      </span>
                      <span className="mt-0.5 block text-[11px] text-white/40">
                        Unchecked by default · Fabric remains primary
                      </span>
                    </span>
                  </label>
                </TabsContent>

                {emergencyFeed ? (
                  <TabsContent
                    value="data"
                    className="credentials-vault-tab-content mt-0 data-[state=inactive]:hidden"
                  >
                    <div className="rounded-lg border border-violet-400/20 bg-violet-950/20 px-3 py-2">
                      <p className="font-mono text-[0.55rem] tracking-[0.14em] text-violet-200/90 uppercase">
                        Optional · emergency only
                      </p>
                      <p className="mt-1 text-[12px] leading-snug text-white/50">
                        Used only when Fabric is unavailable and fallback is enabled. Not required
                        for Genesis.
                      </p>
                    </div>
                    <VaultField
                      label="Crosstrade token (optional)"
                      tip="Emergency feed token. Leave empty if you only use Fabric."
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
                    <VaultField label="Crosstrade account (optional)">
                      <input
                        className="onboarding-field text-[13px]"
                        value={creds.CROSSTRADE_ACCOUNT}
                        onChange={(e) =>
                          onChange({ ...creds, CROSSTRADE_ACCOUNT: e.target.value })
                        }
                      />
                    </VaultField>
                  </TabsContent>
                ) : null}

    </>
  );
}
