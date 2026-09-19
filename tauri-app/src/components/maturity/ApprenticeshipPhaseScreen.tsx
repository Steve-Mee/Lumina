import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { ApprenticeshipMission } from "@/components/maturity/ApprenticeshipMission";
import { PhaseHubWipeConfirm } from "@/components/maturity/PhaseHubWipeConfirm";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { EvolutionLadderStrip } from "@/components/shared/EvolutionLadderStrip";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import {
  fetchApprenticeshipProgress,
  fetchMaturityHub,
  postStartMaturityPhase,
  postStopMaturityPhase,
  postWipeMaturityPhase,
  type MaturityHubPayload,
} from "@/lib/maturationClient";
import type { ApprenticeshipProgressView } from "@/lib/apprenticeship/apprenticeshipChecklist";
import { apprenticeshipHeaderStatus } from "@/lib/apprenticeship/apprenticeshipFailCopy";
import { setPreferApprenticeshipHub } from "@/lib/apprenticeship/apprenticeshipSurfacePref";
import { useOnboardingStore } from "@/store/onboardingStore";

export function ApprenticeshipPhaseScreen() {
  const [hub, setHub] = useState<MaturityHubPayload | null>(null);
  const [progress, setProgress] = useState<ApprenticeshipProgressView | null>(null);
  const [busy, setBusy] = useState(false);
  const [wiping, setWiping] = useState(false);
  const [wipeStep, setWipeStep] = useState<1 | 2>(1);
  const [wipeOpen, setWipeOpen] = useState(false);
  const [wipeError, setWipeError] = useState<string | null>(null);
  const refreshOnboarding = useOnboardingStore((s) => s.refresh);
  const returnToPhaseHub = useOnboardingStore((s) => s.returnToPhaseHub);

  const reload = useCallback(async () => {
    try {
      const [hubPayload, prog] = await Promise.all([
        fetchMaturityHub(),
        fetchApprenticeshipProgress(),
      ]);
      setHub(hubPayload);
      setProgress(prog);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Apprenticeship progress unavailable");
    }
  }, []);

  const running = Boolean(hub?.runner_active || progress?.runner_active);

  useEffect(() => {
    void reload();
    const id = window.setInterval(() => {
      void reload();
    }, running ? 2000 : 4000);
    return () => window.clearInterval(id);
  }, [reload, running]);

  const passNow = Boolean(progress?.pass_now);

  useEffect(() => {
    if (!passNow || running) return;
    void refreshOnboarding();
  }, [passNow, running, refreshOnboarding]);

  const status = apprenticeshipHeaderStatus({
    running,
    passNow,
    focusStatus: hub?.focus_status ?? null,
    error: hub?.error ?? null,
    progressMessage: hub?.progress_message ?? null,
  });

  const onStart = async () => {
    setBusy(true);
    try {
      setPreferApprenticeshipHub(false);
      await postStartMaturityPhase("apprenticeship");
      toast.success("Apprenticeship clock started");
      await reload();
      await refreshOnboarding();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Start failed");
    } finally {
      setBusy(false);
    }
  };

  const onStop = async () => {
    setBusy(true);
    try {
      await postStopMaturityPhase();
      toast.success("Stop requested — clock finishes this poll, then halts");
      await reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Stop failed");
    } finally {
      setBusy(false);
    }
  };

  const onReturnHub = async () => {
    setPreferApprenticeshipHub(true);
    returnToPhaseHub();
    await refreshOnboarding();
  };

  const onWipe = () => {
    if (running) {
      toast.info("Stop the clock before wipe");
      return;
    }
    setWipeError(null);
    setWipeStep(1);
    setWipeOpen(true);
  };

  const confirmWipe = async () => {
    setWiping(true);
    setWipeError(null);
    try {
      await postWipeMaturityPhase("apprenticeship");
      setWipeOpen(false);
      toast.success("Apprenticeship wiped — Playground kept");
      setPreferApprenticeshipHub(true);
      await refreshOnboarding();
    } catch (err) {
      setWipeError(err instanceof Error ? err.message : "Wipe failed");
    } finally {
      setWiping(false);
    }
  };

  return (
    <OnboardingShell className="birth-phase-screen birth-phase-screen--cinematic onboarding-shell--form">
      <div className="birth-phase-cinematic relative mx-auto flex h-dvh min-h-0 w-full max-w-none flex-col overflow-hidden">
        <LuminaPhaseHeader
          eyebrow="Apprenticeship"
          title="Walk"
          status={status}
          tone={passNow ? "emerald" : running ? "cyan" : "amber"}
          variant="compact"
          className="lumina-phase-header relative z-20"
        />
        <EvolutionLadderStrip activePhase="apprenticeship" className="relative z-20 evolution-ladder-strip--dense !py-1" />
        <ApprenticeshipMission
          hub={hub}
          progress={progress}
          busy={busy}
          onStart={() => void onStart()}
          onStop={() => void onStop()}
          onReturnHub={() => void onReturnHub()}
          onWipe={onWipe}
        />
        <PhaseHubWipeConfirm
          kind={wipeOpen ? "apprenticeship" : null}
          step={wipeStep}
          wiping={wiping}
          error={wipeError}
          onCancel={() => {
            setWipeOpen(false);
            setWipeStep(1);
            setWipeError(null);
          }}
          onContinue={() => setWipeStep(2)}
          onConfirm={() => void confirmWipe()}
        />
      </div>
    </OnboardingShell>
  );
}
