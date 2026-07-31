"use client";

// Debounced autosave hook. Watches the active chapter's content, schedules a
// save 800ms after the last keystroke, and reports status:
//   idle | saving | saved | failed   (+ lastSavedAt for "Last saved HH:MM").
// Content is captured by value at schedule time so switching chapters can
// never write the wrong content into the wrong chapter.

import { useCallback, useEffect, useRef, useState } from "react";
import { studioApi } from "@/lib/api/studio";

export type SaveStatus = "idle" | "saving" | "saved" | "failed";

export interface AutosaveState {
  status: SaveStatus;
  lastSavedAt: Date | null;
  saveNow: () => Promise<boolean>;
}

export function useAutosave(
  projectId: string | undefined,
  chapterId: string | undefined,
  content: string,
): AutosaveState {
  const [status, setStatus] = useState<SaveStatus>("idle");
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const savingRef = useRef(false);
  const pendingRef = useRef<{ projectId: string; chapterId: string; content: string } | null>(null);

  const performSave = useCallback(
    async (projectIdToSave: string, chapterIdToSave: string, contentToSave: string) => {
      if (savingRef.current) {
        pendingRef.current = { projectId: projectIdToSave, chapterId: chapterIdToSave, content: contentToSave };
        return false;
      }
      savingRef.current = true;
      setStatus("saving");
      try {
        await studioApi.autosave(projectIdToSave, { [chapterIdToSave]: contentToSave });
        setStatus("saved");
        setLastSavedAt(new Date());
        while (pendingRef.current) {
          const pending = pendingRef.current;
          pendingRef.current = null;
          await studioApi.autosave(pending.projectId, { [pending.chapterId]: pending.content });
        }
        return true;
      } catch {
        setStatus("failed");
        return false;
      } finally {
        savingRef.current = false;
      }
    },
    [],
  );

  const saveNow = useCallback(async () => {
    if (!projectId || !chapterId) return false;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    return performSave(projectId, chapterId, content);
  }, [projectId, chapterId, content, performSave]);

  useEffect(() => {
    if (!projectId || !chapterId) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    const scheduled = content;
    timerRef.current = setTimeout(() => {
      void performSave(projectId, chapterId, scheduled);
    }, 800);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [content, projectId, chapterId, performSave]);

  return { status, lastSavedAt, saveNow };
}
