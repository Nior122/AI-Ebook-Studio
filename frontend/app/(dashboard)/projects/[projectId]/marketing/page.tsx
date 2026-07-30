"use client";

// Marketing module — generates Amazon descriptions, keywords, social posts, etc.
// Uses the background-job system for live progress tracking.

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { booksApi } from "@/lib/api/books";
import { bookWritingApi } from "@/lib/api/bookWriting";
import { jobsApi, type JobResponse } from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { IconMarketing } from "@/components/ui/icons";
import { ErrorState } from "@/components/states/states";
import { JobProgressCard } from "@/components/shared/job-progress-card";

export default function MarketingModulePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [activeJob, setActiveJob] = useState<{ id: string; assetType: string; label: string } | null>(null);

  const { data: books, isLoading } = useQuery({
    queryKey: ["books", projectId], queryFn: () => booksApi.listForProject(projectId),
  });
  const writingBookId = books?.[0]?.metadata_json?.writing_book_id;

  const { data: types } = useQuery({
    queryKey: ["marketing-types", writingBookId],
    queryFn: () => bookWritingApi.listMarketingTypes(writingBookId!),
    enabled: !!writingBookId,
  });

  const { data: assetsData } = useQuery({
    queryKey: ["marketing", writingBookId],
    queryFn: () => bookWritingApi.listMarketing(writingBookId!),
    enabled: !!writingBookId,
  });

  const generateMutation = useMutation({
    mutationFn: async (info: { typeId: string; label: string }) => {
      if (!writingBookId) throw new Error("Missing book id");
      const job = await jobsApi.startMarketing(writingBookId, info.typeId);
      setActiveJob({ id: job.id, assetType: info.typeId, label: info.label });
      return job;
    },
    onError: (err: Error) => toast({ title: "Generation failed", description: err.message, variant: "error" }),
  });

  const onJobComplete = async (job: JobResponse) => {
    setActiveJob(null);
    if (job.status === "COMPLETED") {
      toast({ title: "Marketing asset generated", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["marketing", writingBookId] });
    } else if (job.status === "FAILED") {
      toast({ title: "Generation failed", description: job.error_message ?? undefined, variant: "error" });
    }
  };

  const cancelJob = async () => {
    if (!activeJob) return;
    try { await jobsApi.cancel(activeJob.id); } catch { /* */ }
    setActiveJob(null);
  };

  const deleteMutation = useMutation({
    mutationFn: (assetId: string) => bookWritingApi.deleteMarketing(writingBookId!, assetId),
    onSuccess: () => {
      toast({ title: "Asset deleted", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["marketing", writingBookId] });
    },
  });

  if (isLoading) return <div className="flex justify-center py-12"><Spinner label="Loading…" /></div>;
  if (!writingBookId) {
    return <ErrorState title="Book engine link missing" message="Create a new project to enable marketing." />;
  }

  const assets = assetsData?.items ?? [];
  function findAsset(typeId: string) {
    return assets.find((a: { asset_type: string }) => a.asset_type === typeId);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Marketing</h2>
        <p className="text-sm text-muted-foreground">
          AI-generated marketing assets: Amazon descriptions, keywords, social posts, and email launch campaigns. Generate any type below.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {(types ?? []).map((t: { type_id: string; label: string; description: string }) => {
          const asset = findAsset(t.type_id);
          return (
            <Card key={t.type_id} className="flex flex-col">
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2">
                    <IconMarketing className="h-4 w-4" />
                    {t.label}
                  </span>
                  {asset ? <Badge variant="success">Generated</Badge> : null}
                </CardTitle>
                <p className="text-xs text-muted-foreground">{t.description}</p>
              </CardHeader>
              <CardContent className="flex-1 space-y-3">
                <Button
                  onClick={() => generateMutation.mutate({ typeId: t.type_id, label: t.label })}
                  disabled={generateMutation.isPending || !!activeJob}
                  size="sm"
                  variant={asset ? "outline" : "default"}
                >
                  {generateMutation.isPending && generateMutation.variables?.typeId === t.type_id ? (
                    <Spinner label="Starting…" />
                  ) : asset ? (
                    "Regenerate"
                  ) : (
                    "Generate"
                  )}
                </Button>
                {asset ? (
                  <div className="rounded-lg border border-border bg-secondary/30 p-3">
                    <pre className="whitespace-pre-wrap text-sm">{asset.content}</pre>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={() => deleteMutation.mutate(asset.id)}
                      disabled={deleteMutation.isPending}
                    >
                      Delete
                    </Button>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {activeJob && (
        <JobProgressCard
          jobId={activeJob.id}
          title={`Generating ${activeJob.label}`}
          onComplete={onJobComplete}
          onCancel={cancelJob}
        />
      )}
    </div>
  );
}
