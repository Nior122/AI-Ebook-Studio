// AI provider settings API module. Centralizes the AI discovery endpoints so
// the settings UI never calls `apiClient` ad-hoc and never receives secrets.

import { apiClient } from "@/lib/api";

export interface AIProviderInfo {
  name: string;
  available: boolean;
  healthy: boolean;
  models: string[];
  requires_key: boolean;
}

export interface AIModelInfo {
  key: string;
  provider: string;
  name: string;
  display_name: string;
  context_window: number | null;
  max_output_tokens: number | null;
  supports_streaming: boolean;
  supports_structured_output: boolean;
  supports_tools: boolean;
  supports_vision: boolean;
  status: string;
  input_cost_per_1m_tokens: number;
  output_cost_per_1m_tokens: number;
  tags: string[];
}

export interface AICapabilityInfo {
  key: string;
  provider: string;
  name: string;
  capabilities: Record<string, boolean>;
  context_window: number | null;
}

export interface AIProviderPreference {
  preferred_provider: string | null;
  preferred_model: string | null;
  fallback_provider: string | null;
  fallback_model: string | null;
  temperature: number;
  default_writing_style: string | null;
  default_language: string | null;
  stream_responses: boolean;
}

export const aiApi = {
  /** List configured providers (no secrets). */
  async listProviders(): Promise<AIProviderInfo[]> {
    return apiClient.get<AIProviderInfo[]>("/ai/providers");
  },

  /** List available models across configured providers. */
  async listModels(): Promise<AIModelInfo[]> {
    return apiClient.get<AIModelInfo[]>("/ai/models");
  },

  /** Capability matrix for building capability-aware UI. */
  async listCapabilities(): Promise<AICapabilityInfo[]> {
    return apiClient.get<AICapabilityInfo[]>("/ai/capabilities");
  },

  /** Get the current user's saved AI preferences. */
  async getPreferences(): Promise<AIProviderPreference> {
    return apiClient.get<AIProviderPreference>("/ai/preferences");
  },

  /** Save the current user's AI preferences. */
  async updatePreferences(
    prefs: Partial<AIProviderPreference>,
  ): Promise<AIProviderPreference> {
    return apiClient.put<AIProviderPreference>("/ai/preferences", { payload: prefs });
  },
};
