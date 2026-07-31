"use client";

// TranslationPanel — translate the book from a source language into a target
// language via a background job. Ported from the workspace page, extended
// with a source-language select (default "en") and friendly error toasts.

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { IconTranslate } from "@/components/ui/icons";
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

const LANGS = [
  { code: "en", name: "English" },
  { code: "es", name: "Spanish" },
  { code: "fr", name: "French" },
  { code: "de", name: "German" },
  { code: "pt", name: "Portuguese" },
  { code: "it", name: "Italian" },
  { code: "ja", name: "Japanese" },
  { code: "zh", name: "Chinese" },
  { code: "ar", name: "Arabic" },
  { code: "ru", name: "Russian" },
  { code: "ko", name: "Korean" },
  { code: "nl", name: "Dutch" },
];

export function TranslationPanel({ writingBookId }: PanelProps) {
  const [source, setSource] = useState("en");
  const [target, setTarget] = useState("es");
  const [jobId, setJobId] = useState<string | null>(null);
  const toast = useToast();

  async function start() {
    try {
      const r = await jobsApi.startTranslation(writingBookId, source, target);
      setJobId(r.id);
    } catch (e) {
      toast(toastError(e));
    }
  }

  return (
    <div className="space-y-2 p-1">
      <div className="space-y-1">
        <label className="text-[10px] font-medium text-muted-foreground" htmlFor="translate-source">
          From
        </label>
        <select
          id="translate-source"
          className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        >
          {LANGS.map((l) => (
            <option key={l.code} value={l.code}>
              {l.name}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-1">
        <label className="text-[10px] font-medium text-muted-foreground" htmlFor="translate-target">
          To
        </label>
        <select
          id="translate-target"
          className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        >
          {LANGS.map((l) => (
            <option key={l.code} value={l.code}>
              {l.name}
            </option>
          ))}
        </select>
      </div>
      <Button size="sm" className="w-full" onClick={() => void start()}>
        <IconTranslate className="mr-1 h-3 w-3" /> Translate
      </Button>
      {jobId && <JobProgressCard jobId={jobId} title={`Translation to ${target}`} />}
    </div>
  );
}
