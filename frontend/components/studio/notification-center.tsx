"use client";

// Notification center — bell with unread badge, dropdown list, mark read/all.
// Live-updates when the workspace WebSocket delivers notification.created.

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { studioApi, type NotificationRead } from "@/lib/api/studio";
import { IconBell, IconCheck } from "@/components/ui/icons";

const LEVEL_STYLES: Record<string, string> = {
  success: "border-l-emerald-500",
  error: "border-l-red-500",
  warning: "border-l-amber-500",
  info: "border-l-primary",
};

export function NotificationCenter({ refreshSignal }: { refreshSignal?: number }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const { data, refetch } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => studioApi.listNotifications({ limit: 30 }),
  });
  const unread = data?.unread ?? 0;
  const items = data?.items ?? [];

  useEffect(() => {
    if (refreshSignal) void refetch();
  }, [refreshSignal, refetch]);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const markRead = useCallback(
    async (notification: NotificationRead) => {
      if (!notification.read_at) {
        await studioApi.markRead(notification.id);
        void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      }
      if (notification.action_type === "open_project" && notification.project_id) {
        setOpen(false);
        router.push(`/workspace/${notification.project_id}`);
      }
    },
    [queryClient, router],
  );

  const markAll = useCallback(async () => {
    await studioApi.markAllRead();
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }, [queryClient]);

  return (
    <div className="relative" ref={rootRef}>
      <button
        onClick={() => setOpen((value) => !value)}
        className="relative rounded-lg p-2 text-muted-foreground hover:bg-secondary hover:text-foreground"
        aria-label={`Notifications (${unread} unread)`}
      >
        <IconBell className="h-4 w-4" />
        {unread > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 top-10 z-[95] w-80 overflow-hidden rounded-xl border border-border bg-card shadow-xl">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <h3 className="text-sm font-semibold text-foreground">Notifications</h3>
            {unread > 0 ? (
              <button
                onClick={markAll}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                <IconCheck className="h-3 w-3" /> Mark all read
              </button>
            ) : null}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <p className="p-4 text-center text-xs text-muted-foreground">
                No notifications yet. They'll appear here as your book is generated.
              </p>
            ) : (
              items.map((notification) => (
                <button
                  key={notification.id}
                  onClick={() => void markRead(notification)}
                  className={`block w-full border-l-2 px-3 py-2.5 text-left transition-colors hover:bg-secondary/50 ${
                    LEVEL_STYLES[notification.level] ?? LEVEL_STYLES.info
                  } ${notification.read_at ? "opacity-60" : ""}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-medium text-foreground">{notification.title}</p>
                    {!notification.read_at ? (
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                    ) : null}
                  </div>
                  {notification.body ? (
                    <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">
                      {notification.body}
                    </p>
                  ) : null}
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {new Date(notification.created_at).toLocaleTimeString(undefined, {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </button>
              ))
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
