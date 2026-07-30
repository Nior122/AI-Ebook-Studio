// Small UI helper utilities shared across components.
// `cn` merges Tailwind class lists intelligently (conditional + de-dupes
// conflicting utilities via tailwind-merge) — the standard shadcn/ui pattern.

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge conditional class names and resolve Tailwind conflicts.
 * Usage: cn("px-2", isActive && "bg-primary", className)
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
