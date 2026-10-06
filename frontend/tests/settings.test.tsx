import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import SettingsPage from "@/app/(dashboard)/settings/page";
import { renderWithProviders } from "./test-utils";

afterEach(() => {
  document.documentElement.classList.remove("dark");
});

describe("SettingsPage", () => {
  it("renders the account profile and default book preferences", async () => {
    renderWithProviders(<SettingsPage />);

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(await screen.findByLabelText("Display name")).toHaveValue("Test User");
    expect(screen.getByLabelText("Email")).toHaveValue("test@example.com");
    expect(screen.getByLabelText("Default export format")).toHaveValue("docx");
    expect(screen.getByLabelText("Default writing language")).toHaveValue("en");
  });

  it("persists export preferences across a page remount", async () => {
    const firstRender = renderWithProviders(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("Default export format"), {
      target: { value: "epub" },
    });

    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem("ebook:prefs") ?? "{}")).toEqual({
        defaultExportFormat: "epub",
      });
    });
    firstRender.unmount();

    renderWithProviders(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("Default export format")).toHaveValue("epub");
    });
  });

  it("toggles and persists the selected theme", async () => {
    renderWithProviders(<SettingsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Dark mode" }));

    expect(document.documentElement).toHaveClass("dark");
    expect(localStorage.getItem("ebook:theme")).toBe("dark");
    expect(screen.getByRole("button", { name: "Light mode" })).toBeInTheDocument();
  });
});
