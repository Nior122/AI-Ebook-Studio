// Book settings API module. Formatting settings read/update before conversion.

import { apiClient } from "@/lib/api";
import type { BookSettings, BookSettingsUpdatePayload } from "@/types";

export const bookSettingsApi = {
  get(bookId: string): Promise<BookSettings> {
    return apiClient.get<BookSettings>(`/books/${bookId}/settings`);
  },

  update(bookId: string, payload: BookSettingsUpdatePayload): Promise<BookSettings> {
    return apiClient.patch<BookSettings>(`/books/${bookId}/settings`, payload);
  },
};
