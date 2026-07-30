// Phase 6 — Book Writing Engine API client.
// Backend prefix: /api/v1/book-writing
// Wraps apiClient with typed interfaces mirroring the Phase 6 backend schemas.

import { apiClient } from "@/lib/api";
import type {
  BookBlueprint,
  BookBlueprintUpdatePayload,
  BookBrief,
  BookBriefUpdatePayload,
  BookWorkflow,
  ChapterVersion,
  GenerateRequest,
  Manuscript,
  WritingBook,
  WritingBookCreatePayload,
  WritingBookSettings,
  WritingBookSettingsUpdatePayload,
  WritingBookUpdatePayload,
  WritingChapter,
  WritingChapterCreatePayload,
  WritingChapterUpdatePayload,
} from "@/types/api";

const BASE = "/book-writing";

export const bookWritingApi = {
  // ── Books ──────────────────────────────────────────────
  async createBook(payload: WritingBookCreatePayload): Promise<WritingBook> {
    return apiClient.post<WritingBook>(`${BASE}/books`, payload);
  },

  async listBooks(): Promise<WritingBook[]> {
    return apiClient.get<WritingBook[]>(`${BASE}/books`);
  },

  async getBook(bookId: string): Promise<WritingBook> {
    return apiClient.get<WritingBook>(`${BASE}/books/${bookId}`);
  },

  async updateBook(bookId: string, payload: WritingBookUpdatePayload): Promise<WritingBook> {
    return apiClient.patch<WritingBook>(`${BASE}/books/${bookId}`, { payload });
  },

  async deleteBook(bookId: string): Promise<void> {
    return apiClient.delete<void>(`${BASE}/books/${bookId}`);
  },

  async getWorkflow(bookId: string): Promise<BookWorkflow> {
    return apiClient.get<BookWorkflow>(`${BASE}/books/${bookId}/workflow`);
  },

  // ── Book Brief ─────────────────────────────────────────
  async generateBrief(bookId: string, gen?: GenerateRequest): Promise<BookBrief> {
    return apiClient.post<BookBrief>(`${BASE}/books/${bookId}/brief/generate`, { payload: gen ?? {} });
  },

  async getBrief(bookId: string): Promise<BookBrief> {
    return apiClient.get<BookBrief>(`${BASE}/books/${bookId}/brief`);
  },

  async updateBrief(bookId: string, payload: BookBriefUpdatePayload): Promise<BookBrief> {
    return apiClient.patch<BookBrief>(`${BASE}/books/${bookId}/brief`, { payload });
  },

  // ── Book Blueprint ─────────────────────────────────────
  async generateBlueprint(bookId: string, gen?: GenerateRequest): Promise<BookBlueprint> {
    return apiClient.post<BookBlueprint>(`${BASE}/books/${bookId}/blueprint/generate`, { payload: gen ?? {} });
  },

  async getBlueprint(bookId: string): Promise<BookBlueprint> {
    return apiClient.get<BookBlueprint>(`${BASE}/books/${bookId}/blueprint`);
  },

  async updateBlueprint(bookId: string, payload: BookBlueprintUpdatePayload): Promise<BookBlueprint> {
    return apiClient.patch<BookBlueprint>(`${BASE}/books/${bookId}/blueprint`, { payload });
  },

  // ── Chapters ───────────────────────────────────────────
  async listChapters(bookId: string): Promise<WritingChapter[]> {
    return apiClient.get<WritingChapter[]>(`${BASE}/books/${bookId}/chapters`);
  },

  async createChapter(bookId: string, payload: WritingChapterCreatePayload): Promise<WritingChapter> {
    return apiClient.post<WritingChapter>(`${BASE}/books/${bookId}/chapters`, payload);
  },

  async getChapter(chapterId: string): Promise<WritingChapter> {
    return apiClient.get<WritingChapter>(`${BASE}/chapters/${chapterId}`);
  },

  async updateChapter(chapterId: string, payload: WritingChapterUpdatePayload): Promise<WritingChapter> {
    return apiClient.patch<WritingChapter>(`${BASE}/chapters/${chapterId}`, { payload });
  },

  async deleteChapter(chapterId: string): Promise<void> {
    return apiClient.delete<void>(`${BASE}/chapters/${chapterId}`);
  },

  async reorderChapters(bookId: string, chapterIds: string[]): Promise<WritingChapter[]> {
    return apiClient.post<WritingChapter[]>(`${BASE}/books/${bookId}/chapters/reorder`, { chapter_ids: chapterIds });
  },

  // ── Chapter AI actions ─────────────────────────────────
  async generateOutline(chapterId: string, gen?: GenerateRequest): Promise<WritingChapter> {
    return apiClient.post<WritingChapter>(`${BASE}/chapters/${chapterId}/outline/generate`, { payload: gen ?? {} });
  },

  async generateChapter(chapterId: string, gen?: GenerateRequest): Promise<WritingChapter> {
    return apiClient.post<WritingChapter>(`${BASE}/chapters/${chapterId}/generate`, { payload: gen ?? {} });
  },

  async continueChapter(chapterId: string, gen?: GenerateRequest): Promise<WritingChapter> {
    return apiClient.post<WritingChapter>(`${BASE}/chapters/${chapterId}/continue`, { payload: gen ?? {} });
  },

  async rewriteChapter(chapterId: string, gen?: GenerateRequest): Promise<WritingChapter> {
    return apiClient.post<WritingChapter>(`${BASE}/chapters/${chapterId}/rewrite`, { payload: gen ?? {} });
  },

  async expandChapter(chapterId: string, gen?: GenerateRequest): Promise<WritingChapter> {
    return apiClient.post<WritingChapter>(`${BASE}/chapters/${chapterId}/expand`, { payload: gen ?? {} });
  },

  async shortenChapter(chapterId: string, gen?: GenerateRequest): Promise<WritingChapter> {
    return apiClient.post<WritingChapter>(`${BASE}/chapters/${chapterId}/shorten`, { payload: gen ?? {} });
  },

  async editAction(chapterId: string, action: string, gen?: GenerateRequest): Promise<WritingChapter> {
    return apiClient.post<WritingChapter>(`${BASE}/chapters/${chapterId}/edit/${action}`, { payload: gen ?? {} });
  },

  // ── Chapter versions ───────────────────────────────────
  async listVersions(chapterId: string): Promise<ChapterVersion[]> {
    return apiClient.get<ChapterVersion[]>(`${BASE}/chapters/${chapterId}/versions`);
  },

  async restoreVersion(chapterId: string, versionId: string): Promise<WritingChapter> {
    return apiClient.post<WritingChapter>(`${BASE}/chapters/${chapterId}/versions/${versionId}/restore`);
  },

  // ── Manuscript ─────────────────────────────────────────
  async refreshManuscript(bookId: string): Promise<Manuscript> {
    return apiClient.post<Manuscript>(`${BASE}/books/${bookId}/manuscript/refresh`);
  },

  async getManuscript(bookId: string): Promise<Manuscript> {
    return apiClient.get<Manuscript>(`${BASE}/books/${bookId}/manuscript`);
  },

  // ── Autosave ───────────────────────────────────────────
  async autosave(bookId: string, chapterId: string, content: string, versionType?: string): Promise<WritingChapter> {
    return apiClient.put<WritingChapter>(`${BASE}/books/${bookId}/chapters/${chapterId}/autosave`, {
      payload: { chapter_id: chapterId, content, version_type: versionType ?? "user_edited" },
    });
  },

  // ── Book settings (writing style profile) ──────────────
  async getSettings(bookId: string): Promise<WritingBookSettings> {
    return apiClient.get<WritingBookSettings>(`${BASE}/books/${bookId}/settings`);
  },

  async updateSettings(bookId: string, payload: WritingBookSettingsUpdatePayload): Promise<WritingBookSettings> {
    return apiClient.patch<WritingBookSettings>(`${BASE}/books/${bookId}/settings`, { payload });
  },

  // ── Export ──────────────────────────────────────────────
  async listExportFormats(bookId: string): Promise<Array<{format:string;label:string;mime_type:string;extension:string;description:string}>> {
    return apiClient.get(`${BASE}/books/${bookId}/exports/formats`);
  },
  async createExport(bookId: string, payload: {format:string; include_front_matter?:boolean; include_toc?:boolean; include_back_matter?:boolean}): Promise<any> {
    return apiClient.post(`${BASE}/books/${bookId}/exports`, payload);
  },
  async listExports(bookId: string): Promise<{items:Array<any>}> {
    return apiClient.get(`${BASE}/books/${bookId}/exports`);
  },
  getExportDownloadUrl(bookId: string, assetId: string): string {
    return `${process.env.NEXT_PUBLIC_API_BASE_URL || '/api/v1'}${BASE}/books/${bookId}/exports/${assetId}`;
  },
  async deleteExport(bookId: string, assetId: string): Promise<void> {
    return apiClient.delete(`${BASE}/books/${bookId}/exports/${assetId}`);
  },

  // ── KDP Validation ─────────────────────────────────────
  async validateKDP(bookId: string): Promise<any> {
    return apiClient.post(`${BASE}/books/${bookId}/validate-kdp`);
  },
  async getKDPReport(bookId: string): Promise<any> {
    return apiClient.get(`${BASE}/books/${bookId}/validate-kdp`);
  },

  // ── Marketing ───────────────────────────────────────────
  async listMarketingTypes(bookId: string): Promise<Array<{type_id:string;label:string;description:string}>> {
    return apiClient.get(`${BASE}/books/${bookId}/marketing/types`);
  },
  async generateMarketing(bookId: string, assetType: string): Promise<any> {
    return apiClient.post(`${BASE}/books/${bookId}/marketing/${assetType}`);
  },
  async listMarketing(bookId: string): Promise<{items:Array<any>}> {
    return apiClient.get(`${BASE}/books/${bookId}/marketing`);
  },
  async deleteMarketing(bookId: string, assetId: string): Promise<void> {
    return apiClient.delete(`${BASE}/books/${bookId}/marketing/${assetId}`);
  },

  // ── Translation ─────────────────────────────────────────
  async listTranslateLanguages(bookId: string): Promise<Array<{code:string;name:string}>> {
    return apiClient.get(`${BASE}/books/${bookId}/translate/languages`);
  },
  async translateBook(bookId: string, payload: {source_language:string;target_language:string}): Promise<any> {
    return apiClient.post(`${BASE}/books/${bookId}/translate`, payload);
  },
  async listTranslations(bookId: string): Promise<{items:Array<any>}> {
    return apiClient.get(`${BASE}/books/${bookId}/translate/history`);
  },

  // ── Cover ───────────────────────────────────────────────
  async generateFrontCover(bookId: string): Promise<{content:string;type:string}> {
    return apiClient.post(`${BASE}/books/${bookId}/cover/front`);
  },
  async generateBackCover(bookId: string): Promise<{content:string;type:string}> {
    return apiClient.post(`${BASE}/books/${bookId}/cover/back`);
  },
  async generateSpine(bookId: string): Promise<{content:string;type:string}> {
    return apiClient.post(`${BASE}/books/${bookId}/cover/spine`);
  },
  async generateFullCover(bookId: string): Promise<{front:{content:string;type:string};back:{content:string;type:string};spine:{content:string;type:string}}> {
    return apiClient.post(`${BASE}/books/${bookId}/cover/all`);
  },
};