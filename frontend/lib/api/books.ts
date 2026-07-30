// Books API module. A project owns exactly one primary book created via the
// project-scoped endpoint; the remaining endpoints operate on that book.

import { apiClient } from "@/lib/api";
import type { Book, BookCreatePayload, BookUpdatePayload } from "@/types";

export const booksApi = {
  /** Create (or fetch) the primary book for a project. */
  createForProject(projectId: string, payload: BookCreatePayload): Promise<Book> {
    return apiClient.post<Book>(`/projects/${projectId}/book`, payload);
  },

  /** List books belonging to a project. */
  listForProject(projectId: string): Promise<Book[]> {
    return apiClient.get<Book[]>(`/projects/${projectId}/books`);
  },

  get(bookId: string): Promise<Book> {
    return apiClient.get<Book>(`/books/${bookId}`);
  },

  update(bookId: string, payload: BookUpdatePayload): Promise<Book> {
    return apiClient.patch<Book>(`/books/${bookId}`, payload);
  },
};
