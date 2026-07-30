"use client";

// React Query hooks for books. A project has one primary book; settings are
// fetched/updated per book.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { booksApi } from "@/lib/api/books";
import { bookSettingsApi } from "@/lib/api/book-settings";
import type { Book, BookCreatePayload, BookSettings, BookSettingsUpdatePayload } from "@/types";

export function useProjectBook(projectId: string | undefined) {
  return useQuery({
    queryKey: ["project-book", projectId],
    queryFn: async () => {
      const books = await booksApi.listForProject(projectId as string);
      return books[0] ?? null;
    },
    enabled: Boolean(projectId),
  });
}

export function useBook(bookId: string | undefined) {
  return useQuery({
    queryKey: ["book", bookId],
    queryFn: () => booksApi.get(bookId as string),
    enabled: Boolean(bookId),
  });
}

export function useCreateBook() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, payload }: { projectId: string; payload: BookCreatePayload }) =>
      booksApi.createForProject(projectId, payload),
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({ queryKey: ["project-book", vars.projectId] });
    },
  });
}

export function useBookSettings(bookId: string | undefined) {
  return useQuery({
    queryKey: ["book-settings", bookId],
    queryFn: () => bookSettingsApi.get(bookId as string),
    enabled: Boolean(bookId),
  });
}

export function useUpdateBookSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ bookId, payload }: { bookId: string; payload: BookSettingsUpdatePayload }) =>
      bookSettingsApi.update(bookId, payload),
    onSuccess: (_data: BookSettings, vars) => {
      void qc.invalidateQueries({ queryKey: ["book-settings", vars.bookId] });
    },
  });
}
