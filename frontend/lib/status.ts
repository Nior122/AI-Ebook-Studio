// Maps backend status strings to badge variants and labels for consistent
// display across project cards, the dashboard, and the workspace.

import type { BadgeProps } from "@/components/ui/badge";

type StatusStyle = { label: string; variant: NonNullable<BadgeProps["variant"]> };

export function projectStatusStyle(status: string): StatusStyle {
  switch (status) {
    case "active":
      return { label: "Active", variant: "success" };
    case "archived":
      return { label: "Archived", variant: "muted" };
    case "completed":
      return { label: "Completed", variant: "secondary" };
    case "draft":
      return { label: "Draft", variant: "warning" };
    default:
      return { label: status, variant: "outline" };
  }
}

export function bookStatusStyle(status: string): StatusStyle {
  switch (status) {
    case "completed":
      return { label: "Completed", variant: "success" };
    case "in_progress":
      return { label: "In progress", variant: "warning" };
    case "published":
      return { label: "Published", variant: "secondary" };
    default:
      return { label: "Draft", variant: "muted" };
  }
}
