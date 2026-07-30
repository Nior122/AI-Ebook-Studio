"use client";

// Export module — generate DOCX/PDF/EPUB from the project's writing book.
// Live progress is tracked via the background job system (POST /async... returns
// a job id; we poll GET /jobs/{id} until completion).

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { booksApi } from "@/lib/api/books";
import { bookWritingApi } from "@/lib/api/bookWriting";
import { jobsApi, type JobResponse } from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { IconExport, IconBook } from "@/components/ui/icons";
import { ErrorState } from "@/components/states/states";
import { JobProgressCard } from "@/components/shared/job-progress-card";

export default function ExportsModulePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [includeFrontMatter, setIncludeFrontMatter] = useState(true);
  const [includeToc, setIncludeToc] = useState(true);
  const [includeBackMatter, setIncludeBackMatter] = useState(false);
  const [activeJob, setActiveJob] = useState<{ id: string; format: string } | null>(null);

  const { data: books, isLoading: booksLoading } = useQuery({
    queryKey: ["books", projectId],
    queryFn: () => booksApi.listForProject(projectId),
  });

  const primaryBook = books?.[0];
  const writingBookId = primaryBook?.metadata_json?.writing_book_id;

  const { data: formats } = useQuery({
    queryKey: ["export-formats", writingBookId],
    queryFn: () => bookWritingApi.listExportFormats(writingBookId!),
    enabled: !!writingBookId,
  });

  const { data: exportsData, isLoading: exportsLoading } = useQuery({
    queryKey: ["exports", writingBookId],
    queryFn: () => bookWritingApi.listExports(writingBookId!),
    enabled: !!writingBookId,
  });

  const generateMutation = useMutation({
    mutationFn: async (format: string) => {
      if (!writingBookId) throw new Error("Missing book id");
      const job = await jobsApi.startExport(writingBookId, format as "docx" | "pdf" | "epub");
      setActiveJob({ id: job.id, format });
      return job;
    },
    onError: (err: Error) => {
      toast({ title: "Export failed", description: err.message, variant: "error" });
    },
  });

  const cancelJob = async () => {
    if (!activeJob) return;
    try {
      await jobsApi.cancel(activeJob.id);
    } catch {
      /* nothing */
    }
    setActiveJob(null);
  };

  const onJobComplete = async (job: JobResponse) => {
    setActiveJob(null);
    if (job.status === "COMPLETED") {
      toast({ title: `${activeJob?.format?.toUpperCase() ?? "Export"} generated`, variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["exports", writingBookId] });
    } else if (job.status === "FAILED") {
      toast({ title: "Export failed", description: job.error_message ?? undefined, variant: "error" });
    }
  };

  const deleteMutation = useMutation({
    mutationFn: (assetId: string) => bookWritingApi.deleteExport(writingBookId!, assetId),
    onSuccess: () => {
      toast({ title: "Export deleted", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["exports", writingBookId] });
    },
  });

  if (booksLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner label="Loading…" />
      </div>
    );
  }

  if (!primaryBook) {
    return (
      <ErrorState
        title="No book in this project"
        message="Create a project with a book first to enable exports."
      />
    );
  }

  if (!writingBookId) {
    return (
      <ErrorState
        title="Book engine link missing"
        message="This project doesn't have a linked writer. Create a new project to enable exports."
      />
    );
  }

  const exports = exportsData?.items ?? [];

  function handleDownload(itemId: string) {
    const url = bookWritingApi.getExportDownloadUrl(writingBookId!, itemId);
    window.open(url, "_blank");
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Export</h2>
        <p className="text-sm text-muted-foreground">
          Generate DOCX, PDF, and EPUB files from your book content. Each export uses the latest approved chapters and your formatting settings.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Options</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="flex items-center gap-2">
            <Checkbox checked={includeFrontMatter} onChange={(e) => setIncludeFrontMatter(e.target.checked)} />
            <span className="text-sm">Include front matter (title page)</span>
          </label>
          <label className="flex items-center gap-2">
            <Checkbox checked={includeToc} onChange={(e) => setIncludeToc(e.target.checked)} />
            <span className="text-sm">Include table of contents</span>
          </label>
          <label className="flex items-center gap-2">
            <Checkbox checked={includeBackMatter} onChange={(e) => setIncludeBackMatter(e.target.checked)} />
            <span className="text-sm">Include back matter (about the author)</span>
          </label>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-3">
        {(formats ?? []).map((format) => (
          <Card key={format.format} className="flex flex-col">
            <CardContent className="flex flex-1 flex-col gap-3 p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-foreground">
                  <IconBook className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-base font-semibold tracking-tight">{format.label}</h3>
                  <Badge variant="muted">{format.extension.toUpperCase()}</Badge>
                </div>
              </div>
              <p className="flex-1 text-sm text-muted-foreground">{format.description}</p>
              <Button
                onClick={() => generateMutation.mutate(format.format)}
                disabled={generateMutation.isPending || !!activeJob}
              >
                {generateMutation.isPending && generateMutation.variables === format.format ? (
                  <Spinner label="Starting" />
                ) : (
                  <>
                    <IconExport className="h-4 w-4" />
                    Generate {format.extension.toUpperCase()}
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {activeJob && (
        <JobProgressCard
          jobId={activeJob.id}
          title={`${activeJob.format.toUpperCase()} export`}
          onComplete={onJobComplete}
          onCancel={cancelJob}
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle>Generated files</CardTitle>
        </CardHeader>
        <CardContent>
          {exportsLoading ? (
            <Spinner label="Loading exports…" />
          ) : exports.length === 0 ? (
            <p className="text-sm text-muted-foreground">No exports yet. Generate a file using one of the options above.</p>
          ) : (
            <div className="space-y-2">
              {exports.map((item) => (
                <div key={item.id} className="flex items-center justify-between rounded-lg border border-border bg-card p-3">
                  <div className="flex items-center gap-3">
                    <IconBook className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">{item.file_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {item.asset_type} · v{item.version} ·{" "}
                        {new Date(item.created_at).toLocaleString()}
                        {item.file_size ? ` · ${(item.file_size / 1024).toFixed(1)} KB` : ""}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => handleDownload(item.id)}>
                      <IconExport className="h-4 w-4" />
                      Download
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => deleteMutation.mutate(item.id)}
                      disabled={deleteMutation.isPending}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
