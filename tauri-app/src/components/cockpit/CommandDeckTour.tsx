import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useModeMotion } from "@/hooks/useModeMotion";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { panelCrossfadeWith, transitionOrNone } from "@/lib/motionPresets";
import { modeAccentCssVars } from "@/lib/modePresentation";
import { selectCurrentMode, useCoreStore } from "@/store/coreStore";

export const TOUR_KEY = "lumina.deck.tourComplete";
const TOUR_START_EVENT = "lumina:deck-tour-start";

const STEPS = [
  {
    target: '[data-tour="risk-citadel"]',
    title: "Risk Citadel",
    body: "Left column — live drawdown buffer, fortress integrity, and capital protection metrics.",
  },
  {
    target: '[data-tour="evolution-deck"]',
    title: "Evolution Deck",
    body: "Center — PPO training, evolution arena graph, and SIM readiness before going live.",
  },
  {
    target: '[data-tour="intelligence-deck"]',
    title: "Intelligence Brief",
    body: "Right column — decision theater, performance KPIs, monitor, and live activity.",
  },
  {
    target: '[data-tour="command-hud"]',
    title: "Command HUD",
    body: "Top bar — SIM/REAL mode, engine start/stop, safety actions, and settings.",
  },
  {
    target: '[data-tour="settings-button"]',
    title: "Settings & API key",
    body: "Open Settings to sync your admin API key from .env, tune visuals, and replay this tour.",
  },
] as const;

export function resetCommandDeckTour(): void {
  try {
    localStorage.removeItem(TOUR_KEY);
  } catch {
    // ignore
  }
  window.dispatchEvent(new Event(TOUR_START_EVENT));
}

function getTargetRect(selector: string): DOMRect | null {
  const el = document.querySelector(selector);
  return el?.getBoundingClientRect() ?? null;
}

export function CommandDeckTour() {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const reducedMotion = usePrefersReducedMotion();
  const modeMotion = useModeMotion();
  const operatorMode = useCoreStore(selectCurrentMode);

  useEffect(() => {
    if (localStorage.getItem(TOUR_KEY)) {
      return;
    }
    const timer = window.setTimeout(() => setVisible(true), 600);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const onStart = () => {
      setStep(0);
      setVisible(true);
    };
    window.addEventListener(TOUR_START_EVENT, onStart);
    return () => window.removeEventListener(TOUR_START_EVENT, onStart);
  }, []);

  useEffect(() => {
    if (!visible) {
      return;
    }
    const update = () => setRect(getTargetRect(STEPS[step].target));
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    const id = window.setInterval(update, 400);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
      window.clearInterval(id);
    };
  }, [visible, step]);

  const dismiss = (persist: boolean) => {
    if (persist) {
      localStorage.setItem(TOUR_KEY, "1");
    }
    setVisible(false);
  };

  if (!visible) {
    return null;
  }

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <div
      className="fixed inset-0 z-[100] pointer-events-none"
      data-mode={operatorMode}
      style={modeAccentCssVars(operatorMode)}
    >
      {rect ? (
        <div
          className="deck-tour-spotlight absolute transition-all duration-300"
          style={{
            top: rect.top - 4,
            left: rect.left - 4,
            width: rect.width + 8,
            height: rect.height + 8,
            boxShadow: "0 0 0 9999px rgba(0,0,0,0.65)",
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-black/70" />
      )}

      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          className="deck-tour-card pointer-events-auto absolute bottom-24 left-1/2 w-[min(420px,calc(100vw-2rem))] -translate-x-1/2 rounded-xl p-5 shadow-2xl"
          variants={panelCrossfadeWith(modeMotion)}
          initial={reducedMotion ? false : "hidden"}
          animate="visible"
          exit={reducedMotion ? undefined : "exit"}
          transition={transitionOrNone(reducedMotion, modeMotion)}
        >
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <p className="deck-tour-card__eyebrow">
                Command deck tour · {step + 1}/{STEPS.length}
              </p>
              <h3 className="deck-tour-card__title mt-1 text-base font-semibold">{current.title}</h3>
            </div>
            <button
              type="button"
              className="rounded p-1 text-muted-foreground hover:bg-white/10 hover:text-foreground"
              aria-label="Close tour for this session"
              onClick={() => dismiss(false)}
            >
              <X className="size-4" />
            </button>
          </div>
          <p className="text-sm leading-relaxed text-muted-foreground">{current.body}</p>
          <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
            <Button type="button" variant="command-ghost" size="sm" onClick={() => dismiss(true)}>
              Don&apos;t show again
            </Button>
            <div className="flex gap-2">
              {step > 0 ? (
                <Button type="button" variant="command-ghost" size="sm" onClick={() => setStep((s) => s - 1)}>
                  Back
                </Button>
              ) : null}
              <Button
                type="button"
                size="sm"
                variant="command-primary"
                onClick={() => {
                  if (isLast) {
                    dismiss(true);
                  } else {
                    setStep((s) => s + 1);
                  }
                }}
              >
                {isLast ? (
                  <>
                    <CheckCircle2 className="mr-1.5 size-4" />
                    Got it
                  </>
                ) : (
                  "Next"
                )}
              </Button>
            </div>
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
