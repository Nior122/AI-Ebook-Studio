"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { bookWritingApi } from "@/lib/api/bookWriting";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input, Label, Select } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogFooter, DialogHeader } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { IconBook, IconPlus } from "@/components/ui/icons";
import { EmptyState, ErrorState } from "@/components/states/states";
import { useToast } from "@/components/ui/toast";
import type { WritingBook, WritingBookCreatePayload } from "@/types/api";

const LANGUAGES = ["en", "fr", "de", "es", "pt", "it", "nl", "ja", "ko", "zh"];
const TONES = ["Friendly", "Professional", "Academic", "Conversational", "Authoritative", "Humorous"];
const TYPES = ["nonfiction", "novel", "guide", "textbook", "memoir", "childrens"];

export default function BookWritingListPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<WritingBookCreatePayload>({
    title: "", language: "en", tone: "Friendly", book_type: "nonfiction",
  });

  const { data: books, isLoading, isError, refetch } = useQuery({
    queryKey: ["writing-books"],
    queryFn: () => bookWritingApi.listBooks(),
  });

  const createMutation = useMutation({
    mutationFn: (p: WritingBookCreatePayload) => bookWritingApi.createBook(p),
    onSuccess: (book) => {
      void qc.invalidateQueries({ queryKey: ["writing-books"] });
      setCreateOpen(false);
      setForm({ title: "", language: "en", tone: "Friendly", book_type: "nonfiction" });
      router.push(`/book-writing/${book.id}`);
    },
    onError: (err) => toast({ title: "Could not create book", description: String(err), variant: "error" }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => bookWritingApi.deleteBook(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["writing-books"] });
      toast({ title: "Book deleted", variant: "success" });
    },
  });

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i}><CardContent className="space-y-3 p-5">
            <Skeleton className="h-5 w-2/3" /><Skeleton className="h-4 w-full" /><Skeleton className="h-3 w-1/2" />
          </CardContent></Card>
        ))}
      </div>
    );
  }

  if (isError) {
    return <ErrorState message="Could not load your books." onRetry={() => void refetch()} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">My Books</h1>
        <Button onClick={() => setCreateOpen(true)}><IconPlus className="mr-2 size-4" /> New Book</Button>
      </div>

      {books && books.length === 0 ? (
        <EmptyState
          icon={<IconBook className="size-10 text-muted-foreground" />}
          title="No books yet"
          description="Create your first book to start writing."
          action={{ label: "Create your first book", onClick: () => setCreateOpen(true) }}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {books?.map((b) => (
            <Card
              key={b.id}
              className="cursor-pointer transition-shadow hover:shadow-md"
              onClick={() => router.push(`/book-writing/${b.id}`)}
            >
              <CardHeader>
                <CardTitle className="text-base">{b.title}</CardTitle>
                <p className="text-sm text-muted-foreground line-clamp-2">{b.description || "No description"}</p>
              </CardHeader>
              <CardContent className="flex items-center justify-between">
                <Badge variant={stepBadge(b.current_step)}>{b.current_step}</Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm("Delete this book? This cannot be undone.")) {
                      deleteMutation.mutate(b.id);
                    }
                  }}
                >
                  Delete
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} labelledBy="create-book-title">
        <DialogHeader title="Create a new book" />
        <form
          className="space-y-4"
          onSubmit={(e) => { e.preventDefault(); createMutation.mutate(form); }}
        >
          <Field label="Title" htmlFor="bw-title" required>
            <Input id="bw-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. AI Tools for Teachers" />
          </Field>
          <Field label="Description" htmlFor="bw-desc">
            <Input id="bw-desc" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="A short description of your book" />
          </Field>
          <Field label="Type" htmlFor="bw-type">
            <Select id="bw-type" value={form.book_type ?? ""} onChange={(e) => setForm({ ...form, book_type: e.target.value })}>
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </Select>
          </Field>
          <Field label="Language" htmlFor="bw-lang">
            <Select id="bw-lang" value={form.language ?? "en"} onChange={(e) => setForm({ ...form, language: e.target.value })}>
              {LANGUAGES.map((l) => <option key={l} value={l}>{l.toUpperCase()}</option>)}
            </Select>
          </Field>
          <Field label="Tone" htmlFor="bw-tone">
            <Select id="bw-tone" value={form.tone ?? ""} onChange={(e) => setForm({ ...form, tone: e.target.value })}>
              {TONES.map((t) => <option key={t} value={t}>{t}</option>)}
            </Select>
          </Field>
          <Field label="Author" htmlFor="bw-author">
            <Input id="bw-author" value={form.author_name ?? ""} onChange={(e) => setForm({ ...form, author_name: e.target.value })} placeholder="Your name" />
          </Field>
          <DialogFooter>
            <Button variant="outline" type="button" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={!form.title || createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create Book"}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}

function stepBadge(step: string): "outline" | "secondary" | "success" | "warning" | "muted" | undefined {
  const m: Record<string, "outline" | "secondary" | "success" | "warning" | "muted" | undefined> = {
    idea: "outline", brief: "secondary", blueprint: "secondary",
    outline: "secondary", writing: "success", editing: "warning",
    formatting: "muted", export: "muted",
  };
  return m[step] ?? undefined;
}