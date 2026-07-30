// Projects API module. Thin typed wrappers over the project endpoints.

import { apiClient } from "@/lib/api";
import type {
  Project,
  ProjectCreatePayload,
  ProjectUpdatePayload,
  MessageResponse,
} from "@/types";

export const projectsApi = {
  list(params?: { search?: string; status?: string; favorite?: boolean }): Promise<Project[]> {
    return apiClient.get<Project[]>("/projects", params);
  },

  get(id: string): Promise<Project> {
    return apiClient.get<Project>(`/projects/${id}`);
  },

  create(payload: ProjectCreatePayload): Promise<Project> {
    return apiClient.post<Project>("/projects", payload);
  },

  update(id: string, payload: ProjectUpdatePayload): Promise<Project> {
    return apiClient.patch<Project>(`/projects/${id}`, payload);
  },

  remove(id: string): Promise<MessageResponse> {
    return apiClient.delete<MessageResponse>(`/projects/${id}`);
  },

  archive(id: string): Promise<Project> {
    return apiClient.post<Project>(`/projects/${id}/archive`);
  },

  favorite(id: string): Promise<Project> {
    return apiClient.post<Project>(`/projects/${id}/favorite`);
  },
};
