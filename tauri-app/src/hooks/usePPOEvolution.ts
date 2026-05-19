import { useEffect, useRef, useState } from "react";

import {
  parsePpoEvolutionLine,
  resolvePpoEvolutionWsUrl,
} from "@/lib/ppoEvolutionClient";
import type { PPOEvolutionMetric } from "@/lib/ppoEvolutionTypes";
import { PPO_EVOLUTION_MAX_POINTS } from "@/lib/ppoEvolutionTypes";

const BACKOFF_BASE_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;
const BACKOFF_JITTER_MS = 250;
const KEEPALIVE_INTERVAL_MS = 30_000;

function appendLog(
  prev: PPOEvolutionMetric[],
  entry: PPOEvolutionMetric,
): PPOEvolutionMetric[] {
  const next = [...prev, entry];
  if (next.length <= PPO_EVOLUTION_MAX_POINTS) return next;
  return next.slice(next.length - PPO_EVOLUTION_MAX_POINTS);
}

export function usePPOEvolution(enabled = true): {
  logs: PPOEvolutionMetric[];
  connected: boolean;
} {
  const [logs, setLogs] = useState<PPOEvolutionMetric[]>([]);
  const [connected, setConnected] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const keepaliveTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const intentionalCloseRef = useRef(false);
  const resolvedUrlRef = useRef(resolvePpoEvolutionWsUrl());

  useEffect(() => {
    if (!enabled) {
      intentionalCloseRef.current = true;
      socketRef.current?.close();
      socketRef.current = null;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (keepaliveTimerRef.current) clearInterval(keepaliveTimerRef.current);
      setConnected(false);
      return;
    }

    intentionalCloseRef.current = false;
    reconnectAttemptRef.current = 0;
    resolvedUrlRef.current = resolvePpoEvolutionWsUrl();

    const clearReconnectTimer = () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const clearKeepaliveTimer = () => {
      if (keepaliveTimerRef.current) {
        clearInterval(keepaliveTimerRef.current);
        keepaliveTimerRef.current = null;
      }
    };

    const scheduleReconnect = () => {
      if (intentionalCloseRef.current) return;
      clearReconnectTimer();
      const attempt = reconnectAttemptRef.current;
      const delay = Math.min(
        BACKOFF_MAX_MS,
        BACKOFF_BASE_MS * 2 ** attempt + Math.random() * BACKOFF_JITTER_MS,
      );
      reconnectAttemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(() => {
        openSocket(resolvedUrlRef.current);
      }, delay);
    };

    const startKeepalive = (ws: WebSocket) => {
      clearKeepaliveTimer();
      keepaliveTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, KEEPALIVE_INTERVAL_MS);
    };

    const openSocket = (url: string) => {
      if (intentionalCloseRef.current) return;

      const existing = socketRef.current;
      if (
        existing &&
        (existing.readyState === WebSocket.OPEN ||
          existing.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      clearReconnectTimer();
      clearKeepaliveTimer();
      setConnected(false);

      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        if (socketRef.current !== ws) return;
        reconnectAttemptRef.current = 0;
        setConnected(true);
        startKeepalive(ws);
      };

      ws.onmessage = (event) => {
        if (socketRef.current !== ws) return;
        const text = typeof event.data === "string" ? event.data : "";
        const entry = parsePpoEvolutionLine(text);
        if (entry) {
          setLogs((prev) => appendLog(prev, entry));
        }
      };

      ws.onerror = () => {
        if (socketRef.current !== ws) return;
        setConnected(false);
      };

      ws.onclose = () => {
        if (socketRef.current !== ws) return;
        socketRef.current = null;
        clearKeepaliveTimer();
        setConnected(false);

        if (intentionalCloseRef.current) return;
        scheduleReconnect();
      };
    };

    openSocket(resolvedUrlRef.current);

    return () => {
      intentionalCloseRef.current = true;
      clearReconnectTimer();
      clearKeepaliveTimer();
      socketRef.current?.close();
      socketRef.current = null;
      setConnected(false);
    };
  }, [enabled]);

  return { logs, connected };
}
