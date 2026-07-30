// Shared placeholder for not-yet-built workflow modules. Keeps every module
// page consistent: a calm "coming soon" panel with the module's purpose and
// what will be possible later. Avoids dead links and sets expectations.

import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { IconSparkles } from "@/components/ui/icons";

interface ModulePlaceholderProps {
  title: string;
  description: string;
  icon: ReactNode;
  comingSoon?: boolean;
  children?: ReactNode;
}

export function ModulePlaceholder({
  title,
  description,
  icon,
  comingSoon = true,
  children,
}: ModulePlaceholderProps) {
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-secondary text-foreground">
          {icon}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
            {comingSoon ? (
              <Badge variant="warning">Coming soon</Badge>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </div>

      {children ? (
        children
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 p-10 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-foreground">
              <IconSparkles className="h-6 w-6" />
            </div>
            <p className="max-w-md text-sm text-muted-foreground">
              This module is part of the interface foundation. The AI engine behind it will
              connect here in a later phase — the workflow, navigation, and layout are ready now.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
