"use client";

// CoverPanel — generate a professional book cover via a background job.
// Ported from the workspace page with friendly error toasts.

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { IconCover } from "@/components/ui/icons";
import { jobsApi } from "@/lib/api/jobs";
import { JobProgressCard } from "@/components/shared/job-progress-card";
import { toastError } from "@/lib/errors";

interface PanelProps {
  projectId: string;
  writingBookId: string;
  activeChapterId: string | null;
  onApplyEdit?: (content: string) => void;
  onInsertImage?: (markdown: string) => void;
}

export function CoverPanel({ writingBookId }: PanelProps) {
  const [jobId, setJobId] = useState<string | null>(null);
  const toast = useToast();

  async function generate() {
    try {
      const r = await jobsApi.startCover(writingBookId);
      setJobId(r.id);
    } catch (e) {
      toast(toastError(e));
    }
  }

  return (
    <div className="space-y-2 p-1">
      <p className="text-xs text-muted-foreground">
        Generate a professional cover from your book's title and content.
      </p>
      <Button size="sm" className="w-full" onClick={() => void generate()}>
        <IconCover className="mr-1 h-3 w-3" /> Generate cover
      </Button>
      {jobId && <JobProgressCard jobId={jobId} title="Cover generation" />}
    </div>
  );
}
