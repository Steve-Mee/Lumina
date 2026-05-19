import { createContext, useContext, type ReactNode } from "react";

import { usePPOEvolution } from "@/hooks/usePPOEvolution";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";

interface PPOEvolutionContextValue {
  logs: PPOEvolutionMetric[];
  connected: boolean;
}

const PPOEvolutionContext = createContext<PPOEvolutionContextValue | null>(null);

interface PPOEvolutionProviderProps {
  enabled?: boolean;
  children: ReactNode;
}

export function PPOEvolutionProvider({ enabled = true, children }: PPOEvolutionProviderProps) {
  const { logs, connected } = usePPOEvolution(enabled);

  return (
    <PPOEvolutionContext.Provider value={{ logs, connected }}>
      {children}
    </PPOEvolutionContext.Provider>
  );
}

export function usePPOEvolutionLive(): PPOEvolutionContextValue {
  const context = useContext(PPOEvolutionContext);
  if (!context) {
    throw new Error("usePPOEvolutionLive must be used within PPOEvolutionProvider");
  }
  return context;
}
