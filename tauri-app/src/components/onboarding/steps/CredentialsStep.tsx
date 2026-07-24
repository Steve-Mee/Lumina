import { useEffect, useMemo, useState, type ReactNode } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  CheckCircle2,
  CircleAlert,
  CircleDashed,
  TriangleAlert,
} from "lucide-react";

import { CredentialsVaultOrganism } from "@/components/onboarding/CredentialsVaultOrganism";
import { HelpTip } from "@/components/ui/HelpTip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  postFabricBootstrap,
  postFabricConnectionTest,
  postFabricNtWatch,
  type FabricConnectionTestReport,
} from "@/lib/setupClient";
import { persistMonitoringApiKey } from "@/lib/monitoringClient";
import {
  credentialsReadyInDraft,
  credentialsReadyInEnv,
} from "@/lib/credentialsPrefill";
import {
  detectNinjaTrader,
  launchNinjaTrader,
  NINJATRADER_DOWNLOAD_URL,
} from "@/lib/ninjaTraderClient";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { cn } from "@/lib/utils";

interface CredentialsStepProps {
  draft: OnboardingDraft;
  missing: string[];
  present?: Record<string, boolean>;
  envPath?: string;
  hasAdminApiKeyInEnv?: boolean;
  wizardRequired?: boolean;
  skipReason?: "env_configured" | "setup_complete" | null;
  setupReviewActive?: boolean;
  saving?: boolean;
  onChange: (credentials: OnboardingDraft["credentials"]) => void;
  onContinue: () => void;
  onImportFromEnv: () => Promise<boolean>;
  onBackToGenesis?: () => void;
}

type VaultTab = "security" | "fabric" | "alerts" | "data";
type ChipState = "idle" | "ok" | "partial" | "fail";

function generateJwt(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").slice(0, 32);
}

function generateFabricToken(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

/** Match backend auto-gen style: sk_ + 32 hex bytes. */
function generateAdminKey(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `sk_${hex}`;
}

function VaultField({
  label,
  hint,
  tip,
  children,
}: {
  label: string;
  hint?: string;
  tip?: string;
  children: ReactNode;
}) {
  return (
    <div className="credentials-vault-field-card">
      <div className="mb-0.5 flex items-center gap-1.5">
        <p className="credentials-vault-field-label mb-0">{label}</p>
        {tip ? <HelpTip text={tip} /> : null}
      </div>
      {children}
      {hint ? <p className="credentials-vault-field-hint">{hint}</p> : null}
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === "pass") {
    return <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-300" aria-hidden />;
  }
  if (status === "fail") {
    return <CircleAlert className="mt-0.5 size-3.5 shrink-0 text-red-300" aria-hidden />;
  }
  if (status === "warn") {
    return <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-amber-300" aria-hidden />;
  }
  return <CircleDashed className="mt-0.5 size-3.5 shrink-0 text-white/35" aria-hidden />;
}

function StatusChip({
  label,
  state,
  tip,
}: {
  label: string;
  state: ChipState;
  tip: string;
}) {
  return (
    <span
      className="credentials-vault-status-chip"
      data-state={state === "idle" ? undefined : state}
      title={tip}
    >
      <span className="credentials-vault-status-chip__dot" />
      {label}
    </span>
  );
}

export function CredentialsStep({
  draft,
  missing,
  present = {},
  envPath,
  hasAdminApiKeyInEnv,
  wizardRequired = true,
  skipReason: _skipReason,
  setupReviewActive = false,
  saving,
  onChange,
  onContinue,
  onImportFromEnv,
  onBackToGenesis,
}: CredentialsStepProps) {
  const creds = draft.credentials;
  const [vaultTab, setVaultTab] = useState<VaultTab>("fabric");
  const [importing, setImporting] = useState(false);
  const [syncingKey, setSyncingKey] = useState(false);
  const [testingFabric, setTestingFabric] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(false);
  const [fabricReport, setFabricReport] = useState<FabricConnectionTestReport | null>(null);
  const [fabricCertified, setFabricCertified] = useState(false);
  const [ntInstalled, setNtInstalled] = useState<boolean | null>(null);
  const [ntChecking, setNtChecking] = useState(false);
  const [deployNote, setDeployNote] = useState<string | null>(null);
  const [emergencyFeed, setEmergencyFeed] = useState(false);

  const alreadyConfigured =
    !setupReviewActive &&
    (!wizardRequired || (missing.length === 0 && credentialsReadyInEnv(present)));

  const fabricGreen =
    fabricCertified || fabricReport?.overall === "green";

  const canContinue =
    fabricGreen &&
    (alreadyConfigured ||
      credentialsReadyInDraft(creds) ||
      credentialsReadyInEnv(present) ||
      setupReviewActive);

  const secState: ChipState = useMemo(() => {
    const jwt = Boolean(creds.LUMINA_JWT_SECRET_KEY.trim() || present.LUMINA_JWT_SECRET_KEY);
    const admin = Boolean(creds.LUMINA_ADMIN_API_KEY.trim() || present.LUMINA_ADMIN_API_KEY);
    if (jwt && admin) return "ok";
    if (jwt || admin) return "partial";
    return "idle";
  }, [creds, present]);

  const fabricState: ChipState = useMemo(() => {
    return Boolean(creds.LUMINA_FABRIC_TOKEN.trim() || present.LUMINA_FABRIC_TOKEN)
      ? "ok"
      : "idle";
  }, [creds, present]);

  const linkState: ChipState = useMemo(() => {
    if (fabricGreen) return "ok";
    if (!fabricReport) return "idle";
    if (fabricReport.overall === "amber") return "partial";
    return "fail";
  }, [fabricGreen, fabricReport]);

  const alertsState: ChipState = useMemo(() => {
    const bot = Boolean(creds.TELEGRAM_BOT_TOKEN.trim() || present.TELEGRAM_BOT_TOKEN);
    const chat = Boolean(creds.TELEGRAM_CHAT_ID.trim() || present.TELEGRAM_CHAT_ID);
    if (bot && chat) return "ok";
    if (bot || chat) return "partial";
    return "idle";
  }, [creds, present]);

  const dataState: ChipState = useMemo(() => {
    if (!emergencyFeed) return "idle";
    const t = Boolean(creds.CROSSTRADE_TOKEN.trim());
    const a = Boolean(creds.CROSSTRADE_ACCOUNT.trim());
    if (t && a) return "ok";
    if (t || a) return "partial";
    return "idle";
  }, [emergencyFeed, creds]);

  const stageCaption = fabricGreen
    ? "Link sealed · organism linked"
    : secState !== "idle" || fabricState !== "idle"
      ? "Channels awakening"
      : "Organism waiting · channels dark";

  const refreshNt = async () => {
    setNtChecking(true);
    try {
      const det = await detectNinjaTrader();
      setNtInstalled(det.installed);
      return det.installed;
    } catch {
      setNtInstalled(false);
      return false;
    } finally {
      setNtChecking(false);
    }
  };

  const runBootstrap = async () => {
    setBootstrapping(true);
    try {
      const result = await postFabricBootstrap();
      if (result.token_ready && !creds.LUMINA_FABRIC_TOKEN.trim()) {
        await onImportFromEnv();
      }
      if (result.deploy?.deployed) {
        setDeployNote(`AddOn deployed · ${result.deploy.copied.length} files`);
      } else if (result.deploy?.error) {
        setDeployNote(result.deploy.error);
      }
      if (result.fabric_link_green) setFabricCertified(true);
      if (result.halt) toast.error("Fabric halt active — re-run diagnostic");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Fabric bootstrap failed");
    } finally {
      setBootstrapping(false);
    }
  };

  useEffect(() => {
    void refreshNt();
    void runBootstrap();
    void postFabricNtWatch()
      .then((r) => {
        if (r.action === "halt") {
          toast.error("NinjaTrader update broke Fabric — re-run diagnostic");
          setFabricCertified(false);
        } else if (r.action === "certified") {
          setFabricCertified(true);
        }
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount once
  }, []);

  // If emergency turned off while on Data tab, bounce to Fabric.
  useEffect(() => {
    if (!emergencyFeed && vaultTab === "data") setVaultTab("fabric");
  }, [emergencyFeed, vaultTab]);

  const handleFabricTest = async () => {
    if (ntInstalled === false) {
      toast.error("Install NinjaTrader 8 first");
      setVaultTab("fabric");
      return;
    }
    setTestingFabric(true);
    setFabricReport(null);
    try {
      const report = await postFabricConnectionTest({
        include_safe_mode: true,
        instrument: "MES",
      });
      setFabricReport(report);
      setFabricCertified(Boolean(report.certified) || report.overall === "green");
      if (report.overall === "green") toast.success("Fabric link: GREEN — Genesis unlocked");
      else if (report.overall === "amber")
        toast.message("Fabric link: AMBER — not enough for Genesis");
      else toast.error("Fabric link: RED — fix issues before Genesis");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Fabric test failed";
      toast.error(message);
      setFabricCertified(false);
      setFabricReport({
        overall: "red",
        started_at: new Date().toISOString(),
        duration_ms: 0,
        target: "127.0.0.1:50051",
        gateway_mode: "sim",
        checks: [{ id: "client_error", title: "Diagnostics request", status: "fail", message }],
        summary: message,
        remediation: ["Backend :8000?", "Host on :50051?", "Token matches?"],
      });
    } finally {
      setTestingFabric(false);
    }
  };

  const handleImportAll = async () => {
    setImporting(true);
    try {
      const ok = await onImportFromEnv();
      if (ok) toast.success("Imported from .env");
      else toast.error("Import failed");
    } finally {
      setImporting(false);
    }
  };

  const handleSyncAdminKey = async () => {
    setSyncingKey(true);
    try {
      const ok = await onImportFromEnv();
      if (ok) toast.success("Synced from backend");
      else toast.error("Sync failed");
    } finally {
      setSyncingKey(false);
    }
  };

  const openNtInstall = () => {
    window.open(NINJATRADER_DOWNLOAD_URL, "_blank", "noopener,noreferrer");
  };

  const missingHints = useMemo(() => {
    if (alreadyConfigured) return [];
    return missing.filter((key) => {
      if (key.startsWith("CROSSTRADE")) return false;
      return !creds[key as keyof typeof creds]?.trim();
    });
  }, [missing, creds, alreadyConfigured]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35 }}
      className="credentials-vault-screen"
    >
      <div className="credentials-vault-grid">
        <aside className="credentials-vault-stage">
          <CredentialsVaultOrganism
            linked={fabricGreen}
            caption={stageCaption}
            className="my-auto"
          />
        </aside>

        <section
          className="credentials-vault-panel lumina-glass lumina-glass--overlay"
          aria-label="Operator vault"
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
              {/* Only after a successful vault seal (GREEN) — never on first-install linear path. */}
              {setupReviewActive && onBackToGenesis && fabricGreen ? (
                <button
                  type="button"
                  className="onboarding-btn-secondary rounded-md px-2.5 py-1 font-mono text-[0.55rem] tracking-wider uppercase"
                  onClick={() => onBackToGenesis()}
                  title="Return to Neural Genesis"
                >
                  Genesis
                </button>
              ) : null}
              <button
                type="button"
                className="onboarding-btn-secondary rounded-md px-2.5 py-1 font-mono text-[0.55rem] tracking-wider uppercase"
                disabled={importing}
                onClick={() => void handleImportAll()}
              >
                {importing ? "…" : "Import .env"}
              </button>
              {hasAdminApiKeyInEnv ? (
                <button
                  type="button"
                  className="onboarding-btn-secondary rounded-md px-2.5 py-1 font-mono text-[0.55rem] tracking-wider uppercase"
                  disabled={syncingKey}
                  onClick={() => void handleSyncAdminKey()}
                >
                  {syncingKey ? "…" : "Sync key"}
                </button>
              ) : null}
            </div>
          </div>

          {/* Status strip — clear activation feedback */}
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

          <div className="credentials-vault-panel__body">
            {ntInstalled === false ? (
              <div className="credentials-vault-nt-block mb-2 shrink-0">
                <p className="credentials-vault-nt-block__title">NinjaTrader 8 required</p>
                <p className="credentials-vault-nt-block__body">
                  Install NinjaTrader 8, then re-check. Lumina deploys the Fabric AddOn
                  automatically.
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
                    onClick={() => void refreshNt().then((ok) => ok && void runBootstrap())}
                  >
                    {ntChecking ? "Checking…" : "I installed it — re-check"}
                  </button>
                </div>
              </div>
            ) : null}

            {deployNote ? (
              <p className="mb-2 shrink-0 font-mono text-[0.55rem] tracking-wide text-cyan-200/50">
                {deployNote}
              </p>
            ) : null}

            {missingHints.length > 0 ? (
              <div className="credentials-vault-missing mb-2 shrink-0">
                {missingHints.map((key) => (
                  <span key={key} className="credentials-vault-missing-chip">
                    {key}
                  </span>
                ))}
              </div>
            ) : null}

            <Tabs
              value={vaultTab}
              onValueChange={(v) => setVaultTab(v as VaultTab)}
              className="credentials-vault-tabs"
            >
              <TabsList
                className={cn(
                  "credentials-vault-tab-list",
                  emergencyFeed
                    ? "credentials-vault-tab-list--4"
                    : "credentials-vault-tab-list--3",
                )}
                aria-label="Vault channels"
              >
                <TabsTrigger value="security">Security</TabsTrigger>
                <TabsTrigger value="fabric">Fabric</TabsTrigger>
                <TabsTrigger value="alerts">Alerts</TabsTrigger>
                {emergencyFeed ? <TabsTrigger value="data">Data</TabsTrigger> : null}
              </TabsList>

              <div className="credentials-vault-tab-body">
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
                      onClick={() => void handleFabricTest()}
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
                        if (on) setVaultTab("data");
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
              </div>
            </Tabs>
          </div>

          <div className="credentials-vault-cta-bar">
            <button
              type="button"
              className="onboarding-cta"
              disabled={!canContinue || saving || ntInstalled === false}
              onClick={onContinue}
              title={
                fabricGreen
                  ? "Seal vault and continue"
                  : "Run Fabric diagnostic until GREEN to unlock Genesis"
              }
            >
              {saving ? "Sealing…" : "Save & seal"}
            </button>
            {!fabricGreen ? (
              <p className="credentials-vault-seal-hint">
                Critical: Fabric diagnostic must be GREEN before Genesis
              </p>
            ) : (
              <p
                className="credentials-vault-seal-hint"
                style={{
                  color: "color-mix(in srgb, var(--lumina-cyan) 70%, white)",
                }}
              >
                Fabric GREEN · Genesis unlocked
              </p>
            )}
          </div>
        </section>
      </div>
    </motion.div>
  );
}
