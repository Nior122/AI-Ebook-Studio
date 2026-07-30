// Login form tests: inline validation and successful submission.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "@/app/(auth)/login/page";
import { mockRouter, renderWithProviders } from "./test-utils";

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRouter();
  });

  it("shows validation errors for empty fields", async () => {
    renderWithProviders(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
    expect(screen.getByText(/password is required/i)).toBeInTheDocument();
  });

  it("calls login and redirects on success", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    const { replace } = mockRouter();
    renderWithProviders(<LoginPage />, { auth: { login } });

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "author@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^password/i), {
      target: { value: "SecurePass123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(login).toHaveBeenCalledWith({
      email: "author@example.com",
      password: "SecurePass123",
    }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("shows a server error message on failure", async () => {
    const login = vi.fn().mockRejectedValue(new Error("boom"));
    mockRouter();
    renderWithProviders(<LoginPage />, { auth: { login } });

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "author@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^password/i), {
      target: { value: "SecurePass123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/couldn't sign you in/i)).toBeInTheDocument();
  });
});
