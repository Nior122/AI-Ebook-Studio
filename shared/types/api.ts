// Shared API contracts for shapes that both the Next.js frontend and FastAPI
// backend must agree on. The frontend imports these through the @shared/* alias.

export interface ApiHealth {
  app: string;
  status: "ok" | "degraded";
  environment: string;
  timestamp: string;
  database?: "connected" | "unavailable";
}

export type AiProviderId = "openai" | "anthropic" | "gemini" | "openrouter" | "local";

export type ImageProviderId = "pollinations";

export type DocumentFormatId = "docx" | "pdf" | "epub";
