"use client";

// AssistantPanel — AI writing assistant for the unified book workspace.
// Chat with the assistant about the current book, or run quick edit actions
// (Fix grammar / Shorten / Expand / Continue / Rewrite) that apply the
// returned content directly to the active chapter via onApplyEdit.

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { IconSparkles } from "@/components/ui/icons";
import { studioApi, type AssistantResponse } from "@/lib/api/studio";
import { toastError } from "@/lib/errors";

interface PanelProps {
  projectId: string;
  writingBookId: string;
  activeChapterId: string | null;
  onApplyEdit?: (content: string) => void;
  onInsertImage?: (markdown: string) => void;
}

type QuickAction = "fix_grammar" | "shorten" | "expand" | "continue" | "rewrite";

const QUICK_ACTIONS: { action: QuickAction; label: string }[] = [
  { action: "fix_grammar", label: "Fix grammar" },
  { action: "shorten", label: "Shorten" },
  { action: "expand", label: "Expand" },
  { action: "continue", label: "Continue" },
  { action: "rewrite", label: "Rewrite" },
];

interface ChatEntry {
  role: "user" | "assistant";
  text: string;
}

export function AssistantPanel({ projectId, activeChapterId, onApplyEdit }: PanelProps) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<ChatEntry[]>([]);
  const toast = useToast();
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [history]);

  async function send(text: string, action?: QuickAction) {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setHistory((h) => [...h, { role: "user", text: trimmed }]);
    setMessage("");
    try {
      const res: AssistantResponse = await studioApi.assistant(projectId, {
        message: trimmed,
        chapter_id: activeChapterId,
        action: action ?? null,
      });
      setHistory((h) => [...h, { role: "assistant", text: res.reply }]);
      if (action && res.applied && res.new_content && onApplyEdit) {
        onApplyEdit(res.new_content);
        toast({
          title: "Edit applied",
          description: "The updated content was applied to your chapter.",
          variant: "success",
        });
      }
    } catch (e) {
      toast(toastError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2 p-1">
      <div className="flex flex-wrap gap-1">
        {QUICK_ACTIONS.map((q) => (
          <button
            key={q.action}
            type="button"
            disabled={!activeChapterId || busy}
            onClick={() => void send("Apply this action", q.action)}
            className="rounded border border-border px-2 py-1 text-[10px] font-medium text-muted-foreground hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
          >
            {q.label}
          </button>
        ))}
      </div>
      {!activeChapterId && (
        <p className="text-[10px] text-muted-foreground">Select a chapter first to use quick actions.</p>
      )}
      <div
        ref={scrollRef}
        className="max-h-64 space-y-2 overflow-y-auto rounded border border-border p-2"
      >
        {history.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Ask the assistant for writing help — or try a quick action above.
          </p>
        ) : (
          history.map((entry, i) => (
            <div
              key={i}
              className={`rounded p-2 text-xs leading-relaxed ${
                entry.role === "user" ? "bg-secondary" : "bg-muted"
              }`}
            >
              {entry.text}
            </div>
          ))
        )}
      </div>
      <Textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Ask the assistant…"
        className="min-h-[72px]"
      />
      <Button
        size="sm"
        className="w-full"
        disabled={busy || !message.trim()}
        onClick={() => void send(message)}
      >
        {busy ? <Spinner className="h-3 w-3" /> : <IconSparkles className="mr-1 h-3 w-3" />} Send
      </Button>
    </div>
  );
}
