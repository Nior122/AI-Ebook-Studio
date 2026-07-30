"use client";

// Create-project modal. Captures project + book metadata, then orchestrates the
// backend flow: ensure a default workspace → create the project → create the
// book. Shows per-step progress and surfaces errors without leaving the modal.

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input, Textarea, Select } from "@/components/ui/input";
import { Dialog, DialogFooter, DialogHeader } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/skeleton";
import { workspacesApi } from "@/lib/api/workspaces";
import { projectsApi } from "@/lib/api/projects";
import { booksApi } from "@/lib/api/books";
import { useToast } from "@/components/ui/toast";
import {
  validateProjectForm,
  type ProjectFormErrors,
  type ProjectFormValues,
} from "@/lib/validations/project";
import { ApiError } from "@/lib/api";

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "pt", label: "Portuguese" },
  { value: "it", label: "Italian" },
  { value: "nl", label: "Dutch" },
  { value: "ja", label: "Japanese" },
  { value: "zh", label: "Chinese" },
];

const EMPTY: ProjectFormValues = {
  name: "",
  description: "",
  book_title: "",
  subtitle: "",
  author_name: "",
  language: "en",
  target_audience: "",
  writing_style: "",
};

type Step = "idle" | "creating" | "done" | "error";

interface CreateProjectDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (projectId: string) => void;
}

export function CreateProjectDialog({ open, onClose, onCreated }: CreateProjectDialogProps) {
  const toast = useToast();
  const [values, setValues] = useState<ProjectFormValues>(EMPTY);
  const [errors, setErrors] = useState<ProjectFormErrors>({});
  const [step, setStep] = useState<Step>("idle");
  const [serverError, setServerError] = useState<string | null>(null);

  function set<K extends keyof ProjectFormValues>(key: K, value: ProjectFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);
    const validation = validateProjectForm(values);
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;

    setStep("creating");
    try {
      const workspace = await workspacesApi.ensureDefault();
      const project = await projectsApi.create({
        workspace_id: workspace.id,
        name: values.name.trim(),
        title: values.book_title.trim(),
        description: values.description?.trim() || null,
      });
      await booksApi.createForProject(project.id, {
        title: values.book_title.trim(),
        subtitle: values.subtitle?.trim() || null,
        author_name: values.author_name?.trim() || null,
        language: values.language,
        target_audience: values.target_audience?.trim() || null,
        writing_style: values.writing_style?.trim() || null,
      });
      setStep("done");
      toast({ title: "Project created", variant: "success" });
      onCreated(project.id);
      setValues(EMPTY);
    } catch (err) {
      setStep("error");
      let msg: string;
      if (err instanceof ApiError) {
        if (err.status === 0) {
          msg = "Cannot reach the server. Check your connection and try again.";
        } else if (err.status === 401) {
          msg = "Your session has expired. Please refresh the page and sign in again.";
        } else if (err.status === 403) {
          msg = "You don't have permission to create projects.";
        } else {
          msg = err.message || "Unable to create project. Please try again.";
        }
      } else {
        msg = err instanceof Error ? err.message : "An unexpected error occurred.";
      }
      setServerError(msg);
    }
  }

  function handleClose() {
    if (step === "creating") return;
    setStep("idle");
    setServerError(null);
    setErrors({});
    onClose();
  }

  return (
    <Dialog open={open} onClose={handleClose} labelledBy="dialog-title">
      <DialogHeader
        title="Create a new book project"
        description="Set up your project and primary book. You can change these later."
      />

      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field label="Project name" htmlFor="p-name" required error={errors.name}>
          <Input
            id="p-name"
            value={values.name}
            onChange={(e) => set("name", e.target.value)}
            aria-invalid={Boolean(errors.name)}
            placeholder="My Nonfiction Book"
          />
        </Field>

        <Field label="Book title" htmlFor="p-book" required error={errors.book_title}>
          <Input
            id="p-book"
            value={values.book_title}
            onChange={(e) => set("book_title", e.target.value)}
            aria-invalid={Boolean(errors.book_title)}
            placeholder="The Art of Calm Productivity"
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Subtitle" htmlFor="p-subtitle">
            <Input
              id="p-subtitle"
              value={values.subtitle}
              onChange={(e) => set("subtitle", e.target.value)}
              placeholder="Optional"
            />
          </Field>
          <Field label="Author name" htmlFor="p-author">
            <Input
              id="p-author"
              value={values.author_name}
              onChange={(e) => set("author_name", e.target.value)}
              placeholder="Jane Author"
            />
          </Field>
        </div>

        <Field label="Description" htmlFor="p-desc" error={errors.description}>
          <Textarea
            id="p-desc"
            value={values.description}
            onChange={(e) => set("description", e.target.value)}
            placeholder="What is this book about?"
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Language" htmlFor="p-lang">
            <Select
              id="p-lang"
              value={values.language}
              onChange={(e) => set("language", e.target.value)}
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Target audience" htmlFor="p-audience">
            <Input
              id="p-audience"
              value={values.target_audience}
              onChange={(e) => set("target_audience", e.target.value)}
              placeholder="e.g. busy professionals"
            />
          </Field>
        </div>

        <Field label="Writing style" htmlFor="p-style">
          <Input
            id="p-style"
            value={values.writing_style}
            onChange={(e) => set("writing_style", e.target.value)}
            placeholder="e.g. conversational, authoritative"
          />
        </Field>

        {serverError ? (
          <p role="alert" className="text-sm text-destructive">
            {serverError}
          </p>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={handleClose} disabled={step === "creating"}>
            Cancel
          </Button>
          <Button type="submit" disabled={step === "creating"}>
            {step === "creating" ? <Spinner label="Creating…" /> : "Create project"}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
