import { useEffect, useRef, useState } from "react";

import {
  getBackendHealthSnapshot,
  subscribeBackendHealth,
} from "@/lib/backendHealthStore";
import {
  resolveDeckStatus,
  type DeckStatusInput,
  type DeckStatusRailChip,
} from "@/lib/deckStatusOrchestrator";
import { selectFallbackMode, selectModeSyncStatus, useCoreStore } from "@/store/coreStore";

const RECOVERY_CHIP_MS = 3000;

export interface DeckStatusRailState {
  railChip: DeckStatusRailChip;
}

export function useDeckStatusRail(): DeckStatusRailState {
  const [health, setHealth] = useState(getBackendHealthSnapshot);
  const [recoveryFlash, setRecoveryFlash] = useState(false);
  const wasAliveRef = useRef(health.alive);
  const fallbackMode = useCoreStore(selectFallbackMode);
  const modeSyncStatus = useCoreStore(selectModeSyncStatus);

  useEffect(() => subscribeBackendHealth(setHealth, true), []);

  useEffect(() => {
    if (health.known && !wasAliveRef.current && health.alive) {
      setRecoveryFlash(true);
      const timer = window.setTimeout(() => setRecoveryFlash(false), RECOVERY_CHIP_MS);
      return () => window.clearTimeout(timer);
    }
    if (health.known) {
      wasAliveRef.current = health.alive;
    }
    return undefined;
  }, [health.alive, health.known]);

  const input: DeckStatusInput = {
    backendDown: false,
    birthActive: false,
    fallbackActive: false,
    welcomeVisible: false,
    backendRecovered: recoveryFlash,
    syncPending: modeSyncStatus === "pending",
    syncError: modeSyncStatus === "error",
  };

  const resolution = resolveDeckStatus(input);
  let railChip = resolution.railChip;
  if (!railChip && fallbackMode) {
    railChip = "fallback";
  }

  return { railChip };
}

export function resolveDeckBlockingStatus(
  input: Pick<
    DeckStatusInput,
    "birthActive" | "welcomeVisible" | "fallbackActive"
  >,
): ReturnType<typeof resolveDeckStatus> {
  const health = getBackendHealthSnapshot();
  return resolveDeckStatus({
    ...input,
    backendDown: health.known && !health.alive,
    backendRecovered: false,
    syncPending: false,
    syncError: false,
  });
}
