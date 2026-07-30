"use client";

// Project workspace layout. Loads the project + its book, renders the workspace
// header (title, status, progress, actions) and a workflow module sub-nav, then
// renders the active module page in the content area. A secondary "activity"
// column is reserved for future live data.

import { notFound } from "next/navigation";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { use, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/states/states";
import { IconSettings, IconBook } from "@/components/ui/icons";
import { useProject } from "@/hooks/use-projects";
import { useProjectBook } from "@/hooks/use-books";
import { WORKFLOW_MODULES } from "@/components/projects/workflow-modules";
import { bookStatusStyle } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

function ModuleNav({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 overflow-x-auto pb-2" aria-label="Workflow modules">
      {WORKFLOW_MODULES.map((m) => {
        const href = `/projects/${projectId}/${m.href}`;
        const active = pathname === href;
        const Icon = m.icon;
        return (
          <Link
            key={m.id}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              active
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            {m.title}
          </Link>
        );
      })}
    </nav>
  );
}

export default function ProjectWorkspaceLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const { data: project, isLoading, isError, refetch } = useProject(projectId);
  const { data: book } = useProjectBook(projectId);
  const [showActivity, setShowActivity] = useState(true);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full rounded-lg" />
        <Skeleton className="h-10 w-full rounded-lg" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    );
  }

  if (isError || !project) {
    if (isError && !project) notFound();
    return <ErrorState message="We couldn't load this project." onRetry={() => void refetch()} />;
  }

  const bookStatus = book ? bookStatusStyle(book.status) : null;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <IconBook className="h-4 w-4" />
            <span className="truncate">{project.name}</span>
          </div>
          <h1 className="mt-1 truncate text-2xl font-semibold tracking-tight">
            {book?.title ?? project.title ?? "Untitled book"}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge variant={bookStatus?.variant ?? "muted"}>
              {bookStatus?.label ?? "No book yet"}
            </Badge>
            {book?.author_name ? (
              <span className="text-sm text-muted-foreground">by {book.author_name}</span>
            ) : null}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/projects/${projectId}/formatting`}>
            <Button variant="outline" size="sm">
              <IconSettings className="h-4 w-4" />
              Book Settings
            </Button>
          </Link>
        </div>
      </div>

      {/* Module sub-nav */}
      <ModuleNav projectId={projectId} />

      {/* Content + secondary area */}
      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        <div className="min-w-0">{children}</div>
        <aside className="hidden lg:block">
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Recent activity</h2>
              <button
                onClick={() => setShowActivity((s) => !s)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                {showActivity ? "Hide" : "Show"}
              </button>
            </div>
            {showActivity ? (
              <p className="text-sm text-muted-foreground">
                Activity will appear here as you write, generate images, and export your book.
              </p>
            ) : null}
          </div>
        </aside>
      </div>
    </div>
  );
}
