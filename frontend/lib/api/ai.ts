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

/** A user-supplied custom AI provider (never includes the plaintext key). */
export interface CustomAIProvider {
  id: string;
  name: string;
  provider_type: "openai_compatible" | "anthropic" | "gemini";
  base_url: string | null;
  model_ids: string[];
  default_model: string | null;
  supports_structured_output: boolean;
  is_active: boolean;
  has_key: boolean;
  provider_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** Input for creating/updating a custom provider. api_key is write-only. */
export interface CustomAIProviderInput {
  name: string;
  provider_type: "openai_compatible" | "anthropic" | "gemini";
  base_url?: string | null;
  api_key?: string | null;
  model_ids: string[];
  default_model?: string | null;
  supports_structured_output?: boolean;
  is_active?: boolean;
}

/** Result of a custom-provider connection test. */
export interface CustomProviderTestResult {
  ok: boolean;
  model: string | null;
  reply?: string;
  error?: string;
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

  // ---------------------------------------------------------------------
  // Custom (user-supplied) AI providers
  // ---------------------------------------------------------------------
  /** List the user's custom providers (keys masked). */
  async listCustomProviders(): Promise<CustomAIProvider[]> {
    return apiClient.get<CustomAIProvider[]>("/ai/custom-providers");
  },

  /** Create a custom provider. The API key is encrypted server-side. */
  async createCustomProvider(input: CustomAIProviderInput): Promise<CustomAIProvider> {
    return apiClient.post<CustomAIProvider>("/ai/custom-providers", { payload: input });
  },

  /** Update a custom provider. Omit api_key to keep the existing key. */
  async updateCustomProvider(
    id: string,
    input: CustomAIProviderInput,
  ): Promise<CustomAIProvider> {
    return apiClient.put<CustomAIProvider>(`/ai/custom-providers/${id}`, { payload: input });
  },

  /** Delete a custom provider. */
  async deleteCustomProvider(id: string): Promise<void> {
    await apiClient.delete(`/ai/custom-providers/${id}`);
  },

  /** Send a tiny completion through the provider to verify connectivity. */
  async testCustomProvider(id: string): Promise<CustomProviderTestResult> {
    return apiClient.post<CustomProviderTestResult>(`/ai/custom-providers/${id}/test`, {});
  },
};
