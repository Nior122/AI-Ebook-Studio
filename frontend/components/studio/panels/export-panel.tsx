"use client";

// ExportPanel — export the book to DOCX / PDF / EPUB via a background job.
// Ported from the workspace page with friendly error toasts.

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { IconExport } from "@/components/ui/icons";
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

const FORMATS = ["docx", "pdf", "epub"] as const;
type ExportFormat = (typeof FORMATS)[number];

export function ExportPanel({ writingBookId }: PanelProps) {
  const [fmt, setFmt] = useState<ExportFormat>("docx");
  const [jobId, setJobId] = useState<string | null>(null);
  const toast = useToast();

  async function start() {
    try {
      const r = await jobsApi.startExport(writingBookId, fmt);
      setJobId(r.id);
    } catch (e) {
      toast(toastError(e));
    }
  }

  return (
    <div className="space-y-2 p-1">
      <p className="text-xs text-muted-foreground">Export the book to a shareable file.</p>
      <div className="flex gap-1">
        {FORMATS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFmt(f)}
            className={`flex-1 rounded px-2 py-1 text-[10px] font-medium ${
              fmt === f ? "bg-primary text-primary-foreground" : "bg-secondary"
            }`}
          >
            .{f.toUpperCase()}
          </button>
        ))}
      </div>
      <Button size="sm" className="w-full" onClick={() => void start()}>
        <IconExport className="mr-1 h-3 w-3" /> Export {fmt.toUpperCase()}
      </Button>
      {jobId && <JobProgressCard jobId={jobId} title={`${fmt.toUpperCase()} export`} />}
    </div>
  );
}
