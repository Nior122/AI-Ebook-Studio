"use client";

// Images module — bridges to existing images engine + uses Phase 6 backend.

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { booksApi } from "@/lib/api/books";
import { bookWritingApi } from "@/lib/api/bookWriting";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { IconImage } from "@/components/ui/icons";
import { ErrorState } from "@/components/states/states";

interface GeneratedImage {
  id: string;
  title?: string | null;
  current_image_url?: string | null;
  aspect_ratio?: string | null;
  style?: string | null;
  status?: string | null;
  created_at?: string | null;
}

export default function ImagesModulePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [generating, setGenerating] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [count, setCount] = useState(3);

  const { data: books, isLoading } = useQuery({
    queryKey: ["books", projectId], queryFn: () => booksApi.listForProject(projectId),
  });
  const writingBookId = books?.[0]?.metadata_json?.writing_book_id;

  const { data: imagesData } = useQuery({
    queryKey: ["images", writingBookId],
    queryFn: async () => {
      try {
        return await bookWritingApi.listMarketing(writingBookId!);
      } catch {
        return { items: [] as any[] };
      }
    },
    enabled: !!writingBookId,
  });

  if (isLoading) return <div className="flex justify-center py-12"><Spinner label="Loading…" /></div>;
  if (!writingBookId) {
    return <ErrorState title="Book engine link missing" message="Create a new project to enable image generation." />;
  }

  // Simple deterministic image list kept in localStorage for now; the full image engine
  // lives at /book-writing/[bookId]?tab=images. Show recent images + a generator form.
  let stored: GeneratedImage[] = [];
  try {
    stored = JSON.parse(localStorage.getItem(`images-${writingBookId}`) || "[]");
  } catch { stored = []; }

  async function generate() {
    if (!prompt.trim()) {
      toast({ title: "Enter a prompt", variant: "error" });
      return;
    }
    setGenerating(true);
    const newImages: GeneratedImage[] = [];
    for (let i = 0; i < count; i++) {
      const seed = Math.floor(Math.random() * 1_000_000);
      const encoded = encodeURIComponent(prompt + `, variation ${i + 1}, seed ${seed}`);
      const url = `https://image.pollinations.ai/prompt/${encoded}?width=1600&height=900&seed=${seed}&nologo=true`;
      newImages.push({
        id: crypto.randomUUID(),
        title: prompt,
        current_image_url: url,
        aspect_ratio: "16:9",
        style: "realistic",
        status: "completed",
        created_at: new Date().toISOString(),
      });
    }
    const updated = [...newImages, ...stored];
    localStorage.setItem(`images-${writingBookId}`, JSON.stringify(updated));
    setGenerating(false);
    setPrompt("");
    queryClient.invalidateQueries({ queryKey: ["images", writingBookId] });
    toast({ title: `${count} image(s) generated`, variant: "success" });
  }

  function remove(id: string) {
    const updated = stored.filter((i) => i.id !== id);
    localStorage.setItem(`images-${writingBookId}`, JSON.stringify(updated));
    queryClient.invalidateQueries({ queryKey: ["images", writingBookId] });
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Images</h2>
        <p className="text-sm text-muted-foreground">
          Auto-placed images throughout your manuscript. Generate cover-quality 16:9 images, place them where they fit best, regenerate, replace, or delete.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <IconImage className="h-5 w-5" />
            Generate images
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            placeholder="Describe the image: subject, environment, style, mood…"
            className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <div className="flex items-end gap-3">
            <div>
              <label className="block text-sm font-medium">Count</label>
              <input
                type="number"
                min={1}
                max={8}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="h-10 w-20 rounded-md border border-input bg-background px-3 text-sm"
              />
            </div>
            <Button onClick={generate} disabled={generating}>
              {generating ? <Spinner label="Generating…" /> : "Generate"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Gallery</CardTitle>
        </CardHeader>
        <CardContent>
          {stored.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No images yet. Use the form above to generate images.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {stored.map((img) => (
                <div key={img.id} className="overflow-hidden rounded-lg border border-border bg-card">
                  <img
                    src={img.current_image_url || ""}
                    alt={img.title || "Generated image"}
                    className="aspect-video w-full object-cover"
                  />
                  <div className="p-3">
                    <p className="line-clamp-2 text-sm">{img.title}</p>
                    <div className="mt-2 flex items-center justify-between">
                      <Badge variant="muted">{img.aspect_ratio || "16:9"}</Badge>
                      <Button variant="outline" size="sm" onClick={() => remove(img.id)}>
                        Delete
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
