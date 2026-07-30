// TanStack Query client factory.
// Centralizing the default options here keeps caching/retry policy in one place
// and lets both the client <Providers> and any test harness build identical clients.

import type { QueryClient } from "@tanstack/react-query";

/**
 * Configure a QueryClient with sensible production defaults.
 * Mutations and fetches are optimistic-friendly: stale data renders instantly
 * while a refetch happens in the background.
 */
export function makeQueryClient(client: QueryClient): QueryClient {
  client.setDefaultOptions({
    queries: {
      // Reasonable defaults for a SaaS UI: cached data is shown immediately and
      // refreshed in the background on focus/visibility — never blocks the UI.
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: 0,
    },
  });
  return client;
}
