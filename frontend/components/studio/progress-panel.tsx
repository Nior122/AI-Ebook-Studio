"use client";

// Floating generation progress panel. Shows overall %, estimated remaining
// time, and the current task/chapter. Minimizable — generation continues in
// the background either way.

import { useEffect, useRef, useState } from "react";
import { jobsApi, type JobResponse } from "@/lib/api/jobs";
import { Spinner } from "@/components/ui/skeleton";
import { IconClose } from "@/components/ui/icons";

interface ProgressPanelProps {
  projectId: string;
  jobId: string | null;
  onDone?: (job: JobResponse) => void;
  onDismiss?: () => void;
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "…";
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

export function ProgressPanel({ jobId, onDone, onDismiss }: ProgressPanelProps) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [minimized, setMinimized] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAtRef = useRef<number | null>(null);
  const doneRef = useRef(false);

  useEffect(() => {
    if (!jobId) return;
    doneRef.current = false;
    setJob(null);
    setMinimized(false);

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const poll = async () => {
      try {
        const current = await jobsApi.get(jobId);
        if (cancelled) return;
        if (!startedAtRef.current) startedAtRef.current = Date.now();
        setJob(current);
        setElapsed((Date.now() - (startedAtRef.current ?? Date.now())) / 1000);
        if (
          current.status === "COMPLETED" ||
          current.status === "FAILED" ||
          current.status === "CANCELLED"
        ) {
          if (!doneRef.current) {
            doneRef.current = true;
            onDone?.(current);
          }
          return;
        }
        timer = setTimeout(poll, 800);
      } catch {
        if (!cancelled) timer = setTimeout(poll, 2500);
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, onDone]);

  if (!jobId || !job) return null;

  const progress = job.progress ?? 0;
  const etaSeconds =
    progress > 3 && job.status === "RUNNING"
      ? (elapsed / progress) * (100 - progress)
      : null;
  const running = job.status === "RUNNING" || job.status === "QUEUED" || job.status === "PENDING";

  if (minimized) {
    return (
      <div className="fixed bottom-4 right-4 z-[90] flex items-center gap-2 rounded-full border border-border bg-card px-3 py-2 shadow-lg">
        <Spinner className="h-3.5 w-3.5" />
        <button
          className="text-xs font-medium text-foreground"
          onClick={() => setMinimized(false)}
        >
          Generating… {progress}%
        </button>
        {onDismiss ? (
          <button onClick={onDismiss} aria-label="Dismiss" className="text-muted-foreground">
            <IconClose className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>
    );
  }

  const terminalLabel =
    job.status === "COMPLETED"
      ? "Completed"
      : job.status === "FAILED"
        ? "Failed"
        : job.status === "CANCELLED"
          ? "Cancelled"
          : null;

  return (
    <div className="fixed bottom-4 right-4 z-[90] w-80 rounded-xl border border-border bg-card p-4 shadow-xl">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-foreground">Generating your book</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {job.current_step ?? "Starting…"}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setMinimized(true)}
            className="rounded p-1 text-xs text-muted-foreground hover:bg-secondary"
            title="Minimize — generation continues in the background"
          >
            —
          </button>
          {onDismiss ? (
            <button
              onClick={onDismiss}
              className="rounded p-1 text-muted-foreground hover:bg-secondary"
              aria-label="Close"
            >
              <IconClose className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
      </div>

      <div className="mt-3 h-2 overflow-hidden rounded-full bg-secondary">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
        <span>{progress}%</span>
        {running ? (
          <span>
            {etaSeconds !== null ? `~${formatDuration(etaSeconds)} left` : "estimating…"}
          </span>
        ) : (
          <span className={job.status === "FAILED" ? "font-medium text-red-600" : "font-medium text-emerald-600"}>
            {terminalLabel}
          </span>
        )}
      </div>

      {job.status === "FAILED" && job.error_message ? (
        <p className="mt-2 rounded-md bg-destructive/10 p-2 text-xs text-foreground">
          {job.error_message}
        </p>
      ) : null}
    </div>
  );
}
