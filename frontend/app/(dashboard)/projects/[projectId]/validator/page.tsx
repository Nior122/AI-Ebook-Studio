"use client";

// KDP Validator — runs compliance checks on the book's content and formatting.
// Uses the background-job system so the user can see live progress.

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { booksApi } from "@/lib/api/books";
import { bookWritingApi } from "@/lib/api/bookWriting";
import { jobsApi, type JobResponse } from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { IconLayout, IconCheck, IconAlert } from "@/components/ui/icons";
import { ErrorState } from "@/components/states/states";
import { JobProgressCard } from "@/components/shared/job-progress-card";

interface CheckItem { check: string; message: string; recommendation?: string }

export default function ValidatorModulePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [report, setReport] = useState<unknown>(null);
  const [activeJob, setActiveJob] = useState<string | null>(null);

  const { data: books, isLoading } = useQuery({
    queryKey: ["books", projectId], queryFn: () => booksApi.listForProject(projectId),
  });
  const writingBookId = books?.[0]?.metadata_json?.writing_book_id;

  const validateMutation = useMutation({
    mutationFn: async () => {
      if (!writingBookId) throw new Error("Missing book id");
      const job = await jobsApi.startKdpValidate(writingBookId);
      setActiveJob(job.id);
      return job;
    },
    onError: (err: Error) => toast({ title: "Validation failed", description: err.message, variant: "error" }),
  });

  const onJobComplete = async (job: JobResponse) => {
    setActiveJob(null);
    if (job.status === "COMPLETED") {
      toast({ title: "Validation complete", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["kdp-report", writingBookId] });
      try {
        const data = await bookWritingApi.getKDPReport(writingBookId!);
        setReport(data);
      } catch {
        /* ignore */
      }
    } else if (job.status === "FAILED") {
      toast({ title: "Validation failed", description: job.error_message ?? undefined, variant: "error" });
    }
  };

  const cancelJob = async () => {
    if (!activeJob) return;
    try { await jobsApi.cancel(activeJob); } catch { /* */ }
    setActiveJob(null);
  };

  const { data: latestReport } = useQuery({
    queryKey: ["kdp-report", writingBookId],
    queryFn: () => bookWritingApi.getKDPReport(writingBookId!),
    enabled: !!writingBookId && !report,
  });

  if (isLoading) return <div className="flex justify-center py-12"><Spinner label="Loading…" /></div>;
  if (!writingBookId) {
    return <ErrorState title="Book engine link missing" message="Create a new project to enable validation." />;
  }

  const currentReport = report ?? latestReport;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">KDP Validation</h2>
        <p className="text-sm text-muted-foreground">
          Runs KDP compliance checks on your book: margins, fonts, image sizing, page size, chapter numbering, content structure. Generates a pass/fail report with actionable fix recommendations.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <IconLayout className="h-5 w-5" />
            Run validation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Button
            onClick={() => validateMutation.mutate()}
            disabled={validateMutation.isPending || !!activeJob}
          >
            {validateMutation.isPending ? <Spinner label="Starting…" /> : "Run KDP Check"}
          </Button>
        </CardContent>
      </Card>

      {activeJob && (
        <JobProgressCard
          jobId={activeJob}
          title="KDP validation"
          onComplete={onJobComplete}
          onCancel={cancelJob}
        />
      )}

      {currentReport ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Validation Report</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center gap-3">
                <Badge
                  variant={currentReport.status === "PASSED" ? "success" : currentReport.status === "FAILED" ? "destructive" : "warning"}
                >
                  {currentReport.status}
                </Badge>
                <span className="text-2xl font-semibold">{currentReport.score}/100</span>
                <span className="text-sm text-muted-foreground">compliance score</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Ran {new Date(currentReport.created_at).toLocaleString()}
              </p>
            </CardContent>
          </Card>

          {currentReport.issues?.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-destructive">Issues ({currentReport.issues.length})</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {currentReport.issues.map((item: CheckItem, idx: number) => (
                  <div key={idx} className="rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                    <div className="flex items-start gap-2">
                      <IconAlert className="mt-0.5 h-4 w-4 flex-shrink-0 text-destructive" />
                      <div>
                        <Badge variant="destructive" className="mb-1">{item.check}</Badge>
                        <p className="text-sm font-medium">{item.message}</p>
                        {item.recommendation && (
                          <p className="mt-1 text-sm text-muted-foreground">Fix: {item.recommendation}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {currentReport.warnings?.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-amber-600">Warnings ({currentReport.warnings.length})</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {currentReport.warnings.map((item: CheckItem, idx: number) => (
                  <div key={idx} className="rounded-lg border border-amber-300 bg-amber-50 p-3">
                    <Badge variant="warning" className="mb-1">{item.check}</Badge>
                    <p className="text-sm font-medium">{item.message}</p>
                    {item.recommendation && (
                      <p className="mt-1 text-sm text-muted-foreground">Suggestion: {item.recommendation}</p>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {currentReport.passed_checks?.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-emerald-600">Passed ({currentReport.passed_checks.length})</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {currentReport.passed_checks.map((item: CheckItem, idx: number) => (
                  <div key={idx} className="flex items-center gap-2 text-sm">
                    <IconCheck className="h-4 w-4 text-emerald-600" />
                    <Badge variant="success">{item.check}</Badge>
                    <span>{item.message}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      ) : null}
    </div>
  );
}
