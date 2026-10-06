import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { Protected } from "@/components/layouts/protected";
import { mockClerkAuthState, mockRouter, renderWithProviders } from "./test-utils";

describe("Protected", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockClerkAuthState({ isLoaded: true, isSignedIn: true });
    window.history.replaceState({}, "", "/");
  });

  it("redirects unauthenticated users to sign-in with a return URL", async () => {
    const { replace } = mockRouter();
    window.history.replaceState({}, "", "/projects");
    mockClerkAuthState({ isLoaded: true, isSignedIn: false });

    renderWithProviders(<Protected>Secret</Protected>);

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/sign-in?redirect_url=%2Fprojects");
    });
    expect(screen.queryByText("Secret")).not.toBeInTheDocument();
  });

  it("renders children for authenticated users", () => {
    mockRouter();

    renderWithProviders(<Protected>Secret content</Protected>);

    expect(screen.getByText("Secret content")).toBeInTheDocument();
  });

  it("shows a loading state while Clerk resolves the session", () => {
    mockRouter();
    mockClerkAuthState({ isLoaded: false });

    renderWithProviders(<Protected>Secret</Protected>);

    expect(screen.getByRole("status")).toHaveTextContent(/loading your workspace/i);
    expect(screen.queryByText("Secret")).not.toBeInTheDocument();
  });
});
