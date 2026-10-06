"use client";

// TranslationPanel creates and reopens independent translated editions. The
// source manuscript remains editable and unchanged throughout the workflow.

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { IconTranslate } from "@/components/ui/icons";
import { JobProgressCard } from "@/components/shared/job-progress-card";
import { toastError } from "@/lib/errors";
import {
  bookWritingApi,
  type TranslationEdition,
  type TranslationSummary,
} from "@/lib/api/bookWriting";
import { jobsApi, type JobResponse } from "@/lib/api/jobs";

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
  { code: "zh", name: "Chinese (Simplified)" },
  { code: "ar", name: "Arabic" },
  { code: "ru", name: "Russian" },
  { code: "ko", name: "Korean" },
  { code: "nl", name: "Dutch" },
  { code: "hi", name: "Hindi" },
  { code: "pl", name: "Polish" },
  { code: "sv", name: "Swedish" },
  { code: "tr", name: "Turkish" },
  { code: "th", name: "Thai" },
  { code: "vi", name: "Vietnamese" },
  { code: "id", name: "Indonesian" },
  { code: "uk", name: "Ukrainian" },
];

function getSupportedLanguageCode(value: string): string {
  const normalized = value.trim().toLowerCase();
  const shortCode = normalized.split("-", 1)[0];
  return LANGS.find(
    (language) => language.code === shortCode || language.name.toLowerCase() === normalized,
  )?.code ?? "en";
}

export function TranslationPanel({ writingBookId }: PanelProps) {
  const [source, setSource] = useState("en");
  const [target, setTarget] = useState("es");
  const [jobId, setJobId] = useState<string | null>(null);
  const [isJobActive, setIsJobActive] = useState(false);
  const [editions, setEditions] = useState<TranslationSummary[]>([]);
  const [edition, setEdition] = useState<TranslationEdition | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const toast = useToast();

  const refreshHistory = useCallback(async () => {
    setLoadingHistory(true);
    setHistoryError(null);
    try {
      const result = await bookWritingApi.listTranslations(writingBookId);
      setEditions(result.items);
    } catch (error) {
      setHistoryError((error as Error).message || "Could not load translated editions.");
    } finally {
      setLoadingHistory(false);
    }
  }, [writingBookId]);

  useEffect(() => {
    let active = true;
    setEditions([]);
    setEdition(null);
    setJobId(null);
    setIsJobActive(false);
    void refreshHistory();
    void bookWritingApi.getBook(writingBookId).then((book) => {
      if (active) setSource(getSupportedLanguageCode(book.language));
    }).catch(() => {
      // Keep the standard English default if metadata cannot be loaded.
    });
    return () => {
      active = false;
    };
  }, [refreshHistory, writingBookId]);

  const openEdition = useCallback(async (translationId: string) => {
    try {
      const result = await bookWritingApi.getTranslation(writingBookId, translationId);
      setEdition(result);
      setSource(result.source_language);
      setTarget(result.target_language);
    } catch (error) {
      toast(toastError(error));
    }
  }, [toast, writingBookId]);

  const onJobComplete = useCallback(async (job: JobResponse) => {
    try {
      const translationId = job.result?.translation_id;
      if (job.status === "COMPLETED" && typeof translationId === "string") {
        await openEdition(translationId);
      }
      await refreshHistory();
    } finally {
      setIsJobActive(false);
    }
  }, [openEdition, refreshHistory]);

  async function start(
    translationId?: string,
    sourceLanguage: string = source,
    targetLanguage: string = target,
  ) {
    setIsJobActive(true);
    try {
      const response = await jobsApi.startTranslation(
        writingBookId,
        sourceLanguage,
        targetLanguage,
        translationId,
      );
      setJobId(response.id);
    } catch (error) {
      setIsJobActive(false);
      toast(toastError(error));
    }
  }

  const canTranslate = source !== target;

  return (
    <div className="space-y-3 p-1">
      <p className="text-xs text-muted-foreground">
        Create a separate translated edition. Your source chapters are never replaced.
      </p>
      <div className="space-y-1">
        <label className="text-[10px] font-medium text-muted-foreground" htmlFor="translate-source">
          From
        </label>
        <select
          id="translate-source"
          className="w-full rounded border border-input bg-background px-2 py-1 text-xs"
          value={source}
          onChange={(event) => setSource(event.target.value)}
        >
          {LANGS.map((language) => (
            <option key={language.code} value={language.code}>
              {language.name}
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
          onChange={(event) => setTarget(event.target.value)}
        >
          {LANGS.map((language) => (
            <option key={language.code} value={language.code}>
              {language.name}
            </option>
          ))}
        </select>
      </div>
      <Button
        size="sm"
        className="w-full"
        disabled={!canTranslate || isJobActive}
        onClick={() => void start()}
      >
        <IconTranslate className="mr-1 h-3 w-3" /> Create translated edition
      </Button>
      {!canTranslate && (
        <p className="text-xs text-amber-700">Choose two different languages.</p>
      )}
      {jobId && (
        <JobProgressCard
          jobId={jobId}
          title={`Translation to ${LANGS.find((language) => language.code === target)?.name ?? target}`}
          onComplete={onJobComplete}
        />
      )}

      <section className="space-y-2 border-t border-border pt-3" aria-labelledby="translation-history-heading">
        <div className="flex items-center justify-between">
          <h3 id="translation-history-heading" className="text-xs font-semibold">Translated editions</h3>
          <Button variant="ghost" size="sm" disabled={loadingHistory} onClick={() => void refreshHistory()}>
            Refresh
          </Button>
        </div>
        {historyError && <p className="text-xs text-destructive">{historyError}</p>}
        {!loadingHistory && editions.length === 0 && !historyError && (
          <p className="text-xs text-muted-foreground">No translated editions yet.</p>
        )}
        <div className="max-h-48 space-y-1 overflow-y-auto">
          {editions.map((item) => (
            <div key={item.id} className="rounded border border-border p-2">
              <div className="flex items-start justify-between gap-2">
                <button
                  className="min-w-0 flex-1 text-left"
                  onClick={() => void openEdition(item.id)}
                >
                  <span className="block text-xs font-medium">
                    {LANGS.find((language) => language.code === item.source_language)?.name ?? item.source_language}
                    {" → "}
                    {LANGS.find((language) => language.code === item.target_language)?.name ?? item.target_language}
                  </span>
                  <span className="block text-[10px] text-muted-foreground">
                    {item.status} · {item.translated_chapter_count}/{item.source_chapter_count} chapters
                  </span>
                </button>
                {item.status === "FAILED" && (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={isJobActive}
                    onClick={() => {
                      setSource(item.source_language);
                      setTarget(item.target_language);
                      void start(item.id, item.source_language, item.target_language);
                    }}
                  >
                    Resume
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {edition && (
        <section className="space-y-2 border-t border-border pt-3" aria-label="Translated manuscript">
          <div>
            <h3 className="text-xs font-semibold">
              {LANGS.find((language) => language.code === edition.target_language)?.name ?? edition.target_language} edition
            </h3>
            <p className="text-[10px] text-muted-foreground">
              {edition.status} · {edition.target_word_count.toLocaleString()} words
            </p>
            {edition.error_message && (
              <p className="mt-1 text-xs text-destructive">{edition.error_message}</p>
            )}
          </div>
          <div className="max-h-80 space-y-1 overflow-y-auto">
            {edition.chapters.map((chapter) => (
              <details key={chapter.id} className="rounded border border-border p-2">
                <summary className="cursor-pointer text-xs font-medium">
                  {chapter.chapter_number}. {chapter.title} · {chapter.status}
                </summary>
                {chapter.error_message && (
                  <p className="mt-2 text-xs text-destructive">{chapter.error_message}</p>
                )}
                <pre className="mt-2 whitespace-pre-wrap break-words font-sans text-xs leading-relaxed">
                  {chapter.content || (chapter.status === "PENDING" ? "Not translated yet." : "No translated text.")}
                </pre>
              </details>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
