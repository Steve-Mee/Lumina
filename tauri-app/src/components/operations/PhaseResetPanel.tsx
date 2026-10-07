import { useCallback, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";

import { RecoveryActionCard } from "@/components/birth/BirthGenesisDeckPrimitives";
import { PhaseHubWipeConfirm } from "@/components/maturity/PhaseHubWipeConfirm";
import { HUB_WIPE_CARDS, type HubWipeKind } from "@/components/maturity/phaseHubFormat";
import { isBirthEngineLive } from "@/lib/birthPhaseModel";
import {
  fetchMaturityHub,
  postWipeAllMaturation,
  postWipeMaturityPhase,
  type MaturityHubPayload,
} from "@/lib/maturationClient";
import { cn } from "@/lib/utils";
import { useBirthStore } from "@/store/birthStore";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";
import { useOnboardingStore } from "@/store/onboardingStore";

function wipeSuccessCopy(kind: HubWipeKind): string {
  if (kind === "full") return "Full wipe complete — blank Genesis, setup kept";
  if (kind === "birth") return "Birth wiped — history kept. Restart from Genesis.";
  if (kind === "awakening") return "Awakening data wiped — Birth plant kept";
  return `${kind} wiped`;
}

export function PhaseResetPanel() {
  const operatorMode = useCoreStore(selectCurrentMode);
  const birthLive = useBirthStore((s) => isBirthEngineLive(s.status));
  const refreshOnboarding = useOnboardingStore((s) => s.refresh);
  const [hub, setHub] = useState<MaturityHubPayload | null>(null);
  const [hubKnown, setHubKnown] = useState(false);
  const [wipeKind, setWipeKind] = useState<HubWipeKind | null>(null);
  const [wipeError, setWipeError] = useState<string | null>(null);
  const [wiping, setWiping] = useState(false);

  const reload = useCallback(async () => {
    try {
      setHub(await fetchMaturityHub());
      setHubKnown(true);
    } catch {
      // Keep last hub. Unknown runner status stays locked.
    }
  }, []);

  useEffect(() => {
    void reload();
    const id = window.setInterval(() => {
      void reload();
    }, 8000);
    return () => window.clearInterval(id);
  }, [reload]);

  const runnerActive = Boolean(hub?.runner_active);
  const realBlocked = operatorMode === "REAL";
  const hubUnknown = !hubKnown;
  const blocked = realBlocked || runnerActive || birthLive || hubUnknown;
  const completed = hubKnown
    ? (hub?.completed_phases ?? []).join(" · ") || "none"
    : "unknown";

  const blockerCopy = realBlocked
    ? "Phase reset is SIM-only. Switch to SIM first."
    : hubUnknown
      ? "Hub unreachable — wipe stays locked."
      : runnerActive || birthLive
        ? "Stop the running phase before wipe."
        : null;

  const onWipe = (kind: HubWipeKind) => {
    if (blocked || wiping) {
      toast.info(blockerCopy ?? "Please wait…");
      return;
    }
    setWipeKind(kind);
    setWipeError(null);
  };

  const runWipe = async (phrase: string) => {
    if (!wipeKind || wiping) return;
    const kind = wipeKind;
    setWiping(true);
    setWipeError(null);
    try {
      if (kind === "full") {
        await postWipeAllMaturation(phrase);
      } else {
        await postWipeMaturityPhase(kind, phrase);
      }
      if (kind === "birth" || kind === "full") {
        useOnboardingStore.setState({ operatorDeckActive: false });
      }
      toast.success(wipeSuccessCopy(kind));
      setWipeKind(null);
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

  return (
    <section className="phase-reset-panel space-y-1.5 rounded-lg border border-red-500/30 bg-red-950/15 p-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <p className="font-mono text-[10px] uppercase text-red-200/90">Named phase reset</p>
        <p className="font-mono text-[10px] text-white/50">Completed: {completed}</p>
      </div>
      <p className="text-[11px] leading-snug text-red-200/80">
        Unreliable exam: wipe Awakening (Birth stays). Unreliable plant: wipe Birth (tick cache
        stays). Unreliable ticks: Full wipe. Smart Setup never wipes.
      </p>
      {blockerCopy ? (
        <p className="rounded-md border border-amber-500/30 bg-amber-950/20 px-2 py-1 font-mono text-[10px] text-amber-100">
          {blockerCopy}
        </p>
      ) : null}
      <div className="genesis-recovery-action-grid genesis-recovery-action-grid--3">
        {HUB_WIPE_CARDS.map((card) => (
          <RecoveryActionCard
            key={card.kind}
            label={card.label}
            tip={card.tip}
            hint={card.hint}
            tone={card.tone}
          >
            <button
              type="button"
              className={cn(
                "genesis-recovery-action-card__btn",
                card.tone === "danger"
                  ? "genesis-recovery-action-card__btn--danger"
                  : "genesis-recovery-action-card__btn--warn",
                (blocked || wiping) && "cursor-not-allowed opacity-70",
              )}
              disabled={blocked || wiping}
              onClick={() => onWipe(card.kind)}
            >
              <Trash2 className="size-3.5 shrink-0" aria-hidden />
              <span>{card.label}</span>
            </button>
          </RecoveryActionCard>
        ))}
      </div>
      <PhaseHubWipeConfirm
        kind={wipeKind}
        wiping={wiping}
        error={wipeError}
        onCancel={() => {
          setWipeKind(null);
          setWipeError(null);
        }}
        onConfirm={(phrase) => void runWipe(phrase)}
      />
    </section>
  );
}
