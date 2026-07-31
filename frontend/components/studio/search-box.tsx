"use client";

// Manuscript search (Ctrl+F). Searches the whole book — chapters, headings,
// and image captions — with instant results and jump-to-chapter.

import { useEffect, useRef, useState } from "react";
import { studioApi, type SearchResult } from "@/lib/api/studio";
import { IconSearch, IconClose } from "@/components/ui/icons";
import { Spinner } from "@/components/ui/skeleton";

interface SearchBoxProps {
  projectId: string;
  onSelectChapter: (chapterId: string) => void;
  onInsertImage?: (markdown: string) => void;
}

export function SearchBox({ projectId, onSelectChapter, onInsertImage }: SearchBoxProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    timerRef.current = setTimeout(async () => {
      try {
        const response = await studioApi.search(projectId, trimmed);
        setResults(response.results);
        setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [query, projectId]);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  return (
    <div className="relative w-full max-w-xs" ref={rootRef}>
      <div className="relative">
        <IconSearch className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="Search manuscript… (Ctrl+F)"
          data-search-input="true"
          className="w-full rounded-lg border border-input bg-background py-1.5 pl-8 pr-8 text-xs text-foreground outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-1 focus:ring-ring"
        />
        {query ? (
          <button
            onClick={() => {
              setQuery("");
              setResults([]);
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label="Clear search"
          >
            <IconClose className="h-3 w-3" />
          </button>
        ) : null}
      </div>

      {open && (loading || results.length > 0) ? (
        <div className="absolute left-0 right-0 top-9 z-[95] max-h-80 overflow-y-auto rounded-xl border border-border bg-card shadow-xl">
          {loading ? (
            <div className="flex justify-center p-3">
              <Spinner className="h-4 w-4" />
            </div>
          ) : (
            results.map((result, index) => (
              <button
                key={`${result.type}-${index}-${result.chapter_id}`}
                className="block w-full border-b border-border/60 px-3 py-2 text-left hover:bg-secondary/50"
                onClick={() => {
                  setOpen(false);
                  if (result.type === "image_caption") {
                    if (result.image_url && onInsertImage) {
                      onInsertImage(`![${result.snippet.slice(0, 40)}](${result.image_url})`);
                    }
                    return;
                  }
                  if (result.chapter_id) onSelectChapter(result.chapter_id);
                }}
              >
                <div className="flex items-center gap-2">
                  <span className="rounded bg-secondary px-1 py-0.5 text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
                    {result.type === "image_caption" ? "image" : result.type}
                  </span>
                  <span className="truncate text-xs font-medium text-foreground">
                    {result.type === "image_caption" ? "Image caption" : result.chapter_title}
                  </span>
                </div>
                <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">
                  {result.snippet}
                </p>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
