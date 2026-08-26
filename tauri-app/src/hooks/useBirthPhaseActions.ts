import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import type { BirthAdvancedSection } from "@/components/birth/BirthAdvancedPanel";
import { buildStalledRecoveryActions } from "@/hooks/birthPhaseRecoveryActions";
import { useBirthPhaseMonitor } from "@/hooks/useBirthPhaseMonitor";
import { useDeckTransition } from "@/hooks/useDeckTransition";
import {
  useBirthPhaseDerived,
  type BirthPhaseDerived,
} from "@/hooks/useBirthPhaseDerived";
import { resolveCertificateFailureSubtitle } from "@/lib/birthCertificateDiagnostics";
import { traceBirthWipe } from "@/lib/birthWipeTrace";
import {
  clearBirthForExtraTraining,
  startBirthSessionContinue,
  type BirthWipeResult,
} from "@/lib/birthClient";
import { useBirthStore } from "@/store/birthStore";
import { useBirthUiStore } from "@/store/birthUiStore";
import { useOnboardingStore } from "@/store/onboardingStore";

export function useBirthPhaseActions() {
  useBirthPhaseMonitor();

  const [recoveryDismissed, setRecoveryDismissed] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [controlBusy, setControlBusy] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState<BirthAdvancedSection | null>(null);
  const [realPreviewActive, setRealPreviewActive] = useState(false);
  const [milestoneVeilActive, setMilestoneVeilActive] = useState(false);
  const veiledMilestonesRef = useRef<Set<string>>(new Set());
  const { transition, startTransition, completeTransition } = useDeckTransition();

  const derived: BirthPhaseDerived = useBirthPhaseDerived(recoveryDismissed);

  const poll = useBirthStore((s) => s.poll);
  const retryBirth = useBirthStore((s) => s.retryBirth);
  const resumeBirth = useBirthStore((s) => s.resumeBirth);
  const reuseDataBirth = useBirthStore((s) => s.reuseDataBirth);
  const resumeStalledStage = useBirthStore((s) => s.resumeStalledStage);
  const expandAndRetryStalledStage = useBirthStore((s) => s.expandAndRetryStalledStage);
  const executeRecommendedRecovery = useBirthStore((s) => s.executeRecommendedRecovery);
  const returnToGenesis = useBirthStore((s) => s.returnToGenesis);
  const openWipeConfirm = useBirthUiStore((s) => s.openWipeConfirm);
  const activateBirth = useOnboardingStore((s) => s.activateBirth);
  const onboardingError = useOnboardingStore((s) => s.error);
  const updateDraft = useOnboardingStore((s) => s.updateDraft);
  const completeBirthTransition = useOnboardingStore((s) => s.completeBirthTransition);
  const enterSetupReview = useOnboardingStore((s) => s.enterSetupReview);

  const {
    genesisMode,
    engineLive,
    checkpointAvailable,
    activating,
    engineActive,
    running,
    failed,
    awakening,
    autonomousMode,
    certificateFailed,
    stageStalledActive,
    stalledRetryable,
    needsAttention,
    status,
    targetTrades,
    trainingDraft,
    evolutionExhausted,
    milestones,
  } = derived;

  useEffect(() => {
    if (engineActive || activating) {
      setRecoveryDismissed(false);
    }
  }, [engineActive, activating]);

  useEffect(() => {
    if (!running || failed || awakening) {
      return;
    }
    for (const milestone of milestones) {
      if (
        (milestone.id === "refinement" ||
          milestone.id === "awakening" ||
          milestone.id === "strategies") &&
        milestone.state === "complete" &&
        !veiledMilestonesRef.current.has(milestone.id)
      ) {
        veiledMilestonesRef.current.add(milestone.id);
        setMilestoneVeilActive(true);
        break;
      }
    }
  }, [milestones, running, failed, awakening]);

  useEffect(() => {
    if (!autonomousMode || !certificateFailed || retrying || activating || engineActive) {
      return;
    }
    setRetrying(true);
    void retryBirth()
      .then((ok) => {
        if (ok) {
          toast.info("Autonomous certificate remediation started");
        }
      })
      .finally(() => setRetrying(false));
  }, [autonomousMode, certificateFailed, retrying, activating, engineActive, retryBirth]);

  useEffect(() => {
    if (!autonomousMode || !stageStalledActive || retrying || activating || engineActive) {
      return;
    }
    const pending =
      status?.progress?.autonomous_recovery_pending === true ||
      (stalledRetryable && !needsAttention);
    if (!pending) {
      return;
    }
    setRetrying(true);
    void executeRecommendedRecovery()
      .then((ok) => {
        if (ok) {
          toast.info("Autonomous recovery dispatched");
        }
      })
      .finally(() => setRetrying(false));
  }, [
    autonomousMode,
    stageStalledActive,
    stalledRetryable,
    needsAttention,
    status?.progress?.autonomous_recovery_pending,
    retrying,
    activating,
    engineActive,
    executeRecommendedRecovery,
  ]);

  useEffect(() => {
    if (!autonomousMode || !awakening || activating) {
      return;
    }
    if (status?.artifacts_ok !== true) {
      return;
    }
    const timer = window.setTimeout(() => {
      setRealPreviewActive(true);
    }, 5000);
    return () => window.clearTimeout(timer);
  }, [autonomousMode, awakening, activating, status?.artifacts_ok]);

  const handleStopBirth = (): Promise<void> => {
    setControlBusy(true);
    setAdvancedOpen(null);
    return useBirthStore
      .getState()
      .stopBirthRun()
      .then((ok) => {
        if (ok) {
          toast.success("Stopped — choose Start birth or wipe for a clean run");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Stop failed");
      })
      .finally(() => setControlBusy(false));
  };

  const handleStartBirth = () => {
    const store = useBirthStore.getState();
    if (!store.sessionHydrated || store.sessionProbeState !== "ready") {
      toast.info(
        "Still loading previous birth session — wait until status is ready before activating.",
      );
      return;
    }
    setControlBusy(true);
    // beginBirthRun only after successful start (activateBirth owns that).
    void activateBirth()
      .then(async (ok) => {
        if (ok) {
          await poll();
          return;
        }
        // Keep recovery/error surface from activateBirth — do not force silent Genesis.
        const err =
          useOnboardingStore.getState().error ??
          onboardingError ??
          "Birth start failed";
        toast.error(err);
      })
      .finally(() => setControlBusy(false));
  };

  const handleWipeBirthData = async (): Promise<BirthWipeResult> => {
    traceBirthWipe("screen.wipe.start", {
      genesisMode,
      engineLive,
      controlBusy,
      activating,
      checkpointAvailable,
    });
    setControlBusy(true);
    try {
      const result = await useBirthStore.getState().wipeBirthData();
      traceBirthWipe("screen.wipe.done", { ok: result.ok, error: result.error });
      if (result.ok) {
        toast.success(result.message ?? "All birth data wiped — ready for a clean start.");
      } else if (result.error) {
        toast.error(result.error);
      }
      return result;
    } finally {
      setControlBusy(false);
      traceBirthWipe("screen.wipe.finally", { controlBusy: false });
    }
  };

  const handleResumeCheckpoint = () => {
    setControlBusy(true);
    // Sticky training shell immediately (Raptor cold-start) — no wipe/decision thrash.
    useBirthStore.getState().beginBirthRun();
    // Dedicated resume: continue_training + reuse_data + pause clear.
    // Champion freeze: backend accepts frozen champion then starts (explicit human path).
    void resumeBirth()
      .then((ok) => {
        if (ok) {
          toast.success("Resumed from checkpoint — training continues");
          return;
        }
        // resumeBirth clears run pin and returns to Genesis on failure.
        toast.error(useBirthStore.getState().pollError ?? "Resume failed");
      })
      .finally(() => setControlBusy(false));
  };

  const handleExtraTraining = () => {
    void clearBirthForExtraTraining()
      .then(() => startBirthSessionContinue(targetTrades))
      .then(() => {
        useBirthStore.setState({ uiPhase: "running", birthSurface: "running" });
        toast.success("Extra training started from checkpoint");
      })
      .catch((e) => toast.error(e instanceof Error ? e.message : "Extra training failed"));
  };

  const enterCommandDeck = () => {
    setRealPreviewActive(true);
  };

  const onRealPreviewComplete = () => {
    setRealPreviewActive(false);
    startTransition({
      kind: "birthEntry",
      targetMode: "SIM",
      scopeSelector: ".onboarding-shell",
    });
  };

  const completeDeckEntry = () => {
    completeTransition();
    toast.success("Welcome to the Neural Command Deck");
    completeBirthTransition();
    useBirthStore.getState().reset();
  };

  const handleResumeBirth = () => {
    setRetrying(true);
    // Sticky training shell immediately — no decision/wipe flash during resume cold-start.
    useBirthStore.getState().beginBirthRun();
    // Never use bare retry here — retry without preserve wiped checkpoint for paused runs.
    void resumeBirth()
      .then((ok) => {
        if (ok) {
          toast.success("Continuing birth from checkpoint");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Birth resume failed");
      })
      .finally(() => setRetrying(false));
  };

  const handleWipeRetryBirth = () => {
    setRetrying(true);
    void retryBirth({ wipe: true })
      .then((ok) => {
        if (ok) {
          toast.success("Fresh birth training started");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Birth restart failed");
      })
      .finally(() => setRetrying(false));
  };

  const handleReuseDataBirth = () => {
    setRetrying(true);
    void reuseDataBirth()
      .then((ok) => {
        if (ok) {
          toast.success("Resuming with reused data manifest");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Birth reuse failed");
      })
      .finally(() => setRetrying(false));
  };

  const handleResumeStalledStage = () => {
    setRetrying(true);
    void resumeStalledStage()
      .then((ok) => {
        if (ok) {
          toast.success("Resuming stalled curriculum stage");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Stage resume failed");
      })
      .finally(() => setRetrying(false));
  };

  const handleExpandAndRetryStalledStage = () => {
    setRetrying(true);
    void expandAndRetryStalledStage()
      .then((ok) => {
        if (ok) {
          toast.success("Expanding data and retrying stage");
          return;
        }
        toast.error(useBirthStore.getState().pollError ?? "Expand and retry failed");
      })
      .finally(() => setRetrying(false));
  };

  const handleCopyForensicsCommand = () => {
    void navigator.clipboard.writeText("python scripts/birth_stage_forensics.py");
    toast.success("Forensics command copied to clipboard");
  };

  const handleReviewGenesisSettings = () => {
    setRecoveryDismissed(true);
    returnToGenesis();
    setAdvancedOpen("settings");
    toast.info("Review genesis settings, save, then use Expand & retry.");
  };

  const stalledRecoveryActions = buildStalledRecoveryActions(evolutionExhausted, {
    openWipeConfirm,
    handleReviewGenesisSettings,
    handleCopyForensicsCommand,
    handleExpandAndRetryStalledStage,
    handleResumeStalledStage,
    setRecoveryDismissed,
  });

  const certificateFailureDetail = resolveCertificateFailureSubtitle(status);

  const onChangeTraining = (patch: Partial<typeof trainingDraft>) => {
    updateDraft({ training: { ...trainingDraft, ...patch } });
  };

  return {
    derived,
    retrying,
    controlBusy,
    advancedOpen,
    setAdvancedOpen,
    realPreviewActive,
    milestoneVeilActive,
    setMilestoneVeilActive,
    setRecoveryDismissed,
    transition,
    handleStopBirth,
    handleStartBirth,
    handleWipeBirthData,
    handleResumeCheckpoint,
    handleExtraTraining,
    enterCommandDeck,
    onRealPreviewComplete,
    completeDeckEntry,
    handleResumeBirth,
    handleWipeRetryBirth,
    handleReuseDataBirth,
    returnToGenesis,
    retryBirth,
    enterSetupReview,
    onChangeTraining,
    stalledRecoveryActions,
    certificateFailureDetail,
  };
}

export type BirthPhaseActions = ReturnType<typeof useBirthPhaseActions>;
