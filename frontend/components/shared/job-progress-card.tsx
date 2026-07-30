"use client";

// JobProgressCard — polls a job's status and shows progress.
// Used for long-running operations: exports, KDP validation, cover generation,
// marketing generation, translation. Falls back gracefully when no job is running.

import { useEffect, useRef, useState } from "react";
import { jobsApi, type JobResponse } from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/skeleton";

interface JobProgressCardProps {
  jobId: string | null;
  title: string;
  onComplete?: (job: JobResponse) => void;
  onCancel?: () => void;
}

const STATUS_LABELS: Record<JobResponse["status"], string> = {
  PENDING: "Pending",
  QUEUED: "Queued",
  RUNNING: "Running",
  COMPLETED: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

const STATUS_COLORS: Record<JobResponse["status"], string> = {
  PENDING: "bg-muted text-muted-foreground",
  QUEUED: "bg-muted text-muted-foreground",
  RUNNING: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
  COMPLETED: "bg-green-500/10 text-green-700 dark:text-green-300",
  FAILED: "bg-red-500/10 text-red-700 dark:text-red-300",
  CANCELLED: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
};

export function JobProgressCard({ jobId, title, onComplete, onCancel }: JobProgressCardProps) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const completedRef = useRef(false);

  useEffect(() => {
    if (!jobId) return;
    completedRef.current = false;
    setError(null);

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const j = await jobsApi.get(jobId);
        if (cancelled) return;
        setJob(j);
        const terminal = j.status === "COMPLETED" || j.status === "FAILED" || j.status === "CANCELLED";
        if (terminal && !completedRef.current) {
          completedRef.current = true;
          onComplete?.(j);
          return;
        }
        timer = setTimeout(poll, 800);
      } catch (err: unknown) {
        if (!cancelled) {
          setError((err as Error).message || "Failed to fetch job status.");
          timer = setTimeout(poll, 2500);
        }
      }
    };

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, onComplete]);

  if (!jobId) return null;

  if (error && !job) {
    return (
      <Card>
        <CardContent className="p-5">
          <p className="text-sm text-red-600">Error tracking job: {error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!job) {
    return (
      <Card>
        <CardContent className="flex items-center gap-3 p-5">
          <Spinner label={`${title} — starting…`} />
        </CardContent>
      </Card>
    );
  }

  const pct = Math.max(0, Math.min(100, job.progress ?? 0));
  const statusLabel = STATUS_LABELS[job.status] ?? job.status;
  const statusColor = STATUS_COLORS[job.status] ?? "bg-muted text-muted-foreground";

  return (
    <Card>
      <CardContent className="space-y-3 p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold">{title}</h3>
            <p className="text-xs text-muted-foreground">{job.job_type}</p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusColor}`}>
            {statusLabel}
          </span>
        </div>
        {job.status === "RUNNING" || job.status === "QUEUED" || job.status === "PENDING" ? (
          <>
            <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full bg-foreground transition-all duration-300"
                style={{ width: `${pct}%` }}
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{job.current_step ?? "Working…"}</span>
              <span className="font-medium">{pct}%</span>
            </div>
            {onCancel && (
              <div className="flex justify-end">
                <Button variant="outline" size="sm" onClick={onCancel}>
                  Cancel
                </Button>
              </div>
            )}
          </>
        ) : null}
        {job.status === "COMPLETED" ? (
          <p className="text-sm text-green-700 dark:text-green-300">Done.</p>
        ) : null}
        {job.status === "FAILED" ? (
          <p className="text-sm text-red-600 dark:text-red-400">
            {job.error_message ?? "The job failed."}
          </p>
        ) : null}
        {job.status === "CANCELLED" ? (
          <p className="text-sm text-amber-700 dark:text-amber-300">Cancelled.</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
