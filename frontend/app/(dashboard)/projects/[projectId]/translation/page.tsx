"use client";

// Translation module — translates the entire book to a target language.

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { booksApi } from "@/lib/api/books";
import { bookWritingApi } from "@/lib/api/bookWriting";
import { jobsApi, type JobResponse } from "@/lib/api/jobs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { IconTranslate } from "@/components/ui/icons";
import { ErrorState } from "@/components/states/states";
import { JobProgressCard } from "@/components/shared/job-progress-card";

export default function TranslationModulePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [sourceLang, setSourceLang] = useState("en");
  const [targetLang, setTargetLang] = useState("es");
  const [activeJob, setActiveJob] = useState<string | null>(null);

  const { data: books, isLoading } = useQuery({
    queryKey: ["books", projectId], queryFn: () => booksApi.listForProject(projectId),
  });
  const writingBookId = books?.[0]?.metadata_json?.writing_book_id;

  const { data: languages } = useQuery({
    queryKey: ["translate-languages", writingBookId],
    queryFn: () => bookWritingApi.listTranslateLanguages(writingBookId!),
    enabled: !!writingBookId,
  });

  const { data: history } = useQuery({
    queryKey: ["translate-history", writingBookId],
    queryFn: () => bookWritingApi.listTranslations(writingBookId!),
    enabled: !!writingBookId,
  });

  const translateMutation = useMutation({
    mutationFn: async () => {
      if (!writingBookId) throw new Error("Missing book id");
      const job = await jobsApi.startTranslation(writingBookId, sourceLang, targetLang);
      setActiveJob(job.id);
      return job;
    },
    onError: (err: Error) => toast({ title: "Translation failed", description: err.message, variant: "error" }),
  });

  const onJobComplete = async (job: JobResponse) => {
    setActiveJob(null);
    if (job.status === "COMPLETED") {
      toast({ title: "Translation complete", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["translate-history", writingBookId] });
      queryClient.invalidateQueries({ queryKey: ["chapters", writingBookId] });
    } else if (job.status === "FAILED") {
      toast({ title: "Translation failed", description: job.error_message ?? undefined, variant: "error" });
    }
  };

  const cancelJob = async () => {
    if (!activeJob) return;
    try { await jobsApi.cancel(activeJob); } catch { /* */ }
    setActiveJob(null);
  };

  if (isLoading) return <div className="flex justify-center py-12"><Spinner label="Loading…" /></div>;
  if (!writingBookId) {
    return <ErrorState title="Book engine link missing" message="Create a new project to enable translation." />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Translation</h2>
        <p className="text-sm text-muted-foreground">
          Translates every chapter while preserving markdown formatting (headings, bold/italic, lists) and image placeholders. The translated text becomes the current chapter content.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <IconTranslate className="h-5 w-5" />
            Translate this book
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium">Source language</label>
              <Select value={sourceLang} onChange={(e) => setSourceLang(e.target.value)}>
                {(languages ?? []).map((l: { code: string; name: string }) => (
                  <option key={l.code} value={l.code}>{l.name}</option>
                ))}
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Target language</label>
              <Select value={targetLang} onChange={(e) => setTargetLang(e.target.value)}>
                {(languages ?? []).map((l: { code: string; name: string }) => (
                  <option key={l.code} value={l.code}>{l.name}</option>
                ))}
              </Select>
            </div>
          </div>
          <Button
            onClick={() => translateMutation.mutate()}
            disabled={translateMutation.isPending || sourceLang === targetLang || !!activeJob}
          >
            {translateMutation.isPending ? <Spinner label="Starting…" /> : `Translate to ${targetLang.toUpperCase()}`}
          </Button>
          {sourceLang === targetLang ? (
            <p className="text-sm text-muted-foreground">Source and target languages must differ.</p>
          ) : null}
        </CardContent>
      </Card>

      {activeJob && (
        <JobProgressCard
          jobId={activeJob}
          title={`Translating to ${targetLang.toUpperCase()}`}
          onComplete={onJobComplete}
          onCancel={cancelJob}
        />
      )}

      <Card>
        <CardHeader><CardTitle>History</CardTitle></CardHeader>
        <CardContent>
          {history?.items?.length ? (
            <div className="space-y-2">
              {history.items.map((rec: { id: string; source_language: string; target_language: string; created_at: string; status: string }) => (
                <div key={rec.id} className="flex items-center justify-between rounded-lg border border-border p-3">
                  <div>
                    <p className="text-sm font-medium">
                      {rec.source_language.toUpperCase()} → {rec.target_language.toUpperCase()}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(rec.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Badge variant={rec.status === "COMPLETED" ? "success" : rec.status === "FAILED" ? "destructive" : "muted"}>
                    {rec.status}
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No translations yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
