import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  GenesisMaturityLadder,
  type MaturationPhaseId,
} from "@/components/birth/GenesisMaturityLadder";
import { PhaseHubAdvanceSection } from "@/components/maturity/PhaseHubAdvanceSection";
import { PhaseHubDeck } from "@/components/maturity/PhaseHubDeck";
import { PhaseHubHonestyBoard } from "@/components/maturity/PhaseHubHonestyBoard";
import { PhaseHubWipeConfirm } from "@/components/maturity/PhaseHubWipeConfirm";
import {
  clearLivingHubPref,
  followPhaseStart,
  maybeOpenLivingCinematic,
} from "@/components/maturity/phaseHubStart";
import type { HubWipeKind } from "@/components/maturity/phaseHubFormat";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import {
  type AdvanceMode,
  type MaturityHubPayload,
  fetchMaturityHub,
  postAdvanceNextPhase,
  postApproveReal,
  postMaturityPreferences,
  postStartMaturityPhase,
  postWipeAllMaturation,
  postWipeMaturityPhase,
} from "@/lib/maturationClient";
import { fetchTwinReadiness, type TwinReadiness } from "@/lib/twinClient";
import { useOnboardingStore } from "@/store/onboardingStore";
import {
  distressPanelClass,
  warnOverlayBodyClass,
} from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

export function PhaseHubScreen() {
  const [hub, setHub] = useState<MaturityHubPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [telegramToken, setTelegramToken] = useState("");
  const [twinReady, setTwinReady] = useState<TwinReadiness | null>(null);
  const [wipeKind, setWipeKind] = useState<HubWipeKind | null>(null);
  const [wipeStep, setWipeStep] = useState<1 | 2>(1);
  const [wipeError, setWipeError] = useState<string | null>(null);
  const [wiping, setWiping] = useState(false);
  const enterOperatorDeck = useOnboardingStore((s) => s.enterOperatorDeck);
  const refreshOnboarding = useOnboardingStore((s) => s.refresh);

  const reload = useCallback(async () => {
    try {
      const payload = await fetchMaturityHub();
      setHub(payload);
      setError(null);
      try {
        setTwinReady(await fetchTwinReadiness());
      } catch {
        setTwinReady(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hub unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
    const id = window.setInterval(() => {
      void reload();
    }, 4000);
    return () => window.clearInterval(id);
  }, [reload]);

  const nextPhase = hub?.next_phase ?? null;
  const focus = (hub?.focus_phase || nextPhase || "birth") as MaturationPhaseId;
  const runnerActive = Boolean(hub?.runner_active);

  const onSetMode = async (mode: AdvanceMode) => {
    setBusy(true);
    try {
      await postMaturityPreferences(mode);
      toast.success(`Advance mode: ${mode}`);
      await reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save preference");
    } finally {
      setBusy(false);
    }
  };

  const onStartNext = async () => {
    if (!nextPhase) return;
    if (nextPhase === "real") {
      setBusy(true);
      try {
        await postApproveReal();
        toast.success("REAL approval recorded — switch mode carefully");
        await reload();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "REAL blocked");
      } finally {
        setBusy(false);
      }
      return;
    }
    if (nextPhase === "birth") {
      toast.info("Start Birth from the Birth screen");
      return;
    }
    setBusy(true);
    try {
      clearLivingHubPref(nextPhase);
      await postStartMaturityPhase(nextPhase);
      if (await maybeOpenLivingCinematic(nextPhase, refreshOnboarding)) {
        toast.success("Clock started");
        return;
      }
      const outcome = await followPhaseStart(async () => {
        const payload = await fetchMaturityHub();
        setHub(payload);
        return payload;
      }, nextPhase);
      if (outcome.ok) {
        toast.success(outcome.message);
      } else {
        toast.error(outcome.message);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Start failed");
    } finally {
      setBusy(false);
    }
  };

  const onAdvance = async () => {
    setBusy(true);
    try {
      await postAdvanceNextPhase({
        confirm: true,
        telegramToken: telegramToken.trim() || undefined,
      });
      toast.success("Next phase started");
      setTelegramToken("");
      await reload();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Advance failed");
    } finally {
      setBusy(false);
    }
  };

  const closeWipe = () => {
    setWipeKind(null);
    setWipeStep(1);
    setWipeError(null);
  };

  const onWipe = (kind: HubWipeKind) => {
    if (busy || runnerActive) {
      toast.info(runnerActive ? "Stop the running phase before wipe." : "Please wait…");
      return;
    }
    setWipeKind(kind);
    setWipeStep(1);
    setWipeError(null);
  };

  const runWipe = async () => {
    if (!wipeKind || wiping) return;
    const kind = wipeKind;
    setWiping(true);
    setWipeError(null);
    try {
      if (kind === "full") {
        await postWipeAllMaturation();
        toast.success("Full wipe complete — blank Genesis, setup kept");
      } else if (kind === "birth") {
        await postWipeMaturityPhase("birth");
        toast.success("Birth wiped — history kept. Restart from Genesis.");
      } else {
        await postWipeMaturityPhase(kind);
        toast.success(
          kind === "awakening"
            ? "Awakening data wiped — Birth plant kept"
            : `${kind} wiped`,
        );
      }
      setWipeKind(null);
      setWipeStep(1);
      await reload();
      await refreshOnboarding();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Wipe failed";
      setWipeError(message);
      toast.error(message);
    } finally {
      setWiping(false);
    }
  };

  const onOpenDeck = () => {
    enterOperatorDeck();
    toast.success("Command Deck — SIM exploration");
  };

  return (
    <OnboardingShell className="phase-hub-screen birth-phase-screen birth-phase-screen--cinematic onboarding-shell--form">
      <div className="birth-phase-cinematic relative mx-auto flex h-dvh min-h-0 w-full max-w-5xl flex-col overflow-hidden px-3 py-2">
        <LuminaPhaseHeader
          eyebrow="Organism continuum"
          title="Phase Hub"
          status={
            hub?.strict_mode === false
              ? "Lab soft-complete · checkpoint · evolve"
              : "Strict proofs · checkpoint · learned · evolve"
          }
          tone="violet"
          variant="strip"
        />

        <div className="mt-2 shrink-0">
          <GenesisMaturityLadder activePhase={focus} />
        </div>

        {hub?.soft_legacy_complete ? (
          <p
            className={cn(
              "mt-2 shrink-0 rounded-md border px-3 py-2 font-mono text-[10px]",
              distressPanelClass("warn"),
              warnOverlayBodyClass(),
            )}
          >
            Last phase was completed under legacy soft stamps. Wipe + re-run for strict evidence.
          </p>
        ) : null}

        {hub ? (
          <div className="mt-1.5">
            <PhaseHubHonestyBoard hub={hub} twinReady={twinReady} />
          </div>
        ) : null}

        {loading && !hub ? (
          <p className="mt-8 text-center font-mono text-sm text-muted-foreground">Loading hub…</p>
        ) : null}

        {error ? (
          <p className="mt-3 rounded-md border border-rose-500/40 bg-rose-950/30 px-3 py-2 font-mono text-xs text-rose-200">
            {error}
          </p>
        ) : null}

        <PhaseHubDeck
          hub={hub}
          busy={busy}
          runnerActive={runnerActive}
          onStartNext={() => void onStartNext()}
          onOpenDeck={onOpenDeck}
          onWipe={onWipe}
        >
          <PhaseHubAdvanceSection
            hub={hub}
            busy={busy}
            telegramToken={telegramToken}
            setTelegramToken={setTelegramToken}
            onSetMode={onSetMode}
            onAdvance={onAdvance}
            setBusy={setBusy}
            reload={reload}
          />
        </PhaseHubDeck>
      </div>
      <PhaseHubWipeConfirm
        kind={wipeKind}
        step={wipeStep}
        wiping={wiping}
        error={wipeError}
        onCancel={closeWipe}
        onContinue={() => setWipeStep(2)}
        onConfirm={() => void runWipe()}
      />
    </OnboardingShell>
  );
}
