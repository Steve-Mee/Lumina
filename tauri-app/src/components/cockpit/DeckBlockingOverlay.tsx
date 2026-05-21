import { useEffect, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, Sparkles, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import { resetCommandDeckTour } from "@/components/cockpit/CommandDeckTour";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { useBackendHealthSnapshot } from "@/hooks/useBackendHealth";
import { transitionOrNone } from "@/lib/motionPresets";
import {
  birthOverlayPanelClass,
  birthOverlayProgressClass,
  birthOverlayTitleClass,
  deckOverlayScrimClass,
  warnOverlayBodyClass,
  warnOverlayIconClass,
  warnOverlayPanelClass,
  warnOverlayTitleClass,
  welcomeOverlayBodyClass,
  welcomeOverlayDismissClass,
  welcomeOverlayIconClass,
  welcomeOverlayPanelClass,
  welcomeOverlayStrongClass,
  welcomeOverlayTitleClass,
} from "@/lib/modePresentation";
import { refreshBackendHealth } from "@/lib/backendHealthStore";
import { fetchBirthStatus } from "@/lib/setupClient";
import { resolveDeckStatus } from "@/lib/deckStatusOrchestrator";
import { selectCurrentMode, selectFallbackMode, useCoreStore } from "@/store/coreStore";
import { cn } from "@/lib/utils";
import { useOnboardingStore } from "@/store/onboardingStore";

import { DISMISS_KEY, WELCOME_FLAG } from "@/lib/deckStatusConstants";

interface BirthProgress {
  status: string;
  message?: string;
  progress?: {
    progress_pct?: number;
    trades_done?: number;
    target_trades?: number;
    stage?: string;
  };
}

function OverlayShell({
  children,
  role = "alertdialog",
  ariaLabelledBy,
  ariaDescribedBy,
}: {
  children: ReactNode;
  role?: "alert" | "alertdialog" | "status";
  ariaLabelledBy?: string;
  ariaDescribedBy?: string;
}) {
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();

  return (
    <motion.div
      role={role}
      aria-modal={role === "alertdialog" ? true : undefined}
      aria-labelledby={ariaLabelledBy}
      aria-describedby={ariaDescribedBy}
      initial={reducedMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={reducedMotion ? undefined : { opacity: 0 }}
      transition={transitionOrNone(reducedMotion, modeMotion)}
      className={cn("deck-blocking-overlay", deckOverlayScrimClass("blocking"))}
    >
      {children}
    </motion.div>
  );
}

function BackendDownPanel({ onRetry }: { onRetry: () => void }) {
  return (
    <OverlayShell role="alert" ariaLabelledBy="deck-backend-title">
      <div className={cn("w-full max-w-lg rounded-xl p-6", warnOverlayPanelClass())}>
        <div className="flex items-start gap-4">
          <AlertTriangle className={cn("mt-0.5 size-8 shrink-0", warnOverlayIconClass())} aria-hidden />
          <div className="min-w-0">
            <h2 id="deck-backend-title" className={warnOverlayTitleClass()}>
              Backend Unreachable
            </h2>
            <p className={cn("mt-3", warnOverlayBodyClass())}>
              FastAPI backend unreachable on port 8000. Start{" "}
              <span className="font-mono">lumina_os/run_backend.ps1</span> before operating the
              deck.
            </p>
          </div>
        </div>
        <div className="mt-6 flex justify-end">
          <Button type="button" variant="command-primary" onClick={onRetry}>
            Retry
          </Button>
        </div>
      </div>
    </OverlayShell>
  );
}

function BirthProgressPanel({
  birth,
  onViewProgress,
}: {
  birth: BirthProgress;
  onViewProgress: () => void;
}) {
  const pct = birth.progress?.progress_pct ?? 0;
  const stage = birth.progress?.stage ?? birth.status;

  return (
    <OverlayShell role="alertdialog" ariaLabelledBy="deck-birth-title">
      <div className={birthOverlayPanelClass()}>
        <h2 id="deck-birth-title" className={birthOverlayTitleClass()}>
          Birth Phase — {stage}
        </h2>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
          <div
            className={birthOverlayProgressClass()}
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
        <div className="mt-2 flex items-center justify-between gap-2 text-xs">
          <span className="text-muted-foreground">{pct.toFixed(0)}% complete</span>
          {birth.message ? (
            <span className="truncate text-[10px] text-muted-foreground">{birth.message}</span>
          ) : null}
        </div>
        <div className="mt-6 flex justify-end">
          <Button type="button" variant="command-primary" onClick={onViewProgress}>
            View birth progress
          </Button>
        </div>
      </div>
    </OverlayShell>
  );
}

function FallbackPanel({
  lastError,
  onDismiss,
}: {
  lastError: string | null;
  onDismiss: () => void;
}) {
  return (
    <OverlayShell role="alert" ariaLabelledBy="deck-fallback-title">
      <div className={cn("relative w-full max-w-lg rounded-xl p-6", warnOverlayPanelClass())}>
        <button
          type="button"
          className="absolute right-3 top-3 rounded p-1 text-[var(--status-warn-fg)]/80 hover:bg-[var(--status-warn-bg)]"
          aria-label="Dismiss fallback warning"
          onClick={onDismiss}
        >
          <X className="size-3.5" />
        </button>
        <div className="flex items-start gap-4 pr-6">
          <AlertTriangle className={cn("mt-0.5 size-8 shrink-0", warnOverlayIconClass())} aria-hidden />
          <div className="min-w-0">
            <h2 id="deck-fallback-title" className={warnOverlayTitleClass()}>
              Telemetry Degraded
            </h2>
            <p className={cn("mt-3", warnOverlayBodyClass())}>
              Live telemetry degraded — polling fallback active (WebSocket unavailable).
              Reconnecting…
            </p>
            {lastError ? (
              <p className="mt-2 truncate font-mono text-[10px] text-[var(--status-warn-fg)]/70">{lastError}</p>
            ) : null}
          </div>
        </div>
        <div className="mt-6 flex justify-end">
          <Button type="button" variant="command-ghost" onClick={onDismiss}>
            Continue on polling
          </Button>
        </div>
      </div>
    </OverlayShell>
  );
}

function WelcomePanel({ onDismiss }: { onDismiss: () => void }) {
  const operatorMode = useCoreStore(selectCurrentMode);

  return (
    <OverlayShell role="status" ariaLabelledBy="deck-welcome-title">
      <div className={welcomeOverlayPanelClass(operatorMode)}>
        <button
          type="button"
          className={cn("absolute right-3 top-3", welcomeOverlayDismissClass(operatorMode))}
          aria-label="Dismiss welcome"
          onClick={onDismiss}
        >
          <X className="size-3.5" />
        </button>
        <div className="flex items-start gap-4 pr-6">
          <Sparkles className={cn("mt-0.5 size-8 shrink-0", welcomeOverlayIconClass(operatorMode))} aria-hidden />
          <div className="min-w-0">
            <h2 id="deck-welcome-title" className={welcomeOverlayTitleClass(operatorMode)}>
              Welcome to the Command Deck
            </h2>
            <p className={cn("mt-3", welcomeOverlayBodyClass(operatorMode))}>
              Birth complete — use{" "}
              <strong className={welcomeOverlayStrongClass(operatorMode)}>Start Engine</strong> in
              the command bar when you are ready. New here? Take the guided tour.
            </p>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button type="button" variant="command-ghost" onClick={onDismiss}>
            Dismiss
          </Button>
          <Button
            type="button"
            variant="command-primary"
            onClick={() => {
              resetCommandDeckTour();
              onDismiss();
            }}
          >
            Start tour
          </Button>
        </div>
      </div>
    </OverlayShell>
  );
}

export function DeckBlockingOverlay() {
  const fallbackMode = useCoreStore(selectFallbackMode);
  const lastError = useCoreStore((state) => state.lastError);
  const setPhase = useOnboardingStore((s) => s.setPhase);

  const [fallbackDismissed, setFallbackDismissed] = useState(false);
  const wasFallbackRef = useRef(false);

  const [welcomeVisible, setWelcomeVisible] = useState(false);
  const [birth, setBirth] = useState<BirthProgress | null>(null);

  useEffect(() => {
    if (!wasFallbackRef.current && fallbackMode) {
      setFallbackDismissed(false);
    }
    wasFallbackRef.current = fallbackMode;
  }, [fallbackMode]);

  useEffect(() => {
    try {
      const show = localStorage.getItem(WELCOME_FLAG) === "1";
      const dismissed = localStorage.getItem(DISMISS_KEY) === "1";
      if (show && !dismissed) {
        setWelcomeVisible(true);
        localStorage.removeItem(WELCOME_FLAG);
      }
    } catch {
      // ignore storage failures
    }
  }, []);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const payload = (await fetchBirthStatus()) as unknown as BirthProgress;
        if (active) {
          setBirth(payload);
        }
      } catch {
        /* backend may be down briefly */
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const birthActive =
    birth != null &&
    birth.status !== "idle" &&
    (birth.status === "running" ||
      (birth.status === "completed" && (birth.progress?.progress_pct ?? 100) < 100));

  const health = useBackendHealthSnapshot();

  const { blocking: activeOverlay } = resolveDeckStatus({
    backendDown: health.known && !health.alive,
    birthActive,
    welcomeVisible,
    fallbackActive: fallbackMode && !fallbackDismissed,
    backendRecovered: false,
    syncPending: false,
    syncError: false,
  });

  const dismissWelcome = () => {
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      // ignore
    }
    setWelcomeVisible(false);
  };

  return (
    <AnimatePresence initial={false}>
      {activeOverlay === "backend" ? (
        <BackendDownPanel key="backend" onRetry={() => void refreshBackendHealth()} />
      ) : null}
      {activeOverlay === "birth" && birth ? (
        <BirthProgressPanel
          key="birth"
          birth={birth}
          onViewProgress={() => setPhase("birth")}
        />
      ) : null}
      {activeOverlay === "fallback" ? (
        <FallbackPanel
          key="fallback"
          lastError={lastError}
          onDismiss={() => setFallbackDismissed(true)}
        />
      ) : null}
      {activeOverlay === "welcome" ? (
        <WelcomePanel key="welcome" onDismiss={dismissWelcome} />
      ) : null}
    </AnimatePresence>
  );
}
