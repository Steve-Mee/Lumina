import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  GenesisMaturityLadder,
  type MaturationPhaseId,
} from "@/components/birth/GenesisMaturityLadder";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { LuminaPhaseHeader } from "@/components/shared/LuminaPhaseHeader";
import { Button } from "@/components/ui/button";
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
import { formatLearned } from "@/components/maturity/phaseHubFormat";
import { PhaseHubHonestyBoard } from "@/components/maturity/PhaseHubHonestyBoard";
import { PhaseHubAdvanceSection } from "@/components/maturity/PhaseHubAdvanceSection";
import {
  distressPanelClass,
  warnOverlayBodyClass,
  warnOverlayTitleClass,
} from "@/lib/modePresentation";
import { cn } from "@/lib/utils";

export function PhaseHubScreen() {
  const [hub, setHub] = useState<MaturityHubPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [telegramToken, setTelegramToken] = useState("");
  const [twinReady, setTwinReady] = useState<TwinReadiness | null>(null);
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
  const activePhase = hub?.active_phase ?? null;
  const focus = (hub?.focus_phase || nextPhase || "birth") as MaturationPhaseId;
  const learnedLines = formatLearned(hub?.learned);
  const nextSpec = nextPhase ? hub?.phase_specs?.[nextPhase] : null;
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
      await postStartMaturityPhase(nextPhase);
      toast.success(`Started phase: ${nextPhase}`);
      await reload();
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

  const onWipePhase = async (phase: string) => {
    if (!window.confirm(`Wipe phase "${phase}" and re-run it? This cannot be undone.`)) {
      return;
    }
    setBusy(true);
    try {
      await postWipeMaturityPhase(phase);
      toast.success(`Wiped phase ${phase}`);
      await reload();
      await refreshOnboarding();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Wipe failed");
    } finally {
      setBusy(false);
    }
  };

  const onWipeAll = async () => {
    if (
      !window.confirm(
        "Wipe ALL maturation progress (birth + later phases)? You will restart from Genesis.",
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      await postWipeAllMaturation();
      toast.success("Full maturation wipe complete");
      await reload();
      await refreshOnboarding();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Wipe-all failed");
    } finally {
      setBusy(false);
    }
  };

  const onOpenDeck = () => {
    enterOperatorDeck();
    toast.success("Command Deck — SIM exploration");
  };

  return (
    <OnboardingShell className="phase-hub-screen onboarding-shell--form">
      <div className="relative z-20 mx-auto flex h-dvh min-h-0 w-full max-w-5xl flex-col overflow-hidden px-4 py-3">
        <LuminaPhaseHeader
          eyebrow="Organism continuum"
          title="Phase Hub"
          status={
            hub?.strict_mode === false
              ? "Lab soft-complete enabled · checkpoint · evolve"
              : "Strict proofs · checkpoint · learned · evolve"
          }
          tone="violet"
          variant="strip"
        />

        <div className="mt-3 shrink-0">
          <GenesisMaturityLadder activePhase={focus} />
        </div>

        {hub?.soft_legacy_complete ? (
          <p
            className={cn(
              "mt-2 rounded-md border px-3 py-2 font-mono text-[10px]",
              distressPanelClass("warn"),
              warnOverlayBodyClass(),
            )}
          >
            Last phase was completed under legacy soft stamps. Wipe + re-run for strict evidence.
          </p>
        ) : null}

        {twinReady && !twinReady.birth_ready ? (
          <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-cyan-500/30 bg-cyan-950/20 px-3 py-2">
            <p className="flex-1 font-mono text-[10px] text-cyan-100/90">
              Twin base training incomplete ({Number(twinReady.base_training_completion_pct ?? 0).toFixed(0)}%).
              Birth sole-auto stays fail-closed until ready.
            </p>
            <Button type="button" size="sm" variant="secondary" onClick={onOpenDeck}>
              Train Twin Agent
            </Button>
          </div>
        ) : twinReady?.birth_ready ? (
          <p className="mt-2 font-mono text-[10px] text-emerald-200/80">
            Twin Birth-ready · base trained
          </p>
        ) : null}

        {hub ? <PhaseHubHonestyBoard hub={hub} /> : null}

        {loading && !hub ? (
          <p className="mt-8 text-center font-mono text-sm text-muted-foreground">Loading hub…</p>
        ) : null}

        {error ? (
          <p className="mt-4 rounded-md border border-rose-500/40 bg-rose-950/30 px-3 py-2 font-mono text-xs text-rose-200">
            {error}
          </p>
        ) : null}

        <div className="mt-4 grid min-h-0 flex-1 gap-4 overflow-y-auto pb-6 md:grid-cols-2">
          {/* Learned */}
          <section className="rounded-xl border border-border/50 bg-muted/10 p-4">
            <h2 className="font-mono text-[10px] tracking-[0.16em] text-emerald-200/90 uppercase">
              What was learned
            </h2>
            <p className="mt-1 font-mono text-[11px] text-muted-foreground">
              Last completed:{" "}
              <span className="text-cyan-200/90">{hub?.last_completed ?? "—"}</span>
            </p>
            {learnedLines.length > 0 ? (
              <ul className="mt-3 space-y-1.5 font-mono text-[11px] text-zinc-200/90">
                {learnedLines.map((line) => (
                  <li key={line} className="border-l border-emerald-500/30 pl-2">
                    {line}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 font-mono text-[11px] text-muted-foreground">
                No learned snapshot yet — complete Birth or the next phase.
              </p>
            )}
            {hub?.last_result ? (
              <pre className="mt-3 max-h-28 overflow-auto rounded bg-black/40 p-2 font-mono text-[9px] text-zinc-400">
                {JSON.stringify(hub.last_result, null, 2)}
              </pre>
            ) : null}
          </section>

          {/* Next steps */}
          <section className="rounded-xl border border-border/50 bg-muted/10 p-4">
            <h2 className="font-mono text-[10px] tracking-[0.16em] text-violet-200/90 uppercase">
              Next steps
            </h2>
            {activePhase || runnerActive ? (
              <div className="mt-2 space-y-1">
                <p className="font-mono text-sm text-amber-200/90">
                  Running: {activePhase ?? "phase runner"}…
                </p>
                {hub?.progress_message ? (
                  <p className="font-mono text-[10px] text-muted-foreground">{hub.progress_message}</p>
                ) : null}
                {typeof hub?.progress_pct === "number" ? (
                  <div className="h-1.5 overflow-hidden rounded bg-black/40">
                    <div
                      className="h-full bg-cyan-400/80 transition-all"
                      style={{ width: `${Math.max(0, Math.min(100, hub.progress_pct))}%` }}
                    />
                  </div>
                ) : null}
              </div>
            ) : null}
            {hub?.focus_status === "failed" || hub?.focus_status === "incomplete" ? (
              <p className="mt-2 font-mono text-[11px] text-rose-200/90">
                Phase incomplete — fix blockers below and Retry / Start again.
              </p>
            ) : null}
            {nextSpec ? (
              <>
                <p className="mt-2 text-lg font-medium text-foreground">{nextSpec.label}</p>
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                  {nextSpec.human_goal}
                </p>
              </>
            ) : (
              <p className="mt-2 font-mono text-sm text-emerald-200/90">
                Continuum complete — REAL path is human-gated.
              </p>
            )}
            {hub?.exit_eval && !hub.exit_eval.ok && hub.exit_eval.missing?.length ? (
              <div className={cn("mt-2 rounded border p-2", distressPanelClass("warn"))}>
                <p className={cn("font-mono text-[9px] uppercase tracking-wider", warnOverlayTitleClass())}>
                  Missing proofs
                </p>
                <ul className={cn("mt-1 space-y-0.5 font-mono text-[10px]", warnOverlayBodyClass())}>
                  {hub.exit_eval.missing.map((m) => (
                    <li key={m}>· {m}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {typeof hub?.last_result?.next_step === "string" ? (
              <p className="mt-2 font-mono text-[10px] text-cyan-200/85">
                Next: {String(hub.last_result.next_step)}
              </p>
            ) : null}

            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                disabled={busy || runnerActive || !nextPhase}
                onClick={() => void onStartNext()}
              >
                {nextPhase === "real" ? "Approve REAL (human)" : "Start next phase"}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={busy || runnerActive || !hub?.can_start_next}
                onClick={() => void onAdvance()}
              >
                Advance
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={onOpenDeck}>
                Open Command Deck
              </Button>
            </div>
          </section>

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

          {/* Checkpoints / wipe */}
          <section className="rounded-xl border border-rose-500/20 bg-rose-950/10 p-4 md:col-span-2">
            <h2 className="font-mono text-[10px] tracking-[0.16em] text-rose-200/80 uppercase">
              Checkpoints & wipe
            </h2>
            <p className="mt-1 font-mono text-[10px] text-muted-foreground">
              Progress is saved after each phase. Restart resumes here — you never re-run Birth
              unless you wipe.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(hub?.completed_phases ?? [])
                .filter((p) => p !== "genesis")
                .map((phase) => (
                  <Button
                    key={phase}
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => void onWipePhase(phase)}
                  >
                    Wipe {phase}
                  </Button>
                ))}
              <Button
                type="button"
                size="sm"
                variant="destructive"
                disabled={busy}
                onClick={() => void onWipeAll()}
              >
                Wipe all progress
              </Button>
              <Button type="button" size="sm" variant="ghost" disabled={busy} onClick={() => void reload()}>
                Refresh hub
              </Button>
            </div>
          </section>
        </div>
      </div>
    </OnboardingShell>
  );
}
