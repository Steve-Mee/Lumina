import { useCallback, useState } from "react";

import {
  IDLE_TRANSITION,
  createTransitionState,
  type DeckTransitionRequest,
  type DeckTransitionState,
} from "@/lib/deckTransitionOrchestrator";

export function useDeckTransition() {
  const [transition, setTransition] = useState<DeckTransitionState>(IDLE_TRANSITION);

  const startTransition = useCallback((request: DeckTransitionRequest) => {
    setTransition(createTransitionState(request));
  }, []);

  const completeTransition = useCallback(() => {
    setTransition(IDLE_TRANSITION);
  }, []);

  return { transition, startTransition, completeTransition };
}
