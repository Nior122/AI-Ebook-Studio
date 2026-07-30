"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useRef } from "react";
import { setSessionToken } from "@/lib/api";

/** Syncs the Clerk session token into the module-level api client.
 *
 * Keeps the token fresh by re-syncing:
 * - Immediately when `isSignedIn` changes
 * - Every 30 seconds while signed in (tokens expire ~60s)
 */
export function ClerkTokenProvider({ children }: { children: React.ReactNode }) {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const syncRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isLoaded) return;

    async function syncToken() {
      if (!isSignedIn) {
        setSessionToken(null);
        return;
      }
      try {
        const token = await getToken();
        setSessionToken(token);
      } catch {
        setSessionToken(null);
      }
    }

    void syncToken();

    if (isSignedIn) {
      syncRef.current = setInterval(() => void syncToken(), 30_000);
    }

    return () => {
      if (syncRef.current) {
        clearInterval(syncRef.current);
        syncRef.current = null;
      }
    };
  }, [getToken, isSignedIn, isLoaded]);

  return <>{children}</>;
}
