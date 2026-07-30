// Vitest setup: registers jest-dom matchers and silences noisy console output
// during tests. Imported automatically via vitest.config.ts `setupFiles`.

import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Mock @clerk/nextjs so component tests don't need the real Clerk instance.
vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({
    isLoaded: true,
    isSignedIn: true,
    user: {
      id: "test_user_id",
      fullName: "Test User",
      firstName: "Test",
      lastName: "User",
      primaryEmailAddress: { emailAddress: "test@example.com" },
      imageUrl: "",
    },
  }),
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: true,
    userId: "test_user_id",
    sessionId: "test_session_id",
    getToken: vi.fn(),
    signOut: vi.fn(),
  }),
  useClerk: () => ({
    signOut: vi.fn(),
    openSignIn: vi.fn(),
    openSignUp: vi.fn(),
  }),
  ClerkProvider: ({ children }: { children: React.ReactNode }) => children,
  SignedIn: ({ children }: { children: React.ReactNode }) => children,
  SignedOut: () => null,
}));

afterEach(() => {
  cleanup();
  localStorage.clear();
});
