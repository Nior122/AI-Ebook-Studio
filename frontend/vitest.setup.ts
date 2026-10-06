// Vitest setup: registers jest-dom matchers and shared Clerk test doubles.
// The mocks keep component tests independent of Clerk's hosted auth service;
// they do not simulate the provider's authentication flow.

import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Clerk is mocked so components can be tested without a configured Clerk app.
// Auth state is a spy so individual tests can match the actual useAuth contract.
vi.mock("@clerk/nextjs", () => ({
  useUser: vi.fn(() => ({
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
  })),
  useAuth: vi.fn(() => ({
    isLoaded: true,
    isSignedIn: true,
    userId: "test_user_id",
    sessionId: "test_session_id",
    getToken: vi.fn(),
    signOut: vi.fn(),
  })),
  useClerk: vi.fn(() => ({
    signOut: vi.fn(),
    openSignIn: vi.fn(),
    openSignUp: vi.fn(),
  })),
  ClerkProvider: ({ children }: { children: React.ReactNode }) => children,
  SignedIn: ({ children }: { children: React.ReactNode }) => children,
  SignedOut: () => null,
  SignIn: () => "Clerk sign-in widget",
  SignUp: () => "Clerk sign-up widget",
}));

afterEach(() => {
  cleanup();
  localStorage.clear();
});
