import { useEffect, useRef, useState } from "react";

import {
  fetchRuntimeStatus,
  type RuntimeStatus,
} from "@/lib/runtimeClient";

type Listener = (runtime: RuntimeStatus | null) => void;

let runtime: RuntimeStatus | null = null;
const listeners = new Set<Listener>();
let subscriberCount = 0;
let intervalId: ReturnType<typeof setInterval> | null = null;

function emit(): void {
  for (const listener of listeners) {
    listener(runtime);
  }
}

async function probe(): Promise<void> {
  try {
    runtime = await fetchRuntimeStatus();
  } catch {
    runtime = null;
  }
  emit();
}

function ensurePolling(): void {
  if (intervalId !== null) {
    return;
  }
  void probe();
  intervalId = setInterval(() => void probe(), 5000);
}

function stopPollingIfIdle(): void {
  if (subscriberCount === 0 && intervalId !== null) {
    clearInterval(intervalId);
    intervalId = null;
  }
}

export function refreshRuntimeStatus(): Promise<void> {
  return probe();
}

export function getRuntimeStatus(): RuntimeStatus | null {
  return runtime;
}

export function subscribeRuntimeStatus(listener: Listener): () => void {
  listeners.add(listener);
  subscriberCount += 1;
  listener(runtime);
  ensurePolling();
  return () => {
    listeners.delete(listener);
    subscriberCount -= 1;
    stopPollingIfIdle();
  };
}

export function useRuntimeStatusPoll(): RuntimeStatus | null {
  const [status, setStatus] = useState<RuntimeStatus | null>(() => runtime);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return subscribeRuntimeStatus((next) => {
      if (mounted.current) {
        setStatus(next);
      }
    });
  }, []);

  useEffect(() => {
    return () => {
      mounted.current = false;
    };
  }, []);

  return status;
}
