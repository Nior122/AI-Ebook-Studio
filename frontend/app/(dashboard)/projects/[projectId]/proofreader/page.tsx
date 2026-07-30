"use client";

// Proofreader module — bridges to the real Phase 6 book-writing editor (review tab).

import { use, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { booksApi } from "@/lib/api/books";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/skeleton";
import { IconProof, IconAlert } from "@/components/ui/icons";

export default function ProofreaderModulePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const router = useRouter();

  const { data: books, isLoading } = useQuery({
    queryKey: ["books", projectId],
    queryFn: () => booksApi.listForProject(projectId),
  });

  const writingBookId = books?.[0]?.metadata_json?.writing_book_id;

  useEffect(() => {
    if (writingBookId) {
      router.replace(`/book-writing/${writingBookId}?tab=review`);
    }
  }, [writingBookId, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner label="Loading…" />
      </div>
    );
  }

  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 p-8 text-center">
        {books && books.length > 0 ? (
          <>
            <IconProof className="h-8 w-8 text-muted-foreground" />
            <h2 className="text-lg font-semibold">Opening AI proofreader…</h2>
          </>
        ) : (
          <>
            <IconAlert className="h-8 w-8 text-muted-foreground" />
            <h2 className="text-lg font-semibold">No book in this project</h2>
            <p className="max-w-md text-sm text-muted-foreground">
              Create a new project to enable proofreading.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
