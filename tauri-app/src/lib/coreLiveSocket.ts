import { useCoreStore } from "@/store/coreStore";

import {
  armFallbackThreshold,
  exitFallbackMode,
  resetPollSeq,
  startPollingFallback,
} from "@/lib/coreLivePoller";
import {
  parseTelemetryFrame,
  resolveCoreLiveUrl,
} from "@/lib/coreLiveTelemetry";

const BACKOFF_BASE_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;
const BACKOFF_JITTER_MS = 250;
const KEEPALIVE_INTERVAL_MS = 30_000;

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let keepaliveTimer: ReturnType<typeof setInterval> | null = null;
let intentionalClose = false;
let resolvedUrl: string | null = null;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isWebSocketConnected(): boolean {
  return socket?.readyState === WebSocket.OPEN;
}

function isIntentionalClose(): boolean {
  return intentionalClose;
}

function clearReconnectTimer(): void {
  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function clearKeepaliveTimer(): void {
  if (keepaliveTimer !== null) {
    clearInterval(keepaliveTimer);
    keepaliveTimer = null;
  }
}

function scheduleReconnect(): void {
  const store = useCoreStore.getState();
  if (intentionalClose) {
    return;
  }

  store.setConnectionStatus("reconnecting");
  store.setReconnectAttempt(store.reconnectAttempt + 1);
  armFallbackThreshold(
    isWebSocketConnected,
    isIntentionalClose,
    () => startPollingFallback(isWebSocketConnected, isIntentionalClose),
  );

  const attempt = useCoreStore.getState().reconnectAttempt;
  const delay =
    Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** Math.max(0, attempt - 1)) +
    Math.floor(Math.random() * BACKOFF_JITTER_MS);

  clearReconnectTimer();
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    openSocket(resolvedUrl ?? resolveCoreLiveUrl());
  }, delay);
}

function startKeepalive(): void {
  clearKeepaliveTimer();
  keepaliveTimer = setInterval(() => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "ping" }));
    }
  }, KEEPALIVE_INTERVAL_MS);
}

function openSocket(url: string): void {
  if (
    socket &&
    (socket.readyState === WebSocket.OPEN ||
      socket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  resolvedUrl = url;
  intentionalClose = false;
  const store = useCoreStore.getState();
  store.setConnectionStatus(
    store.connectionStatus === "reconnecting" ? "reconnecting" : "connecting",
  );
  armFallbackThreshold(
    isWebSocketConnected,
    isIntentionalClose,
    () => startPollingFallback(isWebSocketConnected, isIntentionalClose),
  );

  const ws = new WebSocket(url);
  socket = ws;

  ws.onopen = () => {
    if (socket !== ws) {
      return;
    }
    const openStore = useCoreStore.getState();
    exitFallbackMode();
    openStore.setConnectionStatus("connected");
    openStore.resetReconnectAttempt();
    openStore.setLastError(null);
    resetPollSeq();
    startKeepalive();
  };

  ws.onmessage = (event) => {
    if (socket !== ws) {
      return;
    }
    try {
      const parsed: unknown = JSON.parse(String(event.data));
      if (isRecord(parsed) && parsed.type === "pong") {
        return;
      }
      const frame = parseTelemetryFrame(parsed);
      if (!frame) {
        useCoreStore
          .getState()
          .setLastError("Received malformed telemetry frame");
        return;
      }
      useCoreStore.getState().applyTelemetryFrame(frame);
    } catch {
      useCoreStore.getState().setLastError("Failed to parse WebSocket message");
    }
  };

  ws.onerror = () => {
    if (socket !== ws) {
      return;
    }
    useCoreStore.getState().setLastError("WebSocket connection error");
  };

  ws.onclose = () => {
    if (socket !== ws) {
      return;
    }
    socket = null;
    clearKeepaliveTimer();

    if (intentionalClose) {
      exitFallbackMode();
      useCoreStore.getState().setConnectionStatus("disconnected");
      return;
    }

    useCoreStore.getState().setLastError("WebSocket connection closed");
    scheduleReconnect();
  };
}

export function connectCoreLive(url?: string): void {
  intentionalClose = false;
  clearReconnectTimer();
  openSocket(url ?? resolveCoreLiveUrl());
}

export function disconnectCoreLive(): void {
  intentionalClose = true;
  clearReconnectTimer();
  clearKeepaliveTimer();
  exitFallbackMode();

  if (socket) {
    socket.close();
    socket = null;
  }

  useCoreStore.getState().setConnectionStatus("disconnected");
}