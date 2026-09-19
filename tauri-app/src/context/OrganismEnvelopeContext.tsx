import { createContext, useContext, type ReactNode } from "react";

import { getOrganismClock } from "@/lib/organismClockStore";

const OrganismEnvelopeContext = createContext(0.5);

interface OrganismEnvelopeProviderProps {
  children: ReactNode;
}

/**
 * Envelope lives on CSS vars (`--organism-envelope` via useOrganismShellVars).
 * Do not push rAF snapshots into React state — that re-renders the HUD/shell
 * at 60fps and stacks screen trees during startup layout.
 */
export function OrganismEnvelopeProvider({ children }: OrganismEnvelopeProviderProps) {
  return (
    <OrganismEnvelopeContext.Provider value={0.5}>{children}</OrganismEnvelopeContext.Provider>
  );
}

/** Static fallback. Prefer CSS `var(--organism-envelope)` for live breathe. */
export function useOrganismEnvelope(): number {
  const fallback = useContext(OrganismEnvelopeContext);
  const live = getOrganismClock().envelope;
  return Number.isFinite(live) ? live : fallback;
}
