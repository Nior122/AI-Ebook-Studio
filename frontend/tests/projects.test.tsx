// Dashboard tests: renders the book list with stage badges, filters by search,
// and navigates to the unified workspace when a book is opened.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import DashboardPage from "@/app/(dashboard)/dashboard/page";
import * as projectsHooks from "@/hooks/use-projects";
import { renderWithProviders, routerSpies } from "./test-utils";

const projects = [
  {
    id: "p1",
    workspace_id: "w1",
    owner_user_id: "u1",
    name: "The Startup Field Guide",
    title: "The Startup Field Guide",
    description: "Launching and growing a small software business",
    status: "active",
    stage: "review",
    is_favorite: false,
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-10T00:00:00Z",
  },
  {
    id: "p2",
    workspace_id: "w1",
    owner_user_id: "u1",
    name: "Cooking Fundamentals",
    title: "Cooking Fundamentals",
    description: null,
    status: "active",
    stage: "draft",
    is_favorite: false,
    created_at: "2026-07-02T00:00:00Z",
    updated_at: "2026-07-05T00:00:00Z",
  },
];

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(projectsHooks, "useProjects").mockReturnValue({
      data: projects,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as never);
  });

  it("renders books with their lifecycle stage badges", async () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("The Startup Field Guide")).toBeDefined();
    expect(screen.getByText("Cooking Fundamentals")).toBeDefined();
    expect(screen.getByText("Review")).toBeDefined();
    expect(screen.getByText("Draft")).toBeDefined();
  });

  it("opens the unified workspace when a book is clicked", async () => {
    renderWithProviders(<DashboardPage />);
    fireEvent.click(screen.getByText("The Startup Field Guide"));
    expect(routerSpies.push).toHaveBeenCalledWith("/workspace/p1");
  });

  it("filters books by search text", async () => {
    renderWithProviders(<DashboardPage />);
    fireEvent.change(screen.getByPlaceholderText("Search your books…"), {
      target: { value: "cooking" },
    });
    expect(screen.queryByText("The Startup Field Guide")).toBeNull();
    expect(screen.getByText("Cooking Fundamentals")).toBeDefined();
  });
});
