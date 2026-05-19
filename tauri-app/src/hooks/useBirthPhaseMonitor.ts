import { useEffect, useRef } from "react";

import { useBirthStore } from "@/store/birthStore";

const POLL_MS = 2000;

export function useBirthPhaseMonitor() {
  const poll = useBirthStore((s) => s.poll);

  useEffect(() => {
    void poll();
    const timer = window.setInterval(() => void poll(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [poll]);
}

export function useBirthFinaleActions() {
  const finaleTimerRef = useRef<number | null>(null);
  return finaleTimerRef;
}
