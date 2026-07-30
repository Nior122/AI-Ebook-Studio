// Phase 7 — AI Editing & Proofreading API client.

import { apiClient } from "@/lib/api";
import type {
  BulkActionResponse,
  ChapterReviewResponse,
  EditingSuggestion,
  ReviewJob,
  ReviewSummary,
  SelectionActionRequest,
  ReviewRequest,
  StartFullReviewRequest,
} from "@/types/api";

export const editingApi = {
  // Chapter review
  async review(chapterId: string, payload: ReviewRequest): Promise<ChapterReviewResponse> {
    return apiClient.post<ChapterReviewResponse>(
      `/editing/chapters/${chapterId}/review`,
      { payload },
    );
  },

  // Selection quick-action
  async selectionAction(
    chapterId: string,
    payload: SelectionActionRequest,
  ): Promise<EditingSuggestion> {
    return apiClient.post<EditingSuggestion>(
      `/editing/chapters/${chapterId}/review-selection`,
      { payload },
    );
  },

  // Suggestions — single
  async getSuggestion(suggestionId: string): Promise<EditingSuggestion> {
    return apiClient.get<EditingSuggestion>(`/editing/suggestions/${suggestionId}`);
  },

  async acceptSuggestion(suggestionId: string): Promise<EditingSuggestion> {
    return apiClient.post<EditingSuggestion>(`/editing/suggestions/${suggestionId}/accept`);
  },

  async rejectSuggestion(suggestionId: string, reason?: string): Promise<EditingSuggestion> {
    return apiClient.post<EditingSuggestion>(
      `/editing/suggestions/${suggestionId}/reject`,
      { payload: { reason } },
    );
  },

  async ignoreSuggestion(suggestionId: string): Promise<EditingSuggestion> {
    return apiClient.post<EditingSuggestion>(`/editing/suggestions/${suggestionId}/ignore`);
  },

  async regenerateSuggestion(suggestionId: string): Promise<EditingSuggestion> {
    return apiClient.post<EditingSuggestion>(`/editing/suggestions/${suggestionId}/regenerate`);
  },

  // Suggestions — lists & bulk
  async listSuggestions(
    chapterId: string,
    filters?: { category?: string; severity?: string; status?: string },
  ): Promise<EditingSuggestion[]> {
    return apiClient.get<EditingSuggestion[]>(
      `/editing/chapters/${chapterId}/suggestions`,
      filters as Record<string, unknown>,
    );
  },

  async acceptAll(chapterId: string): Promise<BulkActionResponse> {
    return apiClient.post<BulkActionResponse>(`/editing/chapters/${chapterId}/suggestions/accept-all`);
  },

  async rejectAll(chapterId: string): Promise<BulkActionResponse> {
    return apiClient.post<BulkActionResponse>(`/editing/chapters/${chapterId}/suggestions/reject-all`);
  },

  // Review summary
  async reviewSummary(chapterId: string): Promise<ReviewSummary> {
    return apiClient.get<ReviewSummary>(`/editing/chapters/${chapterId}/review-summary`);
  },

  // Review jobs
  async startReviewJob(bookId: string, payload: StartFullReviewRequest): Promise<ReviewJob> {
    return apiClient.post<ReviewJob>(
      `/editing/books/${bookId}/review-job/start`,
      { payload },
    );
  },

  async processReviewJob(jobId: string): Promise<ReviewJob> {
    return apiClient.post<ReviewJob>(`/editing/review-jobs/${jobId}/process`);
  },

  async getReviewJob(jobId: string): Promise<ReviewJob> {
    return apiClient.get<ReviewJob>(`/editing/review-jobs/${jobId}`);
  },

  async listReviewJobs(bookId: string): Promise<ReviewJob[]> {
    return apiClient.get<ReviewJob[]>(`/editing/books/${bookId}/review-jobs`);
  },
};