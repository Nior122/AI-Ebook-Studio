"use client";

// Project card. Shows the project name, description, status, last-updated date,
// and book title when available. Exposes rename/open/archive/delete actions via
// a dropdown menu rendered by the parent (to keep destructive handling central).

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { IconBook } from "@/components/ui/icons";
import { projectStatusStyle } from "@/lib/status";
import type { Project } from "@/types";

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "";
  }
}

interface ProjectCardProps {
  project: Project;
  bookTitle?: string | null;
  onOpen: () => void;
  onRename: () => void;
  onArchive: () => void;
  onDelete: () => void;
}

export function ProjectCard({
  project,
  bookTitle,
  onOpen,
  onRename,
  onArchive,
  onDelete,
}: ProjectCardProps) {
  const status = projectStatusStyle(project.status);

  return (
    <Card className="flex flex-col transition-shadow hover:shadow-md">
      <CardContent className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex items-start justify-between gap-2">
          <button
            onClick={onOpen}
            className="text-left text-base font-semibold tracking-tight text-foreground hover:text-primary"
          >
            {project.name}
          </button>
          <Badge variant={status.variant}>{status.label}</Badge>
        </div>

        {project.description ? (
          <p className="line-clamp-2 text-sm text-muted-foreground">{project.description}</p>
        ) : null}

        <div className="mt-auto space-y-2 pt-2">
          {bookTitle ? (
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <IconBook className="h-4 w-4 shrink-0" />
              <span className="truncate">{bookTitle}</span>
            </p>
          ) : null}
          <p className="text-xs text-muted-foreground">
            Updated {formatDate(project.updated_at)}
          </p>
        </div>

        <div className="flex items-center gap-2 border-t border-border pt-3">
          <Link
            href={`/workspace/${project.id}`}
            className="text-sm font-medium text-primary hover:underline"
          >
            Open
          </Link>
          <span className="text-muted-foreground">·</span>
          <button onClick={onRename} className="text-sm text-muted-foreground hover:text-foreground">
            Rename
          </button>
          <span className="text-muted-foreground">·</span>
          <button onClick={onArchive} className="text-sm text-muted-foreground hover:text-foreground">
            Archive
          </button>
          <span className="text-muted-foreground">·</span>
          <button
            onClick={onDelete}
            className="text-sm text-destructive/80 hover:text-destructive"
          >
            Delete
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
