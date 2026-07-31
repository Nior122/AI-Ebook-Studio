// Studio UX API module — autosave, versions, activities, notifications,
// search, bookmarks, stages, the assistant, images, and provider keys.
// This is the single client-side gateway for the unified workspace features.

import { apiClient } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types (mirror backend schemas/studio.py)
// ---------------------------------------------------------------------------

export interface AutosaveResponse {
  saved_at: string;
  saved_chapters: number;
  revision: number;
}

export interface ProjectVersion {
  id: string;
  project_id: string;
  label: string;
  reason: string | null;
  created_by: string;
  created_at: string;
}

export interface RestoreResponse {
  version_id: string;
  restored: boolean;
  chapters_updated: number;
  message: string;
}

export interface ActivityRead {
  id: string;
  project_id: string;
  kind: string;
  message: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface NotificationRead {
  id: string;
  project_id: string | null;
  kind: string;
  title: string;
  body: string | null;
  level: "info" | "success" | "warning" | "error";
  read_at: string | null;
  action_type: string | null;
  action_payload: Record<string, unknown> | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: NotificationRead[];
  unread: number;
}

export interface Bookmark {
  id: string;
  project_id: string;
  chapter_id: string | null;
  title: string;
  note: string | null;
  created_at: string;
}

export interface SearchResult {
  type: "chapter" | "heading" | "image_caption";
  chapter_id: string | null;
  chapter_title: string;
  snippet: string;
  heading?: string | null;
  image_url?: string | null;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
}

export type ProjectStage = "draft" | "generating" | "review" | "ready_for_export" | "published";

export const STAGE_LABELS: Record<ProjectStage, string> = {
  draft: "Draft",
  generating: "Generating",
  review: "Review",
  ready_for_export: "Ready for Export",
  published: "Published",
};

export interface StageResponse {
  project_id: string;
  stage: string;
  label: string;
}

export interface AssistantRequest {
  message: string;
  chapter_id?: string | null;
  action?: "chat" | "rewrite" | "continue" | "expand" | "shorten" | "fix_grammar" | null;
}

export interface AssistantResponse {
  reply: string;
  applied: boolean;
  new_content: string | null;
}

export interface ProviderKeyStatus {
  provider: string | null;
  has_key: boolean;
}

export interface GeneratedImage {
  id: string;
  chapter_id: string | null;
  prompt: string;
  provider: string;
  aspect_ratio: string;
  file_url: string | null;
  status: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const studioApi = {
  // Autosave
  autosave(projectId: string, chapters: Record<string, string>): Promise<AutosaveResponse> {
    return apiClient.put<AutosaveResponse>(`/projects/${projectId}/autosave`, { chapters });
  },

  // Versions (restore points)
  listVersions(projectId: string, limit = 50): Promise<ProjectVersion[]> {
    return apiClient.get<ProjectVersion[]>(`/projects/${projectId}/versions`, { limit });
  },
  createVersion(projectId: string, label: string, reason?: string): Promise<ProjectVersion> {
    return apiClient.post<ProjectVersion>(`/projects/${projectId}/versions`, { label, reason });
  },
  restoreVersion(versionId: string): Promise<RestoreResponse> {
    return apiClient.post<RestoreResponse>(`/versions/${versionId}/restore`, {});
  },

  // Activity timeline
  listActivities(projectId: string, limit = 100): Promise<ActivityRead[]> {
    return apiClient.get<ActivityRead[]>(`/projects/${projectId}/activities`, { limit });
  },

  // Notifications
  listNotifications(options?: { unread_only?: boolean; limit?: number }): Promise<NotificationListResponse> {
    return apiClient.get<NotificationListResponse>("/notifications", options ?? {});
  },
  unreadCount(): Promise<{ unread: number }> {
    return apiClient.get<{ unread: number }>("/notifications/unread-count");
  },
  markRead(notificationId: string): Promise<NotificationRead> {
    return apiClient.post<NotificationRead>(`/notifications/${notificationId}/read`, {});
  },
  markAllRead(): Promise<{ marked: number }> {
    return apiClient.post<{ marked: number }>("/notifications/read-all", {});
  },

  // Manuscript search
  search(projectId: string, q: string): Promise<SearchResponse> {
    return apiClient.get<SearchResponse>(`/projects/${projectId}/search`, { q });
  },

  // Bookmarks
  listBookmarks(projectId: string): Promise<Bookmark[]> {
    return apiClient.get<Bookmark[]>(`/projects/${projectId}/bookmarks`);
  },
  createBookmark(projectId: string, payload: { chapter_id?: string | null; title: string; note?: string | null }): Promise<Bookmark> {
    return apiClient.post<Bookmark>(`/projects/${projectId}/bookmarks`, payload);
  },
  deleteBookmark(bookmarkId: string): Promise<unknown> {
    return apiClient.delete<unknown>(`/bookmarks/${bookmarkId}`);
  },

  // Project stage
  setStage(projectId: string, stage: ProjectStage): Promise<StageResponse> {
    return apiClient.put<StageResponse>(`/projects/${projectId}/stage`, { stage });
  },

  // AI assistant
  assistant(projectId: string, request: AssistantRequest): Promise<AssistantResponse> {
    return apiClient.post<AssistantResponse>(`/projects/${projectId}/assistant`, request);
  },

  // Images (Pollinations)
  listImages(projectId: string): Promise<GeneratedImage[]> {
    return apiClient.get<GeneratedImage[]>(`/projects/${projectId}/images`);
  },
  generateImage(
    projectId: string,
    payload: { prompt: string; aspect_ratio?: string; style?: string; chapter_id?: string | null },
  ): Promise<GeneratedImage> {
    return apiClient.post<GeneratedImage>(`/projects/${projectId}/images`, payload);
  },

  // Per-user provider keys
  keyStatus(): Promise<ProviderKeyStatus> {
    return apiClient.get<ProviderKeyStatus>("/settings/ai/key-status");
  },
  saveKey(provider: string, api_key: string): Promise<ProviderKeyStatus> {
    return apiClient.put<ProviderKeyStatus>("/settings/ai/key", { provider, api_key });
  },
};
