"use client";

// ValidatorPanel — run a KDP requirements validation via a background job.
// Ported from the workspace page (formerly KdpPanel) with friendly error toasts.

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { IconCheck } from "@/components/ui/icons";
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

export function ValidatorPanel({ writingBookId }: PanelProps) {
  const [jobId, setJobId] = useState<string | null>(null);
  const toast = useToast();

  async function run() {
    try {
      const r = await jobsApi.startKdpValidate(writingBookId);
      setJobId(r.id);
    } catch (e) {
      toast(toastError(e));
    }
  }

  return (
    <div className="space-y-2 p-1">
      <p className="text-xs text-muted-foreground">Check your book against KDP requirements.</p>
      <Button size="sm" className="w-full" onClick={() => void run()}>
        <IconCheck className="mr-1 h-3 w-3" /> Run validation
      </Button>
      {jobId && <JobProgressCard jobId={jobId} title="KDP validation" />}
    </div>
  );
}
