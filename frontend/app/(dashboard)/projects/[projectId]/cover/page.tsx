"use client";

// Cover module — generates front/back/spine cover designs via AI.
// Uses the background-job system for live progress tracking.

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { booksApi } from "@/lib/api/books";
import { bookWritingApi } from "@/lib/api/bookWriting";
import { jobsApi, type JobResponse } from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { IconCover } from "@/components/ui/icons";
import { ErrorState } from "@/components/states/states";
import { JobProgressCard } from "@/components/shared/job-progress-card";

type Tab = "front" | "back" | "spine";

export default function CoverModulePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("front");
  const [result, setResult] = useState<{ front?: string; back?: string; spine?: string }>({});
  const [activeJob, setActiveJob] = useState<{ id: string; component: string } | null>(null);

  const { data: books, isLoading } = useQuery({
    queryKey: ["books", projectId], queryFn: () => booksApi.listForProject(projectId),
  });
  const writingBookId = books?.[0]?.metadata_json?.writing_book_id;

  if (isLoading) return <div className="flex justify-center py-12"><Spinner label="Loading…" /></div>;
  if (!writingBookId) {
    return <ErrorState title="Book engine link missing" message="Create a new project to enable cover generation." />;
  }

  const mutation = useMutation({
    mutationFn: async (kind: Tab) => {
      const job = await jobsApi.startCover(writingBookId, kind);
      setActiveJob({ id: job.id, component: kind });
      return job;
    },
    onError: (err: Error) => toast({ title: "Generation failed", description: err.message, variant: "error" }),
  });

  const allMutation = useMutation({
    mutationFn: async () => {
      const job = await jobsApi.startCover(writingBookId, "all");
      setActiveJob({ id: job.id, component: "all" });
      return job;
    },
    onError: (err: Error) => toast({ title: "Generation failed", description: err.message, variant: "error" }),
  });

  const onJobComplete = async (job: JobResponse) => {
    setActiveJob(null);
    if (job.status === "COMPLETED") {
      toast({ title: "Cover generated", variant: "success" });
      const component = job.result?.component ?? null;
      if (component === "all") {
        try {
          const f = await bookWritingApi.generateFrontCover(writingBookId);
          const b = await bookWritingApi.generateBackCover(writingBookId);
          const s = await bookWritingApi.generateSpine(writingBookId);
          setResult({ front: f.content, back: b.content, spine: s.content });
        } catch {
          /* fallback if sync API not available */
        }
      }
    } else if (job.status === "FAILED") {
      toast({ title: "Generation failed", description: job.error_message ?? undefined, variant: "error" });
    }
  };

  const cancelJob = async () => {
    if (!activeJob) return;
    try { await jobsApi.cancel(activeJob.id); } catch { /* */ }
    setActiveJob(null);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Cover Design</h2>
        <p className="text-sm text-muted-foreground">
          AI-generated design briefs for front cover, back cover, and spine. Use these prompts as a hand-off to a designer or AI image generator.
        </p>
      </div>

      <div className="flex gap-2">
        <Button variant={tab === "front" ? "default" : "outline"} onClick={() => setTab("front")}>Front Cover</Button>
        <Button variant={tab === "back" ? "default" : "outline"} onClick={() => setTab("back")}>Back Cover</Button>
        <Button variant={tab === "spine" ? "default" : "outline"} onClick={() => setTab("spine")}>Spine</Button>
        <div className="flex-1" />
        <Button variant="secondary" onClick={() => allMutation.mutate()} disabled={allMutation.isPending || !!activeJob}>
          {allMutation.isPending ? <Spinner label="Starting…" /> : "Generate All"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <IconCover className="h-5 w-5" />
            {tab === "front" ? "Front Cover" : tab === "back" ? "Back Cover" : "Spine"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button onClick={() => mutation.mutate(tab)} disabled={mutation.isPending || !!activeJob}>
            {mutation.isPending ? <Spinner label="Starting…" /> : `Generate ${tab} cover`}
          </Button>
          {result[tab] ? (
            <div className="rounded-lg border border-border bg-secondary/30 p-4">
              <p className="mb-2"><Badge>Generated brief</Badge></p>
              <pre className="whitespace-pre-wrap text-sm">{result[tab]}</pre>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {activeJob && (
        <JobProgressCard
          jobId={activeJob.id}
          title={activeJob.component === "all" ? "Generating full cover" : `Generating ${activeJob.component} cover`}
          onComplete={onJobComplete}
          onCancel={cancelJob}
        />
      )}

      {result.front || result.back || result.spine ? (
        <Card>
          <CardHeader><CardTitle>All generated components</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {result.front ? (
              <div>
                <h4 className="mb-1 text-sm font-semibold">Front</h4>
                <pre className="whitespace-pre-wrap rounded bg-secondary/30 p-3 text-sm">{result.front}</pre>
              </div>
            ) : null}
            {result.back ? (
              <div>
                <h4 className="mb-1 text-sm font-semibold">Back</h4>
                <pre className="whitespace-pre-wrap rounded bg-secondary/30 p-3 text-sm">{result.back}</pre>
              </div>
            ) : null}
            {result.spine ? (
              <div>
                <h4 className="mb-1 text-sm font-semibold">Spine</h4>
                <pre className="whitespace-pre-wrap rounded bg-secondary/30 p-3 text-sm">{result.spine}</pre>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
