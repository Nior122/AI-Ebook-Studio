"use client";

// MarketingPanel — generate marketing assets (Amazon description, subtitle,
// keywords, social posts, email promotion, …) via a background job.
// Ported from the workspace page; the asset list now matches the backend
// MarketingAssetType enum (uppercase values), with friendly error toasts.

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { IconMarketing } from "@/components/ui/icons";
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

const ASSETS = [
  { value: "AMAZON_DESCRIPTION", name: "Amazon Description" },
  { value: "SUBTITLE", name: "Subtitle" },
  { value: "KEYWORDS", name: "Keywords" },
  { value: "INSTAGRAM_CAPTION", name: "Instagram Caption" },
  { value: "FACEBOOK_POST", name: "Facebook Post" },
  { value: "X_POST", name: "X Post" },
  { value: "LINKEDIN_POST", name: "LinkedIn Post" },
  { value: "EMAIL_PROMOTION", name: "Email Promotion" },
  { value: "PINTEREST_POST", name: "Pinterest Post" },
];

export function MarketingPanel({ writingBookId }: PanelProps) {
  const [asset, setAsset] = useState("AMAZON_DESCRIPTION");
  const [jobId, setJobId] = useState<string | null>(null);
  const toast = useToast();

  async function generate() {
    try {
      const r = await jobsApi.startMarketing(writingBookId, asset);
      setJobId(r.id);
    } catch (e) {
      toast(toastError(e));
    }
  }

  return (
    <div className="space-y-2 p-1">
      <p className="text-xs text-muted-foreground">Generate promotional copy for your book.</p>
      <select
        className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
        value={asset}
        onChange={(e) => setAsset(e.target.value)}
        aria-label="Marketing asset type"
      >
        {ASSETS.map((a) => (
          <option key={a.value} value={a.value}>
            {a.name}
          </option>
        ))}
      </select>
      <Button size="sm" className="w-full" onClick={() => void generate()}>
        <IconMarketing className="mr-1 h-3 w-3" /> Generate
      </Button>
      {jobId && <JobProgressCard jobId={jobId} title={`Marketing: ${asset}`} />}
    </div>
  );
}
