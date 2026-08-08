import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { CredentialsVaultOrganism } from "@/components/onboarding/CredentialsVaultOrganism";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { postFabricNtWatch, type FabricConnectionTestReport } from "@/lib/setupClient";
import {
  credentialsReadyInDraft,
  credentialsReadyInEnv,
} from "@/lib/credentialsPrefill";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { cn } from "@/lib/utils";
import { type VaultTab } from "@/components/onboarding/steps/CredentialsVaultPrimitives";
import {
  CredentialsVaultNtBlock,
  CredentialsVaultStatusStrip,
} from "@/components/onboarding/steps/CredentialsVaultChrome";
import { CredentialsVaultTabPanels } from "@/components/onboarding/steps/CredentialsVaultTabPanels";
import {
  openNinjaTraderInstall,
  refreshNinjaTraderInstalled,
  runFabricBootstrap,
  runFabricDiagnostic,
} from "@/components/onboarding/steps/credentialsFabricActions";
import {
  alertsChipState,
  dataChipState,
  fabricTokenChipState,
  linkChipState,
  securityChipState,
  vaultStageCaption,
} from "@/components/onboarding/steps/credentialsVaultState";

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

  const secState = useMemo(() => securityChipState(creds, present), [creds, present]);
  const fabricState = useMemo(() => fabricTokenChipState(creds, present), [creds, present]);
  const linkState = useMemo(
    () => linkChipState(Boolean(fabricGreen), fabricReport),
    [fabricGreen, fabricReport],
  );
  const alertsState = useMemo(() => alertsChipState(creds, present), [creds, present]);
  const dataState = useMemo(
    () => dataChipState(emergencyFeed, creds),
    [emergencyFeed, creds],
  );
  const stageCaption = vaultStageCaption(Boolean(fabricGreen), secState, fabricState);

  const refreshNt = () => refreshNinjaTraderInstalled(setNtInstalled, setNtChecking);
  const runBootstrap = () =>
    runFabricBootstrap({
      creds,
      onImportFromEnv,
      setBootstrapping,
      setDeployNote,
      setFabricCertified,
    });
  const handleFabricTest = () =>
    runFabricDiagnostic({
      ntInstalled,
      setVaultTabFabric: () => setVaultTab("fabric"),
      setTestingFabric,
      setFabricReport,
      setFabricCertified,
    });
  const openNtInstall = openNinjaTraderInstall;

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

  useEffect(() => {
    if (!emergencyFeed && vaultTab === "data") setVaultTab("fabric");
  }, [emergencyFeed, vaultTab]);

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

          <CredentialsVaultStatusStrip
            secState={secState}
            fabricState={fabricState}
            linkState={linkState}
            alertsState={alertsState}
            dataState={dataState}
            emergencyFeed={emergencyFeed}
          />

          <div className="credentials-vault-panel__body">
            {ntInstalled === false ? (
              <CredentialsVaultNtBlock
                ntChecking={ntChecking}
                openNtInstall={openNtInstall}
                onRecheck={() => void refreshNt().then((ok) => ok && void runBootstrap())}
              />
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
                <CredentialsVaultTabPanels
                  creds={creds}
                  onChange={onChange}
                  fabricReport={fabricReport}
                  fabricGreen={Boolean(fabricGreen)}
                  fabricCertified={fabricCertified}
                  setFabricCertified={setFabricCertified}
                  testingFabric={testingFabric}
                  emergencyFeed={emergencyFeed}
                  setEmergencyFeed={setEmergencyFeed}
                  onSelectDataTab={() => setVaultTab("data")}
                  runFabricTest={handleFabricTest}
                  ntInstalled={ntInstalled}
                />
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
