// Registration form tests: validation (email, password length, match) and
// successful submission flow.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import RegisterPage from "@/app/(auth)/register/page";
import { mockRouter, renderWithProviders } from "./test-utils";

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRouter();
  });

  it("validates mismatched passwords", async () => {
    renderWithProviders(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Jane" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: "SecurePass123" } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "Different123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText(/passwords do not match/i)).toBeInTheDocument();
  });

  it("validates short passwords", async () => {
    renderWithProviders(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Jane" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: "short" } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    const errors = await screen.findAllByText(/at least 8 characters/i);
    expect(errors.length).toBeGreaterThan(0);
  });

  it("registers and redirects on success", async () => {
    const register = vi.fn().mockResolvedValue(undefined);
    const { replace } = mockRouter();
    renderWithProviders(<RegisterPage />, { auth: { register } });

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Jane Author" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: "SecurePass123" } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "SecurePass123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() =>
      expect(register).toHaveBeenCalledWith({
        display_name: "Jane Author",
        email: "jane@example.com",
        password: "SecurePass123",
      }),
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });
});
