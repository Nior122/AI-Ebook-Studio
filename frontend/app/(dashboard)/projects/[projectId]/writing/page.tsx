"use client";

// Writing module — bridges to the real Phase 6 book-writing editor.
// The actual editor lives at /book-writing/[bookId], so we redirect.

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { booksApi } from "@/lib/api/books";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/skeleton";
import { IconPen, IconAlert } from "@/components/ui/icons";

export default function WritingModulePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const router = useRouter();

  const { data: books, isLoading } = useQuery({
    queryKey: ["books", projectId],
    queryFn: () => booksApi.listForProject(projectId),
  });

  const writingBookId = books?.[0]?.metadata_json?.writing_book_id;

  useEffect(() => {
    if (writingBookId) {
      router.replace(`/book-writing/${writingBookId}`);
    }
  }, [writingBookId, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner label="Loading…" />
      </div>
    );
  }

  if (!books || books.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 p-8 text-center">
          <IconAlert className="h-8 w-8 text-muted-foreground" />
          <h2 className="text-lg font-semibold">No book in this project</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            This project doesn't have a book yet. Create a new project to start writing.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!writingBookId) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 p-8 text-center">
          <IconPen className="h-8 w-8 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Book engine link missing</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            This project's book isn't linked to the writing engine. The book for this project was created before the engine was connected — create a new project to use the editor.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex items-center justify-center py-12">
      <Spinner label="Opening editor…" />
    </div>
  );
}
