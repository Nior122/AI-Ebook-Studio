// Protected route guard: unauthenticated users are redirected to /login;
// authenticated users see their children.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { Protected } from "@/components/layouts/protected";
import { mockRouter, renderWithProviders } from "./test-utils";

describe("Protected", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects unauthenticated users to /login", async () => {
    const { replace } = mockRouter();
    renderWithProviders(<Protected>Secret</Protected>, { auth: { status: "unauthenticated" } });
    await waitFor(() => expect(replace).toHaveBeenCalledWith(expect.stringContaining("/login")));
  });

  it("renders children for authenticated users", () => {
    mockRouter();
    renderWithProviders(<Protected>Secret content</Protected>, {
      auth: { status: "authenticated" },
    });
    expect(screen.getByText("Secret content")).toBeInTheDocument();
  });

  it("shows a loading state while resolving the session", () => {
    mockRouter();
    renderWithProviders(<Protected>Secret</Protected>, { auth: { status: "loading" } });
    expect(screen.getAllByText(/loading your workspace/i).length).toBeGreaterThan(0);
  });
});
