// Generation API — one-click book generation

import { apiClient } from "@/lib/api";

export interface BookSetup {
  details: {
    title: string;
    subtitle?: string | null;
    topic: string;
    target_audience: string;
    tone: string;
    writing_style: string;
    language: string;
    author?: string | null;
    book_purpose?: string | null;
  };
  size: {
    total_word_count: number;
    custom: boolean;
    chapters_override?: number | null;
  };
  layout?: {
    page_size?: string;
    custom_page_size?: { width: number; height: number } | null;
    margins?: { top: number; bottom: number; left: number; right: number };
    header_font?: string;
    header_size?: number;
    body_font?: string;
    body_size?: number;
    line_spacing?: number;
    paragraph_spacing?: number;
    image_width?: number;
    image_ratio?: string;
    default_image_style?: string;
    chapter_heading_style?: string;
  };
  ai?: {
    creativity?: string;
    speed?: string;
    provider?: string;
    model?: string;
    temperature?: number | null;
    reading_level?: string | null;
    writing_quality?: string | null;
    use_citations?: boolean;
    generate_exercises?: boolean;
    generate_summaries?: boolean;
  };
  special_instructions?: {
    instructions?: string;
  };
}

export interface SetupResponse {
  project_id: string | null;
  book_id: string | null;
  writing_book_id: string | null;
  job_id: string | null;
  clarification_questions: Array<{ id: string; question: string; placeholder: string }> | null;
}

export const generationApi = {
  setup(payload: BookSetup): Promise<SetupResponse> {
    return apiClient.post<SetupResponse>("/generation/setup", payload);
  },
};

export const WORD_COUNT_PRESETS = [5000, 10000, 15000, 25000, 50000] as const;

/** Rough chapter estimate for a word count (mirrors the backend). */
export function estimateChapters(words: number): number {
  if (words <= 5000) return 5;
  if (words <= 10000) return 8;
  if (words <= 15000) return 10;
  if (words <= 25000) return 14;
  if (words <= 50000) return 20;
  return 25;
}
