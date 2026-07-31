"use client";

// ProofreaderPanel — run an AI proofreading review on the active chapter and
// surface pending suggestions. Ported from the workspace page: same endpoint
// (editingApi.review with mode "proofreading"), same suggestion query, plus
// a readable list of pending suggestions and friendly error toasts.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { IconProof } from "@/components/ui/icons";
import { editingApi } from "@/lib/api/editing";
import { toastError } from "@/lib/errors";

interface PanelProps {
  projectId: string;
  writingBookId: string;
  activeChapterId: string | null;
  onApplyEdit?: (content: string) => void;
  onInsertImage?: (markdown: string) => void;
}

export function ProofreaderPanel({ activeChapterId }: PanelProps) {
  const toast = useToast();
  const qc = useQueryClient();

  const { data: suggestions, isLoading } = useQuery({
    queryKey: ["editing-suggestions", activeChapterId],
    queryFn: () => editingApi.listSuggestions(activeChapterId!, { status: "pending" }),
    enabled: Boolean(activeChapterId),
  });

  async function run() {
    if (!activeChapterId) return;
    try {
      await editingApi.review(activeChapterId, { mode: "proofreading" });
      void qc.invalidateQueries({ queryKey: ["editing-suggestions", activeChapterId] });
      toast({ title: "Review complete", variant: "success" });
    } catch (e) {
      toast(toastError(e));
    }
  }

  return (
    <div className="space-y-2 p-1">
      <p className="text-xs text-muted-foreground">Catch grammar, spelling, and style issues.</p>
      <Button size="sm" className="w-full" disabled={!activeChapterId} onClick={() => void run()}>
        <IconProof className="mr-1 h-3 w-3" /> Proofread chapter
      </Button>
      {!activeChapterId ? (
        <p className="text-[10px] text-muted-foreground">Select a chapter first.</p>
      ) : suggestions && suggestions.length > 0 ? (
        <>
          <p className="text-[10px] font-medium text-muted-foreground">
            {suggestions.length} pending suggestion{suggestions.length === 1 ? "" : "s"}
          </p>
          <div className="space-y-1.5">
            {suggestions.slice(0, 5).map((s) => (
              <div key={s.id} className="rounded border border-border p-2">
                <div className="flex flex-wrap items-center gap-1">
                  <Badge variant="outline" className="text-[9px]">
                    {s.category}
                  </Badge>
                  <Badge variant="outline" className="text-[9px]">
                    {s.severity}
                  </Badge>
                </div>
                <p className="mt-1 line-clamp-2 text-[10px] text-muted-foreground">
                  {s.original_text}
                </p>
              </div>
            ))}
          </div>
        </>
      ) : (
        !isLoading && (
          <p className="text-[10px] text-muted-foreground">No suggestions yet — run a review.</p>
        )
      )}
    </div>
  );
}
