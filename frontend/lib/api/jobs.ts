// Jobs API — poll status of async background jobs.

import { apiClient } from "@/lib/api";

export type JobType =
  | "BOOK_GENERATION"
  | "PROOFREADING"
  | "IMAGE_ANALYSIS"
  | "IMAGE_GENERATION"
  | "DOCX_BUILD"
  | "PDF_EXPORT"
  | "EPUB_EXPORT"
  | "TRANSLATION"
  | "MARKETING_GENERATION"
  | "KDP_VALIDATION"
  | "COVER_GENERATION";

export type JobStatus = "PENDING" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface JobResponse {
  id: string;
  job_type: JobType;
  status: JobStatus;
  progress: number;
  current_step: string | null;
  result: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export const jobsApi = {
  get(jobId: string) {
    return apiClient.get<JobResponse>(`/jobs/${jobId}`);
  },
  cancel(jobId: string) {
    return apiClient.post<{ success: boolean }>(`/jobs/${jobId}/cancel`, {});
  },

  async pollUntilDone(jobId: string, onProgress?: (job: JobResponse) => void, intervalMs = 800, timeoutMs = 600000): Promise<JobResponse> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const job = await jobsApi.get(jobId);
      onProgress?.(job);
      if (job.status === "COMPLETED" || job.status === "FAILED" || job.status === "CANCELLED") {
        return job;
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    throw new Error("Job timed out");
  },

  // Async wrapper helpers — fire and forget.
  startExport(bookId: string, format: "docx" | "pdf" | "epub"): Promise<JobResponse> {
    return apiClient.post<JobResponse>(`/async/books/${bookId}/exports/${format}`, {});
  },
  startKdpValidate(bookId: string): Promise<JobResponse> {
    return apiClient.post<JobResponse>(`/async/books/${bookId}/kdp-validate`, {});
  },
  startMarketing(bookId: string, assetType: string): Promise<JobResponse> {
    return apiClient.post<JobResponse>(`/async/books/${bookId}/marketing/${assetType}`, {});
  },
  startCover(bookId: string, component: string = "all"): Promise<JobResponse> {
    return apiClient.post<JobResponse>(`/async/books/${bookId}/cover?component=${component}`, {});
  },
  startTranslation(bookId: string, sourceLang: string, targetLang: string): Promise<JobResponse> {
    return apiClient.post<JobResponse>(
      `/async/books/${bookId}/translate?source_lang=${sourceLang}&target_lang=${targetLang}`,
      {}
    );
  },
};
