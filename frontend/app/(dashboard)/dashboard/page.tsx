"use client";

// Dashboard — your books at a glance. Search, stage badges, one-click open.
// "New Book" starts the guided wizard; every project opens in the unified
// workspace.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  useProjects,
  useArchiveProject,
  useDeleteProject,
  useDuplicateProject,
  useRestoreProject,
} from "@/hooks/use-projects";
import { useToast } from "@/components/ui/toast";
import { toastError } from "@/lib/errors";
import { STAGE_LABELS, type ProjectStage } from "@/lib/api/studio";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton, Spinner } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/states/states";
import { IconPlus, IconSearch, IconBook, IconSparkles } from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import type { Project } from "@/types";

const STAGE_CHIPS: Record<string, string> = {
  draft: "bg-secondary text-secondary-foreground",
  generating: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
  review: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  ready_for_export: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  published: "bg-purple-500/10 text-purple-700 dark:text-purple-300",
};

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return "";
  }
}

export default function DashboardPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const { data: projects, isLoading, isError, refetch } = useProjects();
  const toast = useToast();
  const archiveProject = useArchiveProject();
  const restoreProject = useRestoreProject();
  const duplicateProject = useDuplicateProject();
  const deleteProject = useDeleteProject();

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return projects ?? [];
    return (projects ?? []).filter((project) =>
      [project.name, project.title, project.description ?? ""].some((field) =>
        field.toLowerCase().includes(needle),
      ),
    );
  }, [projects, search]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">Your books</h1>
          <p className="text-sm text-muted-foreground">
            Every project opens in one workspace — write, review, validate, and export.
          </p>
        </div>
        <Button onClick={() => router.push("/new-book")}>
          <IconPlus className="mr-1.5 h-4 w-4" />
          New Book
        </Button>
      </div>

      <div className="relative max-w-sm">
        <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search your books…"
          className="pl-9"
        />
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-36 rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState
          title="Couldn't load your books"
          message="The backend may be offline. Try again in a moment."
          onRetry={() => void refetch()}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<IconBook className="h-8 w-8" />}
          title={search ? "No books match your search" : "Start your first book"}
          description={
            search
              ? "Try a different title, topic, or keyword."
              : "Tell the AI what to write and it plans, drafts, formats, and validates the whole book."
          }
          action={
            search ? undefined : { label: "Create a book", onClick: () => router.push("/new-book") }
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((project: Project) => {
            const stage = (STAGE_LABELS[project.stage as ProjectStage] ? project.stage : "draft") as ProjectStage;
            return (
              <Card key={project.id} className="flex flex-col transition-shadow hover:shadow-md">
                <CardContent className="flex flex-1 flex-col gap-3 p-5">
                  <div className="flex items-start justify-between gap-2">
                    <button
                      onClick={() => router.push(`/workspace/${project.id}`)}
                      className="text-left text-base font-semibold tracking-tight text-foreground hover:text-primary"
                    >
                      {project.name}
                    </button>
                    <span
                      className={cn(
                        "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium",
                        STAGE_CHIPS[stage],
                      )}
                    >
                      {STAGE_LABELS[stage]}
                    </span>
                  </div>

                  {project.description ? (
                    <p className="line-clamp-2 text-sm text-muted-foreground">{project.description}</p>
                  ) : null}

                  <div className="mt-auto space-y-2 pt-2">
                    <p className="text-xs text-muted-foreground">
                      Updated {formatDate(project.updated_at)}
                    </p>
                    {stage === "generating" ? (
                      <p className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-300">
                        <Spinner className="h-3 w-3" />
                        Generating in the background…
                      </p>
                    ) : null}
                  </div>

                  <div className="flex items-center gap-2 border-t border-border pt-3">
                    <Button size="sm" variant="outline" className="flex-1" onClick={() => router.push(`/workspace/${project.id}`)}>
                      Open workspace
                    </Button>
                    {stage === "draft" ? (
                      <Button
                        size="sm"
                        className="flex-1"
                        onClick={() => router.push(`/workspace/${project.id}`)}
                        title="Generate the book from this project"
                      >
                        <IconSparkles className="mr-1 h-3.5 w-3.5" />
                        Generate
                      </Button>
                    ) : null}
                  </div>
                  <div className="flex items-center justify-between pt-1">
                    <div className="flex items-center gap-1">
                      {project.status === "archived" ? (
                        <button
                          className="rounded px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground hover:bg-secondary hover:text-foreground"
                          onClick={() =>
                            restoreProject.mutate(project.id, {
                              onSuccess: () => toast({ title: "Project restored", variant: "success" }),
                              onError: (error) => toast(toastError(error)),
                            })
                          }
                        >
                          Restore
                        </button>
                      ) : (
                        <button
                          className="rounded px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground hover:bg-secondary hover:text-foreground"
                          onClick={() =>
                            archiveProject.mutate(project.id, {
                              onSuccess: () => toast({ title: "Project archived", variant: "success" }),
                              onError: (error) => toast(toastError(error)),
                            })
                          }
                        >
                          Archive
                        </button>
                      )}
                      <button
                        className="rounded px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground hover:bg-secondary hover:text-foreground"
                        onClick={() =>
                          duplicateProject.mutate(project.id, {
                            onSuccess: () => toast({ title: "Project duplicated", variant: "success" }),
                            onError: (error) => toast(toastError(error)),
                          })
                        }
                      >
                        Duplicate
                      </button>
                    </div>
                    <button
                      className="rounded px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground hover:bg-red-50 hover:text-red-600"
                      onClick={() => {
                        if (window.confirm(`Delete "${project.name}"? It can be restored from the archive.`)) {
                          deleteProject.mutate(project.id, {
                            onSuccess: () => toast({ title: "Project deleted", variant: "success" }),
                            onError: (error) => toast(toastError(error)),
                          });
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
