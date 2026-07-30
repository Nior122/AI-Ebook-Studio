// Workflow module registry for the project workspace. Single source of truth
// for the 10-stage pipeline shown in the sidebar nav and the overview cards.
// Each module is a placeholder for a future AI engine; only the shell and
// (for formatting) the real settings page exist today.

import {
  IconPen,
  IconLayout,
  IconImage,
  IconCheck,
  IconCover,
  IconProof,
  IconTranslate,
  IconMarketing,
  IconExport,
} from "@/components/ui/icons";

export interface WorkflowModule {
  id: string;
  title: string;
  description: string;
  href: string;
  icon: (props: React.SVGProps<SVGSVGElement>) => React.ReactElement;
}

export const WORKFLOW_MODULES: WorkflowModule[] = [
  {
    id: "writing",
    title: "Write",
    description: "Draft and structure your manuscript chapter by chapter.",
    href: "writing",
    icon: IconPen,
  },
  {
    id: "editing",
    title: "Edit",
    description: "Refine prose, tighten pacing, and improve clarity.",
    href: "editing",
    icon: IconPen,
  },
  {
    id: "images",
    title: "Images",
    description: "Analyze your book and intelligently place relevant images.",
    href: "images",
    icon: IconImage,
  },
  {
    id: "formatting",
    title: "Format",
    description: "Set page size, margins, typography, and image layout.",
    href: "formatting",
    icon: IconLayout,
  },
  {
    id: "validator",
    title: "KDP Validation",
    description: "Check your manuscript against KDP publishing requirements.",
    href: "validator",
    icon: IconCheck,
  },
  {
    id: "cover",
    title: "Cover",
    description: "Generate a professional, genre-appropriate book cover.",
    href: "cover",
    icon: IconCover,
  },
  {
    id: "proofreader",
    title: "Proofread",
    description: "Catch grammar, spelling, and consistency issues.",
    href: "proofreader",
    icon: IconProof,
  },
  {
    id: "translation",
    title: "Translate",
    description: "Translate your book into additional languages.",
    href: "translation",
    icon: IconTranslate,
  },
  {
    id: "marketing",
    title: "Marketing",
    description: "Create blurbs, ads, and social posts for your book.",
    href: "marketing",
    icon: IconMarketing,
  },
  {
    id: "exports",
    title: "Export",
    description: "Export to DOCX, PDF, and EPUB for publishing.",
    href: "exports",
    icon: IconExport,
  },
];

export type ModuleStatus = "not_started" | "in_progress" | "completed" | "needs_attention";

export const MODULE_STATUS_LABEL: Record<ModuleStatus, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  completed: "Completed",
  needs_attention: "Needs Attention",
};
