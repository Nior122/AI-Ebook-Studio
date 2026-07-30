// Workspaces API module. The app currently operates within a single default
// workspace per user; these helpers fetch/create the workspace needed to create
// projects (the backend requires `workspace_id` on project creation).

import { apiClient } from "@/lib/api";
import type { Workspace } from "@/types";

export const workspacesApi = {
  list(): Promise<Workspace[]> {
    return apiClient.get<Workspace[]>("/workspaces");
  },

  create(name: string): Promise<Workspace> {
    return apiClient.post<Workspace>("/workspaces", { name });
  },

  /**
   * Return the user's first workspace, creating one named "My Workspace" if
   * none exists yet. Keeps project creation frictionless for new users.
   */
  async ensureDefault(): Promise<Workspace> {
    const existing = await this.list();
    if (existing.length > 0) return existing[0];
    return this.create("My Workspace");
  },
};
