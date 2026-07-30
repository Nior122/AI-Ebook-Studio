"use client";

// Projects page. Grid of project cards with search, status filter, and sort.
// Create/delete/archive are wired through dialogs; rename uses a small modal.
// Empty and loading states are handled explicitly — never a blank screen.

import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogFooter, DialogHeader } from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Field } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/states/states";
import { IconPlus, IconSearch, IconBook } from "@/components/ui/icons";
import { ProjectCard } from "@/components/projects/project-card";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import {
  useProjects,
  useDeleteProject,
  useArchiveProject,
  useUpdateProject,
} from "@/hooks/use-projects";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api";
import type { Project } from "@/types";

type StatusFilter = "all" | "active" | "draft" | "completed" | "archived";
type SortKey = "recent" | "name" | "status";

export default function ProjectsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sort, setSort] = useState<SortKey>("recent");

  const [createOpen, setCreateOpen] = useState(searchParams.get("new") === "1");
  const [renameTarget, setRenameTarget] = useState<Project | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<Project | null>(null);

  const { data, isLoading, isError, refetch } = useProjects();
  const deleteProject = useDeleteProject();
  const archiveProject = useArchiveProject();
  const updateProject = useUpdateProject();

  const projects = useMemo(() => {
    let list = data ?? [];
    if (statusFilter !== "all") list = list.filter((p) => p.status === statusFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          (p.description ?? "").toLowerCase().includes(q),
      );
    }
    const sorted = [...list];
    if (sort === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
    else if (sort === "status") sorted.sort((a, b) => a.status.localeCompare(b.status));
    else sorted.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return sorted;
  }, [data, statusFilter, search, sort]);

  async function confirmDelete() {
    if (!deleteTarget) return;
    try {
      await deleteProject.mutateAsync(deleteTarget.id);
      toast({ title: "Project deleted", variant: "success" });
    } catch (err) {
      toast({
        title: "Could not delete project",
        description: err instanceof ApiError ? err.message : undefined,
        variant: "error",
      });
    } finally {
      setDeleteTarget(null);
    }
  }

  async function confirmArchive() {
    if (!archiveTarget) return;
    try {
      await archiveProject.mutateAsync(archiveTarget.id);
      toast({ title: "Project archived", variant: "success" });
    } catch {
      toast({ title: "Could not archive project", variant: "error" });
    } finally {
      setArchiveTarget(null);
    }
  }

  async function confirmRename() {
    if (!renameTarget || !renameValue.trim()) return;
    try {
      await updateProject.mutateAsync({
        id: renameTarget.id,
        payload: { name: renameValue.trim() },
      });
      toast({ title: "Project renamed", variant: "success" });
      setRenameTarget(null);
    } catch {
      toast({ title: "Could not rename project", variant: "error" });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="text-sm text-muted-foreground">
            Your books and their workspaces.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <IconPlus className="h-4 w-4" />
          New Book
        </Button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <IconSearch className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search projects…"
            className="pl-9"
            aria-label="Search projects"
          />
        </div>
        <Select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
          aria-label="Filter by status"
          className="sm:w-40"
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="draft">Draft</option>
          <option value="completed">Completed</option>
          <option value="archived">Archived</option>
        </Select>
        <Select
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
          aria-label="Sort projects"
          className="sm:w-40"
        >
          <option value="recent">Most recent</option>
          <option value="name">Name</option>
          <option value="status">Status</option>
        </Select>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="space-y-3 p-5">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : isError ? (
        <ErrorState message="We couldn't load your projects." onRetry={() => void refetch()} />
      ) : projects.length === 0 ? (
        <EmptyState
          icon={<IconBook />}
          title={data && data.length > 0 ? "No matching projects" : "No projects yet"}
          description={
            data && data.length > 0
              ? "Try a different search or filter."
              : "Create your first book project to get started."
          }
          action={
            data && data.length > 0
              ? undefined
              : { label: "Create your first book", onClick: () => setCreateOpen(true) }
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onOpen={() => router.push(`/workspace/${project.id}`)}
              onRename={() => {
                setRenameValue(project.name);
                setRenameTarget(project);
              }}
              onArchive={() => setArchiveTarget(project)}
              onDelete={() => setDeleteTarget(project)}
            />
          ))}
        </div>
      )}

      <CreateProjectDialog
        open={createOpen}
        onClose={() => {
          setCreateOpen(false);
          if (searchParams.get("new") === "1") router.replace("/projects");
        }}
        onCreated={(id) => {
          setCreateOpen(false);
          router.push(`/workspace/${id}`);
        }}
      />

      <Dialog
        open={Boolean(renameTarget)}
        onClose={() => setRenameTarget(null)}
        labelledBy="dialog-title"
      >
        <DialogHeader title="Rename project" />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void confirmRename();
          }}
          className="space-y-4"
        >
          <Field label="Project name" htmlFor="rename">
            <Input
              id="rename"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              autoFocus
            />
          </Field>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setRenameTarget(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateProject.isPending}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
        title="Delete project?"
        description={`"${deleteTarget?.name}" will be permanently deleted. This cannot be undone.`}
        confirmLabel="Delete"
        loading={deleteProject.isPending}
      />

      <ConfirmDialog
        open={Boolean(archiveTarget)}
        onClose={() => setArchiveTarget(null)}
        onConfirm={confirmArchive}
        title="Archive project?"
        description={`"${archiveTarget?.name}" will be moved to archived. You can still find it by filtering.`}
        confirmLabel="Archive"
        variant="default"
        loading={archiveProject.isPending}
      />
    </div>
  );
}
