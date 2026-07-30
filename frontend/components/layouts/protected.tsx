"use client";

// Route guard for authenticated areas. While the session is resolving it shows
// a neutral loading screen; unauthenticated users are redirected to /sign-in.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Spinner } from "@/components/ui/skeleton";

export function Protected({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      const next = encodeURIComponent(window.location.pathname);
      router.replace(`/sign-in?redirect_url=${next}`);
    }
  }, [isLoaded, isSignedIn, router]);

  if (!isLoaded || !isSignedIn) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Spinner label="Loading your workspace…" />
      </div>
    );
  }

  return <>{children}</>;
}
