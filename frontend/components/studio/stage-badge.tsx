"use client";

// Project lifecycle stage badge with quick transitions:
// Draft → Generating → Review → Ready for Export → Published.

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { studioApi, STAGE_LABELS, type ProjectStage } from "@/lib/api/studio";
import { toastError } from "@/lib/errors";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

const STAGE_STYLES: Record<ProjectStage, string> = {
  draft: "bg-secondary text-secondary-foreground",
  generating: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
  review: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  ready_for_export: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  published: "bg-purple-500/10 text-purple-700 dark:text-purple-300",
};

const STAGE_ORDER: ProjectStage[] = ["draft", "generating", "review", "ready_for_export", "published"];

export function StageBadge({
  projectId,
  stage,
  onChanged,
}: {
  projectId: string;
  stage: string;
  onChanged?: (stage: string) => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const current = (STAGE_ORDER.includes(stage as ProjectStage) ? stage : "draft") as ProjectStage;

  const setStage = async (next: ProjectStage) => {
    if (next === current || busy) return;
    setBusy(true);
    try {
      await studioApi.setStage(projectId, next);
      toast({ title: `Stage updated — ${STAGE_LABELS[next]}`, variant: "success" });
      onChanged?.(next);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["projects", "detail", projectId] });
    } catch (error) {
      toast(toastError(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative inline-block">
      <Badge className={cn("cursor-default", STAGE_STYLES[current])}>
        {STAGE_LABELS[current]}
      </Badge>
      <div className="mt-1 flex items-center gap-1">
        {STAGE_ORDER.map((option) => {
          const disabled =
            busy || option === current || (current === "generating" && option === "draft");
          return (
            <button
              key={option}
              disabled={disabled}
              onClick={() => void setStage(option)}
              title={`Mark as ${STAGE_LABELS[option]}`}
              className={cn(
                "h-1.5 rounded-full transition-colors",
                option === current
                  ? "w-4 bg-primary"
                  : "w-1.5 bg-border hover:bg-primary/60",
                disabled && "cursor-not-allowed opacity-30",
              )}
            />
          );
        })}
      </div>
    </div>
  );
}
