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
  };
  size: {
    total_word_count: number;
    custom: boolean;
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
  };
  ai?: {
    creativity?: string;
    speed?: string;
    provider?: string;
    model?: string;
    temperature?: number | null;
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