"use client";

// Root route. Redirects authenticated users to the dashboard and everyone else
// to the sign-in screen. Keeps a single entry point regardless of session state.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import { Spinner } from "@/components/ui/skeleton";

export default function HomePage() {
  const router = useRouter();
  const { isLoaded, isSignedIn } = useUser();

  useEffect(() => {
    if (!isLoaded) return;
    if (isSignedIn) router.replace("/dashboard");
    else router.replace("/sign-in");
  }, [isLoaded, isSignedIn, router]);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <Spinner label="Loading AI Ebook Studio…" />
    </main>
  );
}
