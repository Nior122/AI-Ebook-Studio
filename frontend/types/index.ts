// Frontend type definitions.
// Project-specific types that are NOT shared with the backend live here.
// Types that represent API contracts and must stay in sync with the backend
// live in ../../shared so both sides import a single source of truth.

import type { ApiHealth } from "@shared/types/api";

// Re-export shared API contracts so feature code imports from one alias.
export type { ApiHealth } from "@shared/types/api";

// Re-export frontend API contract types for convenient imports.
export * from "./api";

/** Generic envelope used by list endpoints once pagination lands. */
export type Result<T> = T | T[];

/** Convenience: the health shape used by the landing page. */
export type HealthState = ApiHealth;
