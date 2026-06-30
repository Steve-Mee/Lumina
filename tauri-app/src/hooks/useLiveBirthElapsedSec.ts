import { useEffect, useState } from "react";

import type { BirthProgressPayload } from "@/lib/birthClient";
import { resolveLiveBirthElapsedSec } from "@/lib/birthPhaseModel";

export function useLiveBirthElapsedSec(
  progress: BirthProgressPayload | undefined,
  statusElapsedSeconds?: number,
): number | null {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const startMs = progress?.birth_start_time;
    const hasClock =
      (startMs != null && Number(startMs) > 0) ||
      progress?.elapsed_sec != null ||
      statusElapsedSeconds != null;
    if (!hasClock) {
      return;
    }
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [progress?.birth_start_time, progress?.elapsed_sec, statusElapsedSeconds]);

  return resolveLiveBirthElapsedSec(progress, statusElapsedSeconds, nowMs);
}
