import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { AwakeningMission } from "@/components/maturity/AwakeningMission";
import { PhaseHubWipeConfirm } from "@/components/maturity/PhaseHubWipeConfirm";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { EvolutionLadderStrip } from "@/components/shared/EvolutionLadderStrip";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import {
  fetchAwakeningProgress,
  fetchMaturityHub,
  postStartMaturityPhase,
  postStopMaturityPhase,
  postWipeMaturityPhase,
  type MaturityHubPayload,
} from "@/lib/maturationClient";
import type { AwakeningProgressView } from "@/lib/awakening/awakeningChecklist";
import { awakeningHeaderStatus } from "@/lib/awakening/awakeningFailCopy";
import { setPreferAwakeningHub } from "@/lib/awakening/awakeningSurfacePref";
import { useOnboardingStore } from "@/store/onboardingStore";

export function AwakeningPhaseScreen() {
  const [hub, setHub] = useState<MaturityHubPayload | null>(null);
  const [progress, setProgress] = useState<AwakeningProgressView | null>(null);
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
        fetchAwakeningProgress(),
      ]);
      setHub(hubPayload);
      setProgress(prog);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Awakening progress unavailable");
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

  const status = awakeningHeaderStatus({
    running,
    passNow,
    focusStatus: hub?.focus_status ?? null,
    error: hub?.error ?? null,
    progressMessage: hub?.progress_message ?? null,
  });

  const onStart = async () => {
    setBusy(true);
    try {
      setPreferAwakeningHub(false);
      await postStartMaturityPhase("awakening");
      toast.success("Awakening clock started");
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
      toast.success("Stop requested — current cycle finishes, then the clock halts");
      await reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Stop failed");
    } finally {
      setBusy(false);
    }
  };

  const onReturnHub = async () => {
    setPreferAwakeningHub(true);
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
      await postWipeMaturityPhase("awakening");
      setWipeOpen(false);
      toast.success("Awakening wiped — Birth kept");
      setPreferAwakeningHub(true);
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
          eyebrow="Awakening"
          title="Open eyes"
          status={status}
          tone={passNow ? "emerald" : running ? "cyan" : "amber"}
          variant="compact"
          className="lumina-phase-header relative z-20"
        />
        <EvolutionLadderStrip activePhase="awakening" className="relative z-20 evolution-ladder-strip--dense !py-1" />
        <AwakeningMission
          hub={hub}
          progress={progress}
          busy={busy}
          onStart={() => void onStart()}
          onStop={() => void onStop()}
          onReturnHub={() => void onReturnHub()}
          onWipe={onWipe}
        />
        <PhaseHubWipeConfirm
          kind={wipeOpen ? "awakening" : null}
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
