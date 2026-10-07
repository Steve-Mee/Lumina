import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { CharterTile } from "@/components/birth/BirthGenesisDeckPrimitives";
import { BirthLaunchButton } from "@/components/birth/BirthLaunchButton";
import { BirthStagePassChecklistCard } from "@/components/birth/BirthStagePassChecklistCard";
import { PhaseHubWipeConfirm } from "@/components/maturity/PhaseHubWipeConfirm";
import { playgroundTilesFromLearned } from "@/components/maturity/phaseHubPlayground";
import { PlaygroundSenseBrief } from "@/components/maturity/PlaygroundSenseBrief";
import { EvolutionLadderStrip } from "@/components/shared/EvolutionLadderStrip";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import {
  fetchMaturityHub,
  fetchPlaygroundProgress,
  postPlaygroundDeckLive,
  postStartMaturityPhase,
  postStopMaturityPhase,
  postWipeMaturityPhase,
  type MaturityHubPayload,
} from "@/lib/maturationClient";
import {
  buildPlaygroundChecklist,
  type PlaygroundProgressView,
} from "@/lib/playground/playgroundChecklist";
import { playgroundClockButtonLabel } from "@/lib/playground/playgroundFailCopy";
import { setPreferPlaygroundHub } from "@/lib/playground/playgroundSurfacePref";
import { useOnboardingStore } from "@/store/onboardingStore";
import { cn } from "@/lib/utils";

export function PlaygroundDeckOverlay() {
  const [hub, setHub] = useState<MaturityHubPayload | null>(null);
  const [progress, setProgress] = useState<PlaygroundProgressView | null>(null);
  const [busy, setBusy] = useState(false);
  const [wiping, setWiping] = useState(false);
  const [wipeOpen, setWipeOpen] = useState(false);
  const [wipeError, setWipeError] = useState<string | null>(null);
  const [pollNote, setPollNote] = useState<string | null>(null);
  const refreshOnboarding = useOnboardingStore((s) => s.refresh);
  const returnToPhaseHub = useOnboardingStore((s) => s.returnToPhaseHub);

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
      // One status line. A toast on every 2s poll covered the deck.
      setPollNote(err instanceof Error ? err.message : "Playground progress unavailable");
    }
  }, []);

  useEffect(() => {
    void postPlaygroundDeckLive().then((prog) => setProgress(prog)).catch(() => undefined);
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
  const tiles = playgroundTilesFromLearned(learned);
  const checklist = buildPlaygroundChecklist(progress);
  const status = pollNote
    ? pollNote
    : running
      ? hub?.progress_message || "Leerschool · wacht op de klokzin"
      : passNow
        ? "AND passed — return to Phase Hub"
        : "Incomplete — floors stay fail-closed";

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
      toast.success("Stop requested — clock halts after this heartbeat");
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

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 z-30 flex max-h-[46vh] flex-col overflow-hidden">
      <div className="pointer-events-auto mx-auto flex min-h-0 w-full max-w-6xl flex-col px-3 pt-2">
        <div className="lumina-glass lumina-glass--overlay flex min-h-0 max-h-[44vh] flex-col overflow-hidden rounded-md">
          <LuminaPhaseHeader
            eyebrow="Playground"
            title="Eerste stappen"
            status={status}
            tone={pollNote ? "amber" : passNow ? "emerald" : running ? "cyan" : "amber"}
            variant="compact"
          />
          <EvolutionLadderStrip activePhase="playground" className="evolution-ladder-strip--dense shrink-0 !py-1" />
          <div className="min-h-0 flex-1 overflow-auto px-2">
            <PlaygroundSenseBrief sense={progress?.sense} running={running} />
            <div className="genesis-charter-tile-grid phase-hub-kpi-grid px-0 py-1">
              {tiles.map((tile) => (
                <CharterTile key={tile.label} label={tile.label} value={tile.value} tip={tile.tip} footnote={tile.footnote} />
              ))}
            </div>
            <BirthStagePassChecklistCard checklist={checklist} goalLabel="AND gates" showMode={false} />
          </div>
          <div className="phase-hub-cta__row shrink-0 px-2 pb-2">
            <BirthLaunchButton
              activating={busy && !running}
              disabled={busy || running}
              activeLabel="OPENING PLAYGROUND CLOCK…"
              idleLabel={playgroundClockButtonLabel({
                running,
                passNow,
                progressMessage: hub?.progress_message,
              })}
              onClick={() => void onStart()}
              className="phase-hub-cta__primary"
            />
            {running ? (
              <button type="button" className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle phase-hub-cta__deck" disabled={busy} onClick={() => void onStop()}>
                Stop
              </button>
            ) : (
              <button type="button" className="genesis-recovery-action-card__btn genesis-recovery-action-card__btn--idle phase-hub-cta__deck" disabled={busy} onClick={() => void onReturnHub()}>
                Phase Hub
              </button>
            )}
          </div>
          <button
            type="button"
            className={cn("mb-2 shrink-0 font-mono text-[10px] text-rose-200/70", busy && "opacity-50")}
            disabled={busy || running}
            onClick={() => {
              setWipeError(null);
              setWipeOpen(true);
            }}
          >
            Wipe Playground
          </button>
        </div>
      </div>
      <PhaseHubWipeConfirm
        kind={wipeOpen ? "playground" : null}
        wiping={wiping}
        error={wipeError}
        onCancel={() => {
          setWipeOpen(false);
          setWipeError(null);
        }}
        onConfirm={(phrase) => {
          void (async () => {
            setWiping(true);
            try {
              await postWipeMaturityPhase("playground", phrase);
              setWipeOpen(false);
              setPreferPlaygroundHub(true);
              await refreshOnboarding();
            } catch (err) {
              setWipeError(err instanceof Error ? err.message : "Wipe failed");
            } finally {
              setWiping(false);
            }
          })();
        }}
      />
    </div>
  );
}
