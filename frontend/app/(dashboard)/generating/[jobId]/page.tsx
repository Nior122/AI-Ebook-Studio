"use client";

import { use, useEffect, useState, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { jobsApi, type JobResponse } from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { IconSparkles, IconBook, IconCheck, IconX } from "@/components/ui/icons";

const TIMELINE = [
  { at: 0, label: "Planning manuscript" },
  { at: 5, label: "Analyzing your concept" },
  { at: 8, label: "Generating book brief" },
  { at: 15, label: "Creating chapter blueprint" },
  { at: 24, label: "Writing chapters" },
  { at: 86, label: "Reviewing consistency" },
  { at: 92, label: "Applying layout settings" },
  { at: 94, label: "Running quality checks" },
  { at: 98, label: "Final optimization" },
  { at: 100, label: "Generation complete" },
];

export default function GenerationProgressPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectUrl = searchParams.get("redirect");

  const [job, setJob] = useState<JobResponse | null>(null);
  const [startTime] = useState(Date.now());
  const [minimized, setMinimized] = useState(false);
  const doneRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const j = await jobsApi.get(jobId);
        if (cancelled) return;
        setJob(j);

        if ((j.status === "COMPLETED" || j.status === "FAILED" || j.status === "CANCELLED") && !doneRef.current) {
          doneRef.current = true;
          if (j.status === "COMPLETED" && redirectUrl) {
            setTimeout(() => router.push(redirectUrl), 2000);
          }
          return;
        }
        timer = setTimeout(poll, 1200);
       } catch {
         if (!cancelled) {
           timer = setTimeout(poll, 3000);
         }
      }
    };

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, redirectUrl, router]);

  const pct = Math.max(0, Math.min(100, job?.progress ?? 0));
  const step = job?.current_step ?? "Preparing…";
  const result = job?.result as Record<string, unknown> | null;
  const chapterCount = result?.chapter_count ? Number(result.chapter_count) : 0;
  const totalWords = result?.total_words ? Number(result.total_words) : 0;
  const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
  const eta = pct > 0 ? Math.round((elapsedSec / pct) * (100 - pct)) : null;
  const etaStr = eta ? (eta > 60 ? `${Math.round(eta / 60)} min` : `${eta} sec`) : "calculating…";

  const isTerminal = job?.status === "COMPLETED" || job?.status === "FAILED" || job?.status === "CANCELLED";
  const isDone = job?.status === "COMPLETED";

  const activeStepIndex = Math.max(0, TIMELINE.findLastIndex(t => pct >= t.at));
  const milestone = TIMELINE[activeStepIndex] ?? TIMELINE[0];

  if (minimized) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <button
          onClick={() => setMinimized(false)}
          className="flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3 shadow-lg hover:bg-secondary/50"
        >
          <IconSparkles className="h-4 w-4 text-primary animate-pulse" />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Writing your book</span>
              <Badge variant="outline" className="text-[10px] py-0 h-4">{pct}%</Badge>
            </div>
            <div className="mt-1 h-1 w-32 overflow-hidden rounded-full bg-secondary">
              <div className="h-full bg-primary transition-all duration-500" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl py-12">
      <Card className="border-2 border-border">
        <CardContent className="space-y-6 p-8">
          {/* Header */}
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className={`flex h-14 w-14 items-center justify-center rounded-xl ${
                isDone ? "bg-green-500/10" : job?.status === "FAILED" ? "bg-red-500/10" : "bg-primary/10"
              }`}>
                {isDone ? (
                  <IconBook className="h-7 w-7 text-emerald-600" />
                ) : job?.status === "FAILED" ? (
                  <IconX className="h-7 w-7 text-red-600" />
                ) : (
                  <IconSparkles className="h-7 w-7 text-primary animate-pulse" />
                )}
              </div>
              <div>
                <h1 className="text-2xl font-semibold">
                  {isDone ? "Your book is ready!" : job?.status === "FAILED" ? "Generation failed" : "Writing your book"}
                </h1>
                <p className="text-sm text-muted-foreground">
                  {isDone
                    ? `${chapterCount} chapters, ${totalWords.toLocaleString()} words — redirecting to editor…`
                    : job?.status === "FAILED"
                    ? job.error_message ?? "The AI encountered an error. This is usually temporary."
                    : job?.status === "CANCELLED"
                    ? "Generation was cancelled."
                    : `The AI is writing ${chapterCount > 0 ? `${chapterCount} chapters` : "your chapters"} — this usually takes 2-5 minutes.`}
                </p>
              </div>
            </div>
            {!isTerminal && (
              <button
                onClick={() => setMinimized(true)}
                className="shrink-0 rounded p-1.5 hover:bg-secondary text-muted-foreground hover:text-foreground"
                title="Minimize to corner"
              >
                <div className="h-4 w-4">—</div>
              </button>
            )}
          </div>

          {!isTerminal && (
            <>
              {/* Progress bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{milestone.label}</span>
                  <span className="font-semibold">{pct}%</span>
                </div>
                <div className="h-3 w-full overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full bg-primary transition-all duration-500 ease-out"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{step}</span>
                  <span>{etaStr} remaining</span>
                </div>
              </div>

              {/* Stats */}
              <div className="flex gap-3 text-center text-sm">
                <div className="flex-1 rounded-lg bg-secondary/30 p-3">
                  <p className="text-muted-foreground">Completed</p>
                  <p className="text-lg font-semibold tabular-nums">{pct}%</p>
                </div>
                <div className="flex-1 rounded-lg bg-secondary/30 p-3">
                  <p className="text-muted-foreground">Chapters</p>
                  <p className="text-lg font-semibold tabular-nums">{chapterCount > 0 ? `~${chapterCount}` : "—"}</p>
                </div>
                <div className="flex-1 rounded-lg bg-secondary/30 p-3">
                  <p className="text-muted-foreground">Words</p>
                  <p className="text-lg font-semibold tabular-nums">{totalWords > 0 ? totalWords.toLocaleString() : "—"}</p>
                </div>
                <div className="flex-1 rounded-lg bg-secondary/30 p-3">
                  <p className="text-muted-foreground">Time</p>
                  <p className="text-lg font-semibold tabular-nums">
                    {elapsedSec > 60 ? `${Math.floor(elapsedSec / 60)}m` : `${elapsedSec}s`}
                  </p>
                </div>
              </div>

              {/* Timeline */}
              <div className="space-y-0">
                {TIMELINE.map((milestone, i) => {
                  const done = pct >= milestone.at;
                  const active = i === activeStepIndex;
                  return (
                    <div key={i} className="flex items-center gap-3 py-1">
                      <div className={`flex h-5 w-5 items-center justify-center rounded-full text-xs ${
                        done ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"
                      }`}>
                        {done ? <IconCheck className="h-3 w-3" /> : <span>{i + 1}</span>}
                      </div>
                      <span className={`text-xs ${done ? "text-foreground font-medium" : "text-muted-foreground"} ${active ? "underline" : ""}`}>
                        {milestone.label}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className="text-center">
                <p className="text-xs text-muted-foreground">
                  Elapsed: {elapsedSec > 60 ? `${Math.floor(elapsedSec / 60)}m ${elapsedSec % 60}s` : `${elapsedSec}s`}
                </p>
              </div>
            </>
          )}

          {isDone && (
            <Button className="w-full" size="lg" onClick={() => redirectUrl && router.push(redirectUrl)}>
              <IconBook className="mr-2 h-5 w-5" />
              Open Your Book ({chapterCount} chapters, {totalWords.toLocaleString()} words)
            </Button>
          )}

          {job?.status === "FAILED" && (
            <div className="space-y-3">
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:bg-red-950/20 dark:border-red-800">
                <p className="text-sm text-red-700 dark:text-red-300 font-medium">What happened:</p>
                <p className="text-sm text-red-600 dark:text-red-400 mt-1">
                  {job.error_message ?? "The AI couldn't complete this chapter. This is usually a temporary issue — the AI provider may be busy."}
                </p>
              </div>
              <div className="flex gap-3">
                <Button variant="outline" onClick={() => router.push("/new-book")}>Start over</Button>
                <Button onClick={() => window.location.reload()}>Try again</Button>
              </div>
            </div>
          )}

          {job?.status === "CANCELLED" && (
            <div className="text-center">
              <p className="text-sm text-muted-foreground">Generation was cancelled.</p>
              <Button className="mt-3" variant="outline" onClick={() => router.push("/new-book")}>Start a new book</Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}