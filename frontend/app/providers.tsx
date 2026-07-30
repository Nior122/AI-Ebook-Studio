"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { type ReactNode, useState } from "react";
import { makeQueryClient } from "@/lib/query-client";
import { ToastProvider } from "@/components/ui/toast";
import { ClerkTokenProvider } from "@/components/auth/clerk-token-provider";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient(new QueryClient()));

  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ClerkTokenProvider>{children}</ClerkTokenProvider>
      </ToastProvider>
      {process.env.NODE_ENV === "development" ? (
        <ReactQueryDevtools initialIsOpen={false} />
      ) : null}
    </QueryClientProvider>
  );
}
