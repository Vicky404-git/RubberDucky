import type { BridgeEvent, StatusResponse } from "../types/api";

export type ConnectionState = "connecting" | "online" | "offline";

interface StreamHandlers {
  onEvent: (event: BridgeEvent) => void;
  onStatus: (status: StatusResponse) => void;
  onConnection: (state: ConnectionState) => void;
}

function socketUrl(): string {
  const explicit = import.meta.env.VITE_BRIDGE_URL as string | undefined;
  if (explicit) {
    try {
      const url = new URL(explicit);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      url.pathname = "/ws/events";
      url.search = "";
      return url.toString();
    } catch {
      // Fall through to same-origin.
    }
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/events`;
}

export function createEventStream(handlers: StreamHandlers): () => void {
  let socket: WebSocket | null = null;
  let closed = false;
  let attempts = 0;
  let reconnectTimer: number | null = null;

  const connect = () => {
    if (closed) return;
    handlers.onConnection(attempts === 0 ? "connecting" : "offline");
    try {
      socket = new WebSocket(socketUrl());
    } catch {
      scheduleReconnect();
      return;
    }

    socket.onopen = () => {
      attempts = 0;
      handlers.onConnection("online");
    };

    socket.onmessage = (message) => {
      try {
        const parsed = JSON.parse(String(message.data)) as BridgeEvent;
        if (
          parsed.type === "snapshot" &&
          typeof parsed.status === "object" &&
          parsed.status !== null
        ) {
          handlers.onStatus(parsed.status as StatusResponse);
        }
        handlers.onEvent(parsed);
      } catch {
        // Ignore malformed frames; the bridge is the only producer.
      }
    };

    socket.onerror = () => {
      handlers.onConnection("offline");
    };

    socket.onclose = () => {
      handlers.onConnection("offline");
      scheduleReconnect();
    };
  };

  const scheduleReconnect = () => {
    if (closed || reconnectTimer !== null) return;
    attempts += 1;
    const delay = Math.min(1000 * 2 ** Math.min(attempts, 4), 12000);
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delay);
  };

  connect();

  return () => {
    closed = true;
    if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
    socket?.close();
  };
}
