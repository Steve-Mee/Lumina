import { useCoreStore } from "@/store/coreStore";

export type { ConnectionStatus } from "@/store/coreStore";

export interface ActiveMutation {
  hash: string;
  timestamp: string | null;
  challenger_count: number;
}

export interface CoreLiveTelemetry {
  mode: string;
  equity: number | null;
  regime: string;
  risk_level: string;
  active_mutations: ActiveMutation[];
  source_ts: string | null;
}

export interface TelemetryFrame {
  type: "telemetry";
  seq: number;
  ts: string;
  payload: CoreLiveTelemetry;
}

const BACKOFF_BASE_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;
const BACKOFF_JITTER_MS = 250;
const KEEPALIVE_INTERVAL_MS = 30_000;
const FALLBACK_THRESHOLD_MS = 10_000;
const POLL_INTERVAL_MS = 2_000;

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let keepaliveTimer: ReturnType<typeof setInterval> | null = null;
let fallbackThresholdTimer: ReturnType<typeof setTimeout> | null = null;
let pollIntervalTimer: ReturnType<typeof setInterval> | null = null;
let intentionalClose = false;
let resolvedUrl: string | null = null;
let pollSeq = 0;

export function resolveCoreLiveUrl(override?: string): string {
  if (override) {
    return override;
  }
  const envWs = import.meta.env.VITE_LUMINA_BACKEND_WS_URL;
  if (envWs) {
    return envWs;
  }
  const httpBase =
    import.meta.env.VITE_LUMINA_BACKEND_URL ?? "http://127.0.0.1:8000";
  return (
    httpBase.replace(/^http/, "ws").replace(/\/$/, "") + "/ws/core/live"
  );
}

export function resolveCoreLiveHttpUrl(): string {
  const base =
    import.meta.env.VITE_LUMINA_BACKEND_URL ?? "http://127.0.0.1:8000";
  return base.replace(/\/$/, "") + "/api/core/live";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseActiveMutation(value: unknown): ActiveMutation | null {
  if (!isRecord(value)) {
    return null;
  }
  return {
    hash: typeof value.hash === "string" ? value.hash : "",
    timestamp:
      typeof value.timestamp === "string" ? value.timestamp : null,
    challenger_count:
      typeof value.challenger_count === "number"
        ? value.challenger_count
        : 0,
  };
}

function parseTelemetryPayload(value: unknown): CoreLiveTelemetry | null {
  if (!isRecord(value)) {
    return null;
  }

  const mutationsRaw = value.active_mutations;
  const active_mutations = Array.isArray(mutationsRaw)
    ? mutationsRaw
        .map(parseActiveMutation)
        .filter((item): item is ActiveMutation => item !== null)
    : [];

  return {
    mode: typeof value.mode === "string" ? value.mode : "unknown",
    equity:
      typeof value.equity === "number"
        ? value.equity
        : value.equity === null
          ? null
          : null,
    regime: typeof value.regime === "string" ? value.regime : "UNKNOWN",
    risk_level:
      typeof value.risk_level === "string" ? value.risk_level : "UNKNOWN",
    active_mutations,
    source_ts:
      typeof value.source_ts === "string" ? value.source_ts : null,
  };
}

function parseTelemetryFrame(raw: unknown): TelemetryFrame | null {
  if (!isRecord(raw) || raw.type !== "telemetry") {
    return null;
  }
  if (typeof raw.seq !== "number" || typeof raw.ts !== "string") {
    return null;
  }
  const payload = parseTelemetryPayload(raw.payload);
  if (!payload) {
    return null;
  }
  return {
    type: "telemetry",
    seq: raw.seq,
    ts: raw.ts,
    payload,
  };
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

function clearFallbackThresholdTimer(): void {
  if (fallbackThresholdTimer !== null) {
    clearTimeout(fallbackThresholdTimer);
    fallbackThresholdTimer = null;
  }
}

function stopPolling(): void {
  if (pollIntervalTimer !== null) {
    clearInterval(pollIntervalTimer);
    pollIntervalTimer = null;
  }
}

function isWebSocketConnected(): boolean {
  return socket?.readyState === WebSocket.OPEN;
}

function armFallbackThreshold(): void {
  if (intentionalClose || isWebSocketConnected()) {
    return;
  }

  clearFallbackThresholdTimer();
  fallbackThresholdTimer = setTimeout(() => {
    fallbackThresholdTimer = null;
    if (intentionalClose || isWebSocketConnected()) {
      return;
    }
    startPollingFallback();
  }, FALLBACK_THRESHOLD_MS);
}

async function fetchTelemetryFrame(): Promise<TelemetryFrame | null> {
  try {
    const response = await fetch(resolveCoreLiveHttpUrl());
    if (!response.ok) {
      useCoreStore
        .getState()
        .setLastError(`Polling failed: HTTP ${response.status}`);
      return null;
    }
    const parsed: unknown = await response.json();
    const frame = parseTelemetryFrame(parsed);
    if (!frame) {
      useCoreStore
        .getState()
        .setLastError("Received malformed polling payload");
      return null;
    }
    pollSeq += 1;
    return { ...frame, seq: pollSeq };
  } catch {
    useCoreStore.getState().setLastError("Polling request failed");
    return null;
  }
}

async function pollOnce(): Promise<void> {
  if (intentionalClose || isWebSocketConnected()) {
    return;
  }
  const frame = await fetchTelemetryFrame();
  if (frame) {
    useCoreStore.getState().applyTelemetryFrame(frame);
  }
}

function startPollingFallback(): void {
  const store = useCoreStore.getState();
  if (intentionalClose || isWebSocketConnected()) {
    return;
  }

  store.setFallbackMode(true);
  stopPolling();
  void pollOnce();
  pollIntervalTimer = setInterval(() => {
    void pollOnce();
  }, POLL_INTERVAL_MS);
}

function exitFallbackMode(): void {
  clearFallbackThresholdTimer();
  stopPolling();
  useCoreStore.getState().setFallbackMode(false);
}

function scheduleReconnect(): void {
  const store = useCoreStore.getState();
  if (intentionalClose) {
    return;
  }

  store.setConnectionStatus("reconnecting");
  store.setReconnectAttempt(store.reconnectAttempt + 1);
  armFallbackThreshold();

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
  armFallbackThreshold();

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
    pollSeq = 0;
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
