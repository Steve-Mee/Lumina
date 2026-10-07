import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { PlaygroundMission } from "@/components/maturity/PlaygroundMission";
import { PhaseHubWipeConfirm } from "@/components/maturity/PhaseHubWipeConfirm";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { EvolutionLadderStrip } from "@/components/shared/EvolutionLadderStrip";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import {
  fetchMaturityHub,
  fetchPlaygroundProgress,
  postStartMaturityPhase,
  postStopMaturityPhase,
  postWipeMaturityPhase,
  type MaturityHubPayload,
} from "@/lib/maturationClient";
import type { PlaygroundProgressView } from "@/lib/playground/playgroundChecklist";
import { playgroundHeaderStatus } from "@/lib/playground/playgroundFailCopy";
import { setPreferPlaygroundHub } from "@/lib/playground/playgroundSurfacePref";
import { useOnboardingStore } from "@/store/onboardingStore";

export function PlaygroundPhaseScreen() {
  const [hub, setHub] = useState<MaturityHubPayload | null>(null);
  const [progress, setProgress] = useState<PlaygroundProgressView | null>(null);
  const [busy, setBusy] = useState(false);
  const [wiping, setWiping] = useState(false);
  const [wipeOpen, setWipeOpen] = useState(false);
  const [wipeError, setWipeError] = useState<string | null>(null);
  const [pollNote, setPollNote] = useState<string | null>(null);
  const refreshOnboarding = useOnboardingStore((s) => s.refresh);
  const returnToPhaseHub = useOnboardingStore((s) => s.returnToPhaseHub);
  const enterOperatorDeck = useOnboardingStore((s) => s.enterOperatorDeck);

  const reload = useCallback(async () => {
    try {
      const [hubPayload, prog] = await Promise.all([
        fetchMaturityHub(),
        fetchPlaygroundProgress(),
      ]);
      setHub(hubPayload);
      setProgress(prog);
      setPollNote(null);
    } catch (err) {
      setPollNote(err instanceof Error ? err.message : "Playground progress unavailable");
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

  const learned = { ...(hub?.focus_learned ?? {}), ...(progress?.learned ?? {}) };
  const envelopeSealed = learned.envelope_sealed === true;
  const status =
    pollNote ??
    playgroundHeaderStatus({
      running,
      passNow,
      focusStatus: hub?.focus_status ?? null,
      error: hub?.error ?? null,
      progressMessage: hub?.progress_message ?? null,
      envelopeSealed,
    });

  const onStart = async () => {
    setBusy(true);
    try {
      setPreferPlaygroundHub(false);
      await postStartMaturityPhase("playground");
      toast.success("Playground clock started");
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
    setPreferPlaygroundHub(true);
    returnToPhaseHub();
    await refreshOnboarding();
  };

  const onOpenDeck = () => {
    setPreferPlaygroundHub(false);
    enterOperatorDeck();
  };

  const onWipe = () => {
    if (running) {
      toast.info("Stop the clock before wipe");
      return;
    }
    setWipeError(null);
    setWipeOpen(true);
  };

  const confirmWipe = async (phrase: string) => {
    setWiping(true);
    setWipeError(null);
    try {
      await postWipeMaturityPhase("playground", phrase);
      setWipeOpen(false);
      toast.success("Playground wiped — Awakening kept");
      setPreferPlaygroundHub(true);
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
          eyebrow="Playground"
          title="Eerste stappen"
          status={status}
          tone={pollNote ? "amber" : passNow ? "emerald" : running ? "cyan" : "amber"}
          variant={running ? "compact" : "strip"}
          className="lumina-phase-header relative z-20"
        />
        <EvolutionLadderStrip
          activePhase="playground"
          className={
            running
              ? "relative z-20 evolution-ladder-strip--dense !py-1"
              : "relative z-20"
          }
        />
        <PlaygroundMission
          hub={hub}
          progress={progress}
          busy={busy}
          onStart={() => void onStart()}
          onStop={() => void onStop()}
          onReturnHub={() => void onReturnHub()}
          onOpenDeck={onOpenDeck}
          onWipe={onWipe}
        />
        <PhaseHubWipeConfirm
          kind={wipeOpen ? "playground" : null}
          wiping={wiping}
          error={wipeError}
          onCancel={() => {
            setWipeOpen(false);
            setWipeError(null);
          }}
          onConfirm={(phrase) => void confirmWipe(phrase)}
        />
      </div>
    </OnboardingShell>
  );
}
