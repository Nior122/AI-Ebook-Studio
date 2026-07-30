// Projects page tests: renders a project list, opens the create dialog,
// validates input, and confirms deletion via a dialog.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import ProjectsPage from "@/app/(dashboard)/projects/page";
import * as projectsHooks from "@/hooks/use-projects";
import { renderWithProviders } from "./test-utils";

const sampleProjects = [
  {
    id: "p1",
    workspace_id: "w1",
    owner_user_id: "u1",
    name: "My Book",
    title: "My Book Title",
    description: "A test book",
    status: "active",
    is_favorite: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

describe("ProjectsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Stub the projects hooks with controllable implementations.
    vi.spyOn(projectsHooks, "useProjects").mockReturnValue({
      data: sampleProjects,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as never);
    const mutate = vi.fn().mockResolvedValue(undefined);
    vi.spyOn(projectsHooks, "useDeleteProject").mockReturnValue({ mutateAsync: mutate, isPending: false } as never);
    vi.spyOn(projectsHooks, "useArchiveProject").mockReturnValue({ mutateAsync: mutate, isPending: false } as never);
    vi.spyOn(projectsHooks, "useUpdateProject").mockReturnValue({ mutateAsync: mutate, isPending: false } as never);
    vi.spyOn(projectsHooks, "useCreateProject").mockReturnValue({ mutateAsync: mutate, isPending: false } as never);
  });

  it("renders the project list", () => {
    renderWithProviders(<ProjectsPage />);
    expect(screen.getByText("My Book")).toBeInTheDocument();
  });

  it("opens the create dialog from the New Book button", async () => {
    renderWithProviders(<ProjectsPage />);
    fireEvent.click(screen.getByRole("button", { name: /new book/i }));
    expect(await screen.findByText(/create a new book project/i)).toBeInTheDocument();
  });

  it("shows a confirmation dialog before deleting", async () => {
    renderWithProviders(<ProjectsPage />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(/delete project/i);
    expect(dialog).toHaveTextContent(/permanently deleted/i);
  });

  it("filters by search query", async () => {
    renderWithProviders(<ProjectsPage />);
    fireEvent.change(screen.getByLabelText(/search projects/i), {
      target: { value: "nonexistent" },
    });
    await waitFor(() =>
      expect(screen.getByText(/no matching projects/i)).toBeInTheDocument(),
    );
  });
});
