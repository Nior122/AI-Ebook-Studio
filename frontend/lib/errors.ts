// Friendly, actionable error messages.
// The backend returns structured errors ({detail, code}); this module turns
// them into plain-language explanations with a "how to fix it" hint, so users
// never see "Internal Server Error" or "Something went wrong".

import { ApiError } from "@/lib/api";

interface ErrorDetail {
  message?: string;
  code?: string;
  details?: unknown;
}

function readDetail(body: unknown): ErrorDetail | null {
  if (!body || typeof body !== "object") return null;
  const record = body as Record<string, unknown>;
  const detail = record.detail;
  if (typeof detail === "string") return { message: detail };
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    return {
      message: typeof d.message === "string" ? d.message : undefined,
      code: typeof d.code === "string" ? d.code : undefined,
      details: d.details,
    };
  }
  if (typeof record.message === "string") return { message: record.message };
  return null;
}

export function friendlyError(error: unknown): { title: string; description: string } {
  if (error instanceof ApiError) {
    const detail = readDetail(error.body);
    const message = detail?.message ?? error.message;
    const code = detail?.code;

    if (error.status === 0) {
      return {
        title: "Can't reach the server",
        description: "The backend isn't responding. Check that it's running (uvicorn) and reload.",
      };
    }
    if (error.status === 401) {
      return {
        title: "You're signed out",
        description: "Please sign in again — your session expired.",
      };
    }
    if (error.status === 403) {
      return {
        title: "Not allowed",
        description: "You don't have permission to do that on this project.",
      };
    }
    if (error.status === 404) {
      return {
        title: "Not found",
        description: message || "This project or resource no longer exists.",
      };
    }
    if (error.status === 422) {
      return {
        title: "Check the form",
        description: message || "Some fields are missing or invalid — review and try again.",
      };
    }
    if (code === "AI_PROVIDER_NOT_CONFIGURED" || /api key|provider/i.test(message)) {
      return {
        title: "AI provider not configured",
        description:
          "This action needs an AI key. Add one in Settings → AI or in the New Book wizard — the local engine covers generation, proofreading, and covers without a key.",
      };
    }
    if (error.status >= 500) {
      return {
        title: "The server hit a problem",
        description:
          "Something went wrong on our side. Try again in a moment — your work is auto-saved.",
      };
    }
    return { title: "Couldn't complete that", description: message };
  }

  if (error instanceof Error && error.message) {
    return { title: "Couldn't complete that", description: error.message };
  }
  return {
    title: "Unexpected error",
    description: "Something unexpected happened. Please try again.",
  };
}

/** Convenience: toast-compatible error object for useToast(). */
export function toastError(error: unknown): { title: string; description: string; variant: "error" } {
  const friendly = friendlyError(error);
  return { ...friendly, variant: "error" };
}
