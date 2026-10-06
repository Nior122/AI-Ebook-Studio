// Shared test utilities: a render harness that wraps components with providers
// needed for testing. Clerk is mocked at the module level in vitest.setup.ts.
// `next/navigation` is aliased to a jsdom-safe stub in vitest.config.ts;
// `routerSpies` exposes the stub's router methods so tests can assert navigation calls.

import { type ReactElement, type ReactNode } from "react";
import { useAuth } from "@clerk/nextjs";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";
import { ToastProvider } from "@/components/ui/toast";

// The stubbed `next/navigation` useRouter returns a single shared object whose
// methods are vi.fn() spies, so tests can assert on navigation.
import * as navStub from "./stubs/next-navigation";

export const routerSpies = navStub.useRouter() as {
  replace: (href: string) => void;
  push: (href: string) => void;
};

export function mockRouter() {
  return routerSpies;
}

export function mockClerkAuthState(
  state: { isLoaded: boolean; isSignedIn?: boolean },
) {
  vi.mocked(useAuth).mockReturnValue({
    isLoaded: state.isLoaded,
    isSignedIn: state.isLoaded ? state.isSignedIn ?? true : undefined,
    userId: state.isSignedIn === false ? null : "test_user_id",
    sessionId: state.isSignedIn === false ? null : "test_session_id",
    getToken: vi.fn(),
    signOut: vi.fn(),
  } as unknown as ReturnType<typeof useAuth>);
}

export function renderWithProviders(
  ui: ReactElement,
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );

  return render(ui, { wrapper: Wrapper });
}
