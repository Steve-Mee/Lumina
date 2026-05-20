import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { subscribeOrganismClock } from "@/lib/organismClockStore";

const OrganismEnvelopeContext = createContext(0.5);

interface OrganismEnvelopeProviderProps {
  children: ReactNode;
}

/** Envelope reader from shared organism clock (no CSS polling). */
export function OrganismEnvelopeProvider({ children }: OrganismEnvelopeProviderProps) {
  const [envelope, setEnvelope] = useState(0.5);

  useEffect(() => subscribeOrganismClock((snap) => setEnvelope(snap.envelope)), []);

  return (
    <OrganismEnvelopeContext.Provider value={envelope}>{children}</OrganismEnvelopeContext.Provider>
  );
}

export function useOrganismEnvelope(): number {
  return useContext(OrganismEnvelopeContext);
}
