import { useCallback, useEffect, useRef } from "react";

import {
  DECK_TRANSITION_DURATION,
  type DeckTransitionState,
  IDLE_TRANSITION,
  createTransitionState,
} from "@/lib/deckTransitionOrchestrator";

export function usePanelTabTransition(scopeSelector: string) {
  const timerRef = useRef<number | null>(null);
  const activeRef = useRef(false);

  const pulseTabTransition = useCallback(() => {
    const panel = document.querySelector(scopeSelector);
    if (!panel) {
      return;
    }
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current);
    }
    panel.classList.add("panel-tab-transition-active");
    activeRef.current = true;
    timerRef.current = window.setTimeout(() => {
      panel.classList.remove("panel-tab-transition-active");
      activeRef.current = false;
      timerRef.current = null;
    }, DECK_TRANSITION_DURATION.panelTab * 1000);
  }, [scopeSelector]);

  useEffect(
    () => () => {
      if (timerRef.current != null) {
        window.clearTimeout(timerRef.current);
      }
      if (activeRef.current) {
        document.querySelector(scopeSelector)?.classList.remove("panel-tab-transition-active");
      }
    },
    [scopeSelector],
  );

  return { pulseTabTransition };
}

export function createPanelTabTransitionState(): DeckTransitionState {
  return createTransitionState({ kind: "panelTab" });
}

export { IDLE_TRANSITION };
