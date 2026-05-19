import { useEffect, useRef } from "react";

import { logCoreEvent } from "@/lib/coreEventLogger";
import {
  REAL_SAFE_MODE_THRESHOLD_MS,
  shouldArmSafeModeTimer,
} from "@/lib/realSafeMode";
import {
  selectConnectionStatus,
  selectCurrentMode,
  selectFallbackMode,
  useCoreStore,
} from "@/store/coreStore";

export function useRealSafeModeMonitor(): void {
  const operatorMode = useCoreStore(selectCurrentMode);
  const connectionStatus = useCoreStore(selectConnectionStatus);
  const fallbackMode = useCoreStore(selectFallbackMode);
  const reconnectAttempt = useCoreStore((state) => state.reconnectAttempt);
  const lastError = useCoreStore((state) => state.lastError);
  const safeModeActive = useCoreStore((state) => state.safeModeActive);
  const safeModeSince = useCoreStore((state) => state.safeModeSince);
  const setSafeModeActive = useCoreStore((state) => state.setSafeModeActive);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const enterLoggedRef = useRef(false);
  const safeModeSinceRef = useRef<string | null>(null);

  useEffect(() => {
    safeModeSinceRef.current = safeModeSince;
  }, [safeModeSince]);

  useEffect(() => {
    const clearTimer = () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };

    if (connectionStatus === "connected") {
      clearTimer();
      enterLoggedRef.current = false;

      if (safeModeActive) {
        const since = safeModeSinceRef.current;
        const durationMs =
          since !== null
            ? Math.max(0, Date.now() - Date.parse(since))
            : REAL_SAFE_MODE_THRESHOLD_MS;

        setSafeModeActive(false);
        void logCoreEvent("REAL_SAFE_MODE_EXIT", {
          operator_mode: operatorMode,
          connection_status: connectionStatus,
          fallback_mode: fallbackMode,
          reconnect_attempt: reconnectAttempt,
          last_error: lastError,
          duration_ms: durationMs,
        });
      }
      return;
    }

    if (!shouldArmSafeModeTimer(operatorMode, connectionStatus)) {
      clearTimer();
      enterLoggedRef.current = false;

      if (safeModeActive) {
        setSafeModeActive(false);
      }
      return;
    }

    if (safeModeActive || timerRef.current !== null) {
      return;
    }

    timerRef.current = setTimeout(() => {
      timerRef.current = null;

      const state = useCoreStore.getState();
      if (
        state.operatorMode !== "REAL" ||
        state.connectionStatus === "connected" ||
        state.safeModeActive
      ) {
        return;
      }

      const since = new Date().toISOString();
      setSafeModeActive(true, since);

      if (!enterLoggedRef.current) {
        enterLoggedRef.current = true;
        void logCoreEvent("REAL_SAFE_MODE_ENTER", {
          operator_mode: state.operatorMode,
          connection_status: state.connectionStatus,
          fallback_mode: state.fallbackMode,
          reconnect_attempt: state.reconnectAttempt,
          last_error: state.lastError,
        });
      }
    }, REAL_SAFE_MODE_THRESHOLD_MS);

    return clearTimer;
  }, [
    connectionStatus,
    fallbackMode,
    lastError,
    operatorMode,
    reconnectAttempt,
    safeModeActive,
    setSafeModeActive,
  ]);
}
