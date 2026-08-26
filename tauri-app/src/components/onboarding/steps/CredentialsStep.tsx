import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { CredentialsVaultOrganism } from "@/components/onboarding/CredentialsVaultOrganism";
import { CredentialsVaultDetailPanel } from "@/components/onboarding/steps/CredentialsVaultDetailPanel";
import { CredentialsVaultMissionColumn } from "@/components/onboarding/steps/CredentialsVaultMissionColumn";
import {
  fetchFabricLinkStatus,
  postFabricNtWatch,
  type FabricConnectionTestReport,
  type FabricHealResult,
  type FabricLinkLevel,
} from "@/lib/setupClient";
import {
  credentialsReadyInDraft,
  credentialsReadyInEnv,
} from "@/lib/credentialsPrefill";
import { launchNinjaTrader } from "@/lib/ninjaTraderClient";
import type { OnboardingDraft } from "@/store/onboardingStore";
import { useOnboardingStore } from "@/store/onboardingStore";
import {
  openNinjaTraderInstall,
  refreshNinjaTraderInstalled,
  runFabricBootstrap,
  runFabricDiagnostic,
  runFabricRepair,
  runFabricSoftSetup,
} from "@/components/onboarding/steps/credentialsFabricActions";
import {
  alertsChipState,
  buildVaultFocusRows,
  dataChipState,
  defaultVaultFocus,
  diagnosticDisplayState,
  fabricTokenChipState,
  linkChipStateFromLive,
  linkSummaryLive,
  sealReadiness,
  securityChipState,
  twinChipState,
  vaultStageCaption,
  type VaultFocusId,
} from "@/components/onboarding/steps/credentialsVaultState";
import { fetchTwinReadiness, type TwinReadiness } from "@/lib/twinClient";

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
  missing: _missing,
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
  const [focus, setFocus] = useState<VaultFocusId>("fabric_token");
  const [importing, setImporting] = useState(false);
  const [syncingKey, setSyncingKey] = useState(false);
  const [testingFabric, setTestingFabric] = useState(false);
  const [repairingFabric, setRepairingFabric] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(false);
  const [fabricReport, setFabricReport] = useState<FabricConnectionTestReport | null>(null);
  const [healResult, setHealResult] = useState<FabricHealResult | null>(null);
  const [fabricCertified, setFabricCertified] = useState(false);
  /** Live SSOT from GET /api/setup/fabric-link-status (not paper cert). */
  const [liveLevel, setLiveLevel] = useState<FabricLinkLevel | null>(null);
  const [liveMeaning, setLiveMeaning] = useState<string | null>(null);
  const [hostReady, setHostReady] = useState(false);
  const [gateBirthOk, setGateBirthOk] = useState(false);
  const [ntInstalled, setNtInstalled] = useState<boolean | null>(null);
  const [ntChecking, setNtChecking] = useState(false);
  const [deployNote, setDeployNote] = useState<string | null>(null);
  const [focusSeeded, setFocusSeeded] = useState(false);
  const [twinReadiness, setTwinReadiness] = useState<TwinReadiness | null>(null);
  const fabricStartup = useOnboardingStore((s) => s.fabricStartup);
  const payloadTwin = useOnboardingStore((s) => s.payload?.twin);
  const updateDraft = useOnboardingStore((s) => s.updateDraft);
  // SSOT: draft.emergency_market_data_fallback ↔ YAML broker.fallback_on_fabric_failure
  const emergencyFeed = Boolean(draft.emergency_market_data_fallback);
  const setEmergencyFeed = (on: boolean) => {
    updateDraft({ emergency_market_data_fallback: on });
  };

  const alreadyConfigured =
    !setupReviewActive &&
    (!wizardRequired ||
      (_missing.length === 0 && credentialsReadyInEnv(present)));

  // Live GREEN only — never paper cert / last diagnostic alone (Vault color).
  const fabricLiveGreen = String(liveLevel || "").toUpperCase() === "GREEN";
  // Seal / Genesis: dual-plane proof required (ADR-0039/0040).
  // Live GREEN alone is NOT enough — historical_bars proof must exist.
  const fabricReadyForSeal =
    gateBirthOk ||
    (hostReady &&
      (fabricCertified || fabricReport?.overall === "green"));
  // Prefer live /api/twin/readiness; fall back to onboarding payload foundation field.
  const twinBirthReady = Boolean(
    twinReadiness?.birth_ready ||
      twinReadiness?.base_trained ||
      payloadTwin?.birth_ready ||
      payloadTwin?.base_trained,
  );
  const twinPct = Number(
    twinReadiness?.base_training_completion_pct ??
      payloadTwin?.base_training_completion_pct ??
      0,
  );
  const twinReadinessForWizard: TwinReadiness | null =
    twinReadiness ??
    (payloadTwin
      ? {
          birth_ready: Boolean(payloadTwin.birth_ready),
          base_trained: Boolean(payloadTwin.base_trained),
          base_training_completion_pct: Number(
            payloadTwin.base_training_completion_pct ?? 0,
          ),
          curriculum_version: payloadTwin.curriculum_version,
          local_only: true,
        }
      : null);

  const canContinue =
    fabricReadyForSeal &&
    twinBirthReady &&
    (alreadyConfigured ||
      credentialsReadyInDraft(creds) ||
      credentialsReadyInEnv(present) ||
      setupReviewActive);

  const secState = useMemo(() => securityChipState(creds, present), [creds, present]);
  const fabricState = useMemo(() => fabricTokenChipState(creds, present), [creds, present]);
  const linkState = useMemo(
    () => linkChipStateFromLive(liveLevel, hostReady, fabricReport),
    [liveLevel, hostReady, fabricReport],
  );
  const twinState = useMemo(
    () => twinChipState(twinBirthReady, twinPct),
    [twinBirthReady, twinPct],
  );
  const alertsState = useMemo(() => alertsChipState(creds, present), [creds, present]);
  const dataState = useMemo(
    () => dataChipState(emergencyFeed, creds),
    [emergencyFeed, creds],
  );
  const stageCaption = vaultStageCaption(
    Boolean(fabricReadyForSeal),
    secState,
    fabricState,
  );
  const diagState = useMemo(
    () =>
      diagnosticDisplayState(
        Boolean(fabricLiveGreen || fabricCertified || fabricReport?.overall === "green"),
        fabricReport,
      ),
    [fabricLiveGreen, fabricCertified, fabricReport],
  );
  const diagSummary = useMemo(
    () =>
      linkSummaryLive({
        liveLevel,
        meaning: liveMeaning,
        hostReady,
        proofCertified: fabricCertified || gateBirthOk,
        proofBadgeOk: fabricCertified,
        fabricReport,
      }),
    [
      liveLevel,
      liveMeaning,
      hostReady,
      fabricCertified,
      gateBirthOk,
      fabricReport,
    ],
  );

  const readiness = useMemo(
    () =>
      sealReadiness({
        fabricGreen: Boolean(fabricReadyForSeal),
        ntInstalled,
        secState,
        fabricState,
        canContinue,
        twinBirthReady,
      }),
    [
      fabricReadyForSeal,
      ntInstalled,
      secState,
      fabricState,
      canContinue,
      twinBirthReady,
    ],
  );

  const rows = useMemo(
    () =>
      buildVaultFocusRows({
        creds,
        present,
        emergencyFeed,
        twinBirthReady,
        twinCompletionPct: twinPct,
      }),
    [creds, present, emergencyFeed, twinBirthReady, twinPct],
  );

  const refreshTwinReadiness = async () => {
    try {
      setTwinReadiness(await fetchTwinReadiness());
    } catch {
      setTwinReadiness(null);
    }
  };

  const selectDiagnostic = () => setFocus("diagnostic");
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
      setVaultTabFabric: selectDiagnostic,
      setTestingFabric,
      setFabricReport,
      setFabricCertified,
    });
  const handleFabricRepair = () =>
    runFabricRepair({
      ntInstalled,
      setVaultTabFabric: selectDiagnostic,
      setRepairing: setRepairingFabric,
      setHealResult,
      setFabricReport,
      setFabricCertified,
      setDeployNote,
    });

  // Live SSOT poll — primary Vault color tracks host, not sticky cert.
  useEffect(() => {
    let cancelled = false;
    const applyLink = async () => {
      try {
        const link = await fetchFabricLinkStatus();
        if (cancelled) return;
        setLiveLevel(link.level || (link.green ? "GREEN" : "RED"));
        setLiveMeaning(link.meaning || link.reason || null);
        setHostReady(Boolean(link.host_ready || link.green));
        setGateBirthOk(Boolean(link.gate_birth_ok));
        const proofOk = Boolean(
          link.proof?.certified ||
            link.proof?.badge_ok ||
            (link.certificate && link.gate_birth_ok),
        );
        if (proofOk || link.green) {
          setFabricCertified(true);
        }
        // Host hard-down / no proof: clear sticky certified (backend may invalidate cert).
        if (
          String(link.level || "").toUpperCase() === "RED" &&
          !link.host_ready &&
          !link.green &&
          !link.proof?.certified &&
          !link.proof?.badge_ok
        ) {
          setFabricCertified(false);
        }
      } catch {
        /* offline — leave last known */
      }
    };
    void applyLink();
    const id = window.setInterval(() => {
      void applyLink();
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      // P0: NEVER auto taskkill NinjaTrader on mount. That caused continuous
      // NT login/restart loops (fabricCertified starts false every open).
      // Destructive close only via user Repair button (or session-guarded halt).
      const installed = await refreshNinjaTraderInstalled(setNtInstalled, setNtChecking);
      if (cancelled) return;

      // Systems Go probed Fabric — seed proof/host hints, still re-poll live SSOT.
      if (fabricStartup?.green || fabricStartup?.certified || fabricStartup?.hostReady) {
        if (fabricStartup.certified) setFabricCertified(true);
        if (fabricStartup.hostReady) setHostReady(true);
        if (fabricStartup.green) {
          setLiveLevel("GREEN");
          setGateBirthOk(true);
        } else if (fabricStartup.level) {
          setLiveLevel(fabricStartup.level);
        } else if (fabricStartup.hostReady) {
          setLiveLevel("AMBER");
        }
        setDeployNote(
          fabricStartup.reason
            ? `Cold start · ${fabricStartup.reason}`
            : "Cold start · verifying live Fabric…",
        );
        // Do not return — continue soft paths only if not already proven.
        if (fabricStartup.green || (fabricStartup.hostReady && fabricStartup.certified)) {
          // Still allow poll effect below; skip heavy bootstrap/repair.
          return;
        }
      }

      const boot = await runFabricBootstrap({
        creds,
        onImportFromEnv,
        setBootstrapping,
        setDeployNote,
        setFabricCertified,
      });
      if (cancelled) return;
      // Live green alone is not proof; only seed certified when gate/proof present.
      if (boot?.gate_birth_ok || boot?.proof?.certified || boot?.proof?.badge_ok) {
        setFabricCertified(true);
      }
      if (boot?.fabric_link_green || (boot?.host_ready && boot?.gate_birth_ok)) {
        return;
      }
      if (!installed) return;

      try {
        const watch = await postFabricNtWatch();
        if (cancelled) return;
        if (watch.action === "certified") {
          setFabricCertified(true);
          return;
        }
        if (watch.action === "halt") {
          // NEVER auto-kill NT on halt. User must click Repair (opt-in restart).
          setFabricCertified(false);
          setFocus("diagnostic");
          toast.error(
            "Fabric halt: NinjaTrader update broke the link. Click Repair only when ready (NT will restart).",
          );
          return;
        }
      } catch {
        /* ignore watch errors */
      }
      if (cancelled) return;

      // Non-destructive auto path only (no taskkill). Once per session.
      const softKey = "lumina.fabric.soft_setup_v1";
      let softDone = false;
      try {
        softDone = sessionStorage.getItem(softKey) === "1";
      } catch {
        softDone = false;
      }
      // If cold start already deferred (no link), skip soft setup spam.
      if (useOnboardingStore.getState().ntLinkDeferred) {
        setDeployNote("No NinjaTrader link this session — run Test when NT is ready");
        return;
      }

      if (!softDone) {
        try {
          sessionStorage.setItem(softKey, "1");
        } catch {
          /* ignore */
        }
        setFocus("diagnostic");
        await runFabricSoftSetup({
          ntInstalled: true,
          setVaultTabFabric: selectDiagnostic,
          setRepairing: setRepairingFabric,
          setHealResult,
          setFabricReport,
          setFabricCertified,
          setDeployNote,
        });
        return;
      }

      // Already soft-setup this session: probe only.
      setFocus("diagnostic");
      await runFabricDiagnostic({
        ntInstalled: true,
        setVaultTabFabric: selectDiagnostic,
        setTestingFabric: setTestingFabric,
        setFabricReport,
        setFabricCertified,
      });
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount once; never re-kill NT on re-render
  }, []);

  useEffect(() => {
    void refreshTwinReadiness();
    const id = window.setInterval(() => void refreshTwinReadiness(), 12_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (!focusSeeded && ntInstalled !== null) {
      setFocus(
        defaultVaultFocus({
          fabricGreen: Boolean(fabricReadyForSeal),
          ntInstalled,
          linkState,
          twinBirthReady,
        }),
      );
      setFocusSeeded(true);
    }
  }, [focusSeeded, ntInstalled, fabricReadyForSeal, linkState, twinBirthReady]);

  // After Fabric is seal-ready, once, steer operator to Twin if still incomplete.
  useEffect(() => {
    if (fabricReadyForSeal && !twinBirthReady && focusSeeded && focus !== "diagnostic") {
      setFocus("twin_base");
    }
    // Only when seal-ready flips true / twin becomes incomplete — not every focus change
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional one-way steer
  }, [fabricReadyForSeal, twinBirthReady, focusSeeded]);

  useEffect(() => {
    if (!emergencyFeed && (focus === "crosstrade_token" || focus === "crosstrade_account")) {
      setFocus("fabric_token");
    }
  }, [emergencyFeed, focus]);

  useEffect(() => {
    if (fabricReport || healResult?.steps?.length) {
      setFocus("diagnostic");
    }
  }, [fabricReport, healResult]);

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
            linked={Boolean(fabricReadyForSeal)}
            caption={stageCaption}
          />
        </aside>

        <CredentialsVaultMissionColumn
          envPath={envPath}
          bootstrapping={bootstrapping}
          setupReviewActive={setupReviewActive}
          fabricGreen={Boolean(fabricLiveGreen)}
          fabricReadyForSeal={Boolean(fabricReadyForSeal)}
          liveLevel={liveLevel}
          onBackToGenesis={onBackToGenesis}
          importing={importing}
          onImportAll={() => void handleImportAll()}
          hasAdminApiKeyInEnv={hasAdminApiKeyInEnv}
          syncingKey={syncingKey}
          onSyncAdminKey={() => void handleSyncAdminKey()}
          secState={secState}
          fabricState={fabricState}
          linkState={linkState}
          twinState={twinState}
          alertsState={alertsState}
          dataState={dataState}
          emergencyFeed={emergencyFeed}
          setEmergencyFeed={setEmergencyFeed}
          rows={rows}
          focus={focus}
          onFocus={setFocus}
          diagState={diagState}
          diagSummary={diagSummary}
          testingFabric={testingFabric}
          repairingFabric={repairingFabric}
          ntInstalled={ntInstalled}
          onTest={() => void handleFabricTest()}
          onRepair={() => void handleFabricRepair()}
          onLaunchNt={() => void launchNinjaTrader()}
          readiness={readiness}
          canContinue={canContinue}
          saving={saving}
          onContinue={onContinue}
        />

        <CredentialsVaultDetailPanel
          focus={ntInstalled === false ? "nt_install" : focus}
          creds={creds}
          present={present}
          onChange={onChange}
          fabricReport={fabricReport}
          fabricGreen={Boolean(fabricLiveGreen)}
          fabricReadyForSeal={Boolean(fabricReadyForSeal)}
          liveLevel={liveLevel}
          fabricCertified={fabricCertified}
          setFabricCertified={setFabricCertified}
          healResult={healResult}
          testingFabric={testingFabric}
          repairingFabric={repairingFabric}
          ntInstalled={ntInstalled}
          ntChecking={ntChecking}
          openNtInstall={openNinjaTraderInstall}
          onRecheckNt={() => void refreshNt().then((ok) => ok && void runBootstrap())}
          twinReadiness={twinReadinessForWizard}
          onTwinCompleted={() => void refreshTwinReadiness()}
        />
      </div>
      {deployNote ? (
        <p className="sr-only" role="status">
          {deployNote}
        </p>
      ) : null}
    </motion.div>
  );
}
