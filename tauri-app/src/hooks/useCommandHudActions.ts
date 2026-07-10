import { useCallback } from "react";
import { toast } from "sonner";

import { useDeckTransition } from "@/hooks/useDeckTransition";
import { handleRuntimeError } from "@/lib/runtimeErrorToast";
import { postApproveReal } from "@/lib/maturationClient";
import {
  emergencyStop,
  flattenPositions,
  pauseTradingSafely,
  startEngine,
  stopAllActivities,
  stopEngine,
} from "@/lib/runtimeClient";
import { refreshRuntimeStatus } from "@/hooks/useRuntimeStatusPoll";
import { useDeckPanelStore } from "@/store/deckPanelStore";
import { useCoreStore, type TradingMode } from "@/store/coreStore";
import { useBotConfigStore } from "@/store/botConfigStore";

interface UseCommandHudActionsOptions {
  currentMode: TradingMode;
  runtimeAlive: boolean | undefined;
  realTradingEligible: boolean;
  onRealConfirmOpen: () => void;
  onRealConfirmed?: () => void;
}

export function useCommandHudActions({
  currentMode,
  runtimeAlive,
  realTradingEligible,
  onRealConfirmOpen,
  onRealConfirmed,
}: UseCommandHudActionsOptions) {
  const { startTransition } = useDeckTransition();
  const setOperatorMode = useCoreStore((state) => state.setOperatorMode);
  const botConfigDirty = useBotConfigStore((s) => s.isDirty);
  const saveBotConfig = useBotConfigStore((s) => s.save);

  const handleModeSelect = useCallback(
    (mode: TradingMode) => {
      if (mode === currentMode) {
        return;
      }
      if (mode === "REAL") {
        if (!realTradingEligible) {
          toast.error(
            "REAL blocked — complete Awakening (certificate + Evolution Proof) and later maturation phases.",
          );
          return;
        }
        onRealConfirmOpen();
        return;
      }
      startTransition({ kind: "modeSwitch", targetMode: mode });
      setOperatorMode(mode);
    },
    [
      currentMode,
      onRealConfirmOpen,
      realTradingEligible,
      setOperatorMode,
      startTransition,
    ],
  );

  const confirmRealMode = useCallback(() => {
    void postApproveReal()
      .then(() => {
        startTransition({ kind: "modeSwitch", targetMode: "REAL" });
        setOperatorMode("REAL");
        onRealConfirmed?.();
        if (!sessionStorage.getItem("lumina.realOpsHintShown")) {
          sessionStorage.setItem("lumina.realOpsHintShown", "1");
          toast.info("REAL Ops tab unlocked in Intelligence deck", {
            action: {
              label: "Open REAL Ops",
              onClick: () => useDeckPanelStore.getState().setActiveRightTab("realOps"),
            },
          });
        }
      })
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "REAL approval failed");
      });
  }, [onRealConfirmed, setOperatorMode, startTransition]);

  const toggleEngine = useCallback(() => {
    void (runtimeAlive
      ? stopEngine()
          .then((r) => {
            toast.success(r.message);
            void refreshRuntimeStatus();
          })
          .catch(handleRuntimeError)
      : startEngine()
          .then((r) => {
            toast.success(r.message);
            void refreshRuntimeStatus();
          })
          .catch(handleRuntimeError));
  }, [runtimeAlive]);

  const saveAndStart = useCallback(() => {
    void (async () => {
      if (botConfigDirty()) {
        const ok = await saveBotConfig();
        if (!ok) {
          toast.error("Save bot config before starting engine");
          return;
        }
        toast.success("Bot configuration saved");
      }
      return startEngine()
        .then((r) => {
          toast.success(r.message);
          void refreshRuntimeStatus();
        })
        .catch(handleRuntimeError);
    })();
  }, [botConfigDirty, saveBotConfig]);

  const handleNerveActivate = useCallback(() => {
    if (botConfigDirty()) {
      saveAndStart();
      return;
    }
    toggleEngine();
  }, [botConfigDirty, saveAndStart, toggleEngine]);

  const pauseLiveTrading = useCallback(() => {
    void pauseTradingSafely()
      .then((r) => {
        toast.success(r.message);
        void refreshRuntimeStatus();
      })
      .catch(handleRuntimeError);
  }, []);

  const flatten = useCallback(() => {
    void flattenPositions()
      .then(() => toast.success("Positions flattened"))
      .catch(handleRuntimeError);
  }, []);

  const emergencyStopAction = useCallback(() => {
    void emergencyStop()
      .then(() => toast.success("Emergency stop executed"))
      .catch(handleRuntimeError);
  }, []);

  const stopAll = useCallback(() => {
    void stopAllActivities()
      .then((r) => toast.success(r.message))
      .catch(handleRuntimeError);
  }, []);

  return {
    handleModeSelect,
    confirmRealMode,
    toggleEngine,
    saveAndStart,
    handleNerveActivate,
    pauseLiveTrading,
    flatten,
    emergencyStopAction,
    stopAll,
  };
}