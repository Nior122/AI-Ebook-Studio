"use client";

// Live WebSocket hook for the workspace. Connects to /ws/projects/{id} with the
// Clerk session token, streams job.progress / job.terminal / activity.created /
// notification.created / version.restored / stage.changed events, and
// auto-reconnects with backoff. Falls back silently when the socket is closed.

import { useAuth } from "@clerk/nextjs";
import { useEffect, useRef } from "react";

export interface StudioWsEvent {
  type: string;
  payload: Record<string, unknown>;
  ts: string;
}

export function useStudioSocket(
  projectId: string | undefined,
  onEvent: (event: StudioWsEvent) => void,
): { connected: boolean } {
  const { getToken } = useAuth();
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;
  const connectedRef = useRef(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

    const connect = async () => {
      if (cancelled) return;
      try {
        const token = await getToken();
        if (!token || cancelled) {
          if (!cancelled) retryTimer = setTimeout(connect, 3000);
          return;
        }
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";
        const wsUrl = `${protocol}//${window.location.host}${base}/ws/projects/${projectId}?token=${encodeURIComponent(token)}`;
        const socket = new WebSocket(wsUrl);
        socketRef.current = socket;

        socket.onopen = () => {
          attempt = 0;
          connectedRef.current = true;
        };
        socket.onmessage = (message) => {
          try {
            const event = JSON.parse(String(message.data)) as StudioWsEvent;
            if (event.type === "ping" || event.type === "connected") return;
            onEventRef.current(event);
          } catch {
            // Ignore malformed frames.
          }
        };
        socket.onclose = () => {
          connectedRef.current = false;
          if (!cancelled) {
            attempt += 1;
            retryTimer = setTimeout(connect, Math.min(1000 * 2 ** attempt, 15000));
          }
        };
        socket.onerror = () => socket.close();
      } catch {
        if (!cancelled) retryTimer = setTimeout(connect, 3000);
      }
    };

    void connect();
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      socketRef.current?.close();
      socketRef.current = null;
      connectedRef.current = false;
    };
  }, [projectId, getToken]);

  return { connected: connectedRef.current };
}
