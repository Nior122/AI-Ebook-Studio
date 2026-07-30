"use client";

// Project workspace overview. Presents the 10-stage workflow as clear module
// cards (icon, title, description, status, action). Each links to its module
// page. The formatting module is the only one with a working settings page
// today; the rest are intentional placeholders for future engines.

import Link from "next/link";
import { use } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { WORKFLOW_MODULES, MODULE_STATUS_LABEL, type ModuleStatus } from "@/components/projects/workflow-modules";

// Until the engines exist, every module starts as Not Started. This is the only
// honest initial state — no fabricated progress.
const INITIAL_STATUS: ModuleStatus = "not_started";

export default function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Your writing workflow</h2>
        <p className="text-sm text-muted-foreground">
          Move through the stages in order. Each module opens in its own workspace.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {WORKFLOW_MODULES.map((module) => {
          const Icon = module.icon;
          const statusLabel = MODULE_STATUS_LABEL[INITIAL_STATUS];
          return (
            <Card key={module.id} className="flex flex-col">
              <CardContent className="flex flex-1 flex-col gap-3 p-5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-foreground">
                    <Icon className="h-5 w-5" />
                  </div>
                  <Badge variant="muted">{statusLabel}</Badge>
                </div>
                <div>
                  <h3 className="text-base font-semibold tracking-tight">{module.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{module.description}</p>
                </div>
                <div className="mt-auto pt-2">
                  <Link href={`/projects/${projectId}/${module.href}`} className="block">
                    <Button variant="outline" className="w-full">
                      Open Module
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
