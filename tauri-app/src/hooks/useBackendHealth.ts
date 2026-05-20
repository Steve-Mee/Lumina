import { useEffect, useState } from "react";

import {
  getBackendAlive,
  getBackendHealthKnown,
  getBackendHealthSnapshot,
  subscribeBackendHealth,
  type BackendHealthSnapshot,
} from "@/lib/backendHealthStore";

export function useBackendHealth(): boolean {
  const [alive, setAlive] = useState(getBackendAlive);

  useEffect(() => subscribeBackendHealth(setAlive), []);

  return alive;
}

export function useBackendHealthKnown(): boolean {
  const [known, setKnown] = useState(getBackendHealthKnown);

  useEffect(
    () =>
      subscribeBackendHealth((state) => setKnown(state.known), true),
    [],
  );

  return known;
}

export function useBackendHealthSnapshot(): BackendHealthSnapshot {
  const [snapshot, setSnapshot] = useState(getBackendHealthSnapshot);

  useEffect(() => subscribeBackendHealth(setSnapshot, true), []);

  return snapshot;
}
