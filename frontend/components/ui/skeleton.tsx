// Skeleton + Spinner — loading-state primitives. Use Skeleton for layout
// placeholders and Spinner for inline/in-button waiting states.

import * as React from "react";
import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}

function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span role="status" aria-live="polite" className="inline-flex items-center gap-2">
      <span
        className={cn(
          "h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent",
          className,
        )}
        aria-hidden="true"
      />
      {label ? <span className="text-sm">{label}</span> : null}
      <span className="sr-only">{label ?? "Loading"}</span>
    </span>
  );
}

export { Skeleton, Spinner };
