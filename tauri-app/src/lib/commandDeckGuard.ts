import { toast } from "sonner";

import type { CoreStore } from "@/store/coreStore";
import { useCoreStore } from "@/store/coreStore";

export function isCommandDeckBlocked(state: CoreStore): boolean {
  return state.operatorMode === "REAL" && state.safeModeActive;
}

export function assertCommandDeckAllowed(): boolean {
  const state = useCoreStore.getState();
  if (!isCommandDeckBlocked(state)) {
    return true;
  }
  toast.error("REAL safe mode active — trading controls are blocked until telemetry reconnects");
  return false;
}
