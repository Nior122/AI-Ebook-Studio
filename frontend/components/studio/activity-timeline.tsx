"use client";

// Live activity timeline — every meaningful event in the project, newest first.
// Example: "09:14 Chapter 2 generated — Core Principles".

import { useQuery } from "@tanstack/react-query";
import { studioApi, type ActivityRead } from "@/lib/api/studio";
import { Spinner } from "@/components/ui/skeleton";

const KIND_ICONS: Record<string, string> = {
  outline_created: "📋",
  chapter_generated: "✍️",
  image_generated: "🖼️",
  formatting_complete: "📐",
  validation_complete: "✅",
  generation_complete: "🎉",
  version_created: "💾",
  version_restored: "↩️",
  stage_changed: "🏷️",
  job_completed: "✅",
  bookmark_added: "🔖",
};

function timeLabel(value: string): string {
  try {
    return new Date(value).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function ActivityTimeline({ projectId, refreshSignal }: { projectId: string; refreshSignal?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["activities", projectId, refreshSignal ?? 0],
    queryFn: () => studioApi.listActivities(projectId, 60),
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return (
      <div className="flex justify-center p-4">
        <Spinner label="Loading activity…" />
      </div>
    );
  }

  const activities: ActivityRead[] = data ?? [];
  if (activities.length === 0) {
    return (
      <p className="p-3 text-xs text-muted-foreground">
        No activity yet — events will appear here as you work on the book.
      </p>
    );
  }

  return (
    <ol className="space-y-2 p-2">
      {activities.map((activity) => (
        <li key={activity.id} className="flex items-start gap-2 text-xs">
          <span className="mt-0.5 shrink-0 text-sm">
            {KIND_ICONS[activity.kind] ?? "•"}
          </span>
          <div className="min-w-0">
            <p className="leading-snug text-foreground">{activity.message}</p>
            <p className="text-[10px] text-muted-foreground">{timeLabel(activity.created_at)}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
