"use client";

// Dashboard. Welcomes the user, surfaces key stats derived from real project
// data, and lists recent projects with a shortcut to create more.

import Link from "next/link";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/states/states";
import { IconPlus, IconBook, IconProjects, IconCheck, IconExport } from "@/components/ui/icons";
import { useProjects } from "@/hooks/use-projects";
import { useUser } from "@clerk/nextjs";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { useRouter } from "next/navigation";
import { projectStatusStyle } from "@/lib/status";

function StatCard({
  label,
  value,
  icon,
  hint,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-secondary text-foreground">
          {icon}
        </div>
        <div>
          <p className="text-2xl font-semibold tracking-tight">{value}</p>
          <p className="text-sm text-muted-foreground">{label}</p>
          {hint ? <p className="text-xs text-muted-foreground/70">{hint}</p> : null}
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { user } = useUser();
  const { data, isLoading, isError, refetch } = useProjects();
  const [createOpen, setCreateOpen] = useState(false);
  const router = useRouter();

  const stats = useMemo(() => {
    const list = data ?? [];
    const booksInProgress = list.filter((p) => p.status === "active" || p.status === "draft").length;
    const completed = list.filter((p) => p.status === "completed").length;
    const archived = list.filter((p) => p.status === "archived").length;
    return { total: list.length, booksInProgress, completed, archived };
  }, [data]);

  const recent = useMemo(() => (data ?? []).slice(0, 5), [data]);

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Welcome back{user?.fullName ? `, ${user.fullName}` : ""}
          </h1>
          <p className="text-sm text-muted-foreground">
            Here&apos;s what&apos;s happening across your books.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <IconPlus className="h-4 w-4" />
          New Book
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total Projects" value={stats.total} icon={<IconProjects className="h-5 w-5" />} />
        <StatCard
          label="Books In Progress"
          value={stats.booksInProgress}
          icon={<IconBook className="h-5 w-5" />}
        />
        <StatCard
          label="Completed Books"
          value={stats.completed}
          icon={<IconCheck className="h-5 w-5" />}
        />
        <StatCard
          label="Archived"
          value={stats.archived}
          icon={<IconExport className="h-5 w-5" />}
        />
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">Recent projects</h2>
          <Link href="/projects" className="text-sm font-medium text-primary hover:underline">
            View all
          </Link>
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full rounded-lg" />
            ))}
          </div>
        ) : isError ? (
          <ErrorState message="We couldn't load your projects." onRetry={() => void refetch()} />
        ) : recent.length === 0 ? (
          <EmptyState
            icon={<IconBook />}
            title="No projects yet"
            description="Create your first book project to get started."
            action={{ label: "Create your first book", onClick: () => setCreateOpen(true) }}
          />
        ) : (
          <div className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card">
            {recent.map((project) => {
              const status = projectStatusStyle(project.status);
              return (
                <Link
                  key={project.id}
                  href={`/workspace/${project.id}`}
                  className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-secondary/50"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{project.name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {project.title || "Untitled book"}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
                    {status.label}
                  </span>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      <CreateProjectDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(id) => {
          setCreateOpen(false);
          router.push(`/workspace/${id}`);
        }}
      />
    </div>
  );
}
