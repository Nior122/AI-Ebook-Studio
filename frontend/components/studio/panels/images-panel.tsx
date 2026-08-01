"use client";

// ImagesPanel — generate AI images (Pollinations) for the current chapter and
// insert them into the editor as markdown via onInsertImage.

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { IconImage } from "@/components/ui/icons";
import { studioApi, type GeneratedImage } from "@/lib/api/studio";
import { toastError } from "@/lib/errors";

interface PanelProps {
  projectId: string;
  writingBookId: string;
  activeChapterId: string | null;
  onApplyEdit?: (content: string) => void;
  onInsertImage?: (markdown: string) => void;
}

const ASPECTS = [
  { value: "16:9", label: "16:9" },
  { value: "4:3", label: "4:3" },
  { value: "square", label: "Square" },
  { value: "portrait", label: "Portrait" },
];

const STYLES = [
  { value: "realistic", label: "Realistic" },
  { value: "illustration", label: "Illustration" },
  { value: "watercolor", label: "Watercolor" },
  { value: "sketch", label: "Sketch" },
  { value: "comic", label: "Comic" },
];

export function ImagesPanel({ projectId, activeChapterId, onInsertImage }: PanelProps) {
  const [prompt, setPrompt] = useState("");
  const [aspect, setAspect] = useState("16:9");
  const [style, setStyle] = useState("realistic");
  const [images, setImages] = useState<GeneratedImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      setImages(await studioApi.listImages(projectId));
    } catch (e) {
      toast(toastError(e));
    } finally {
      setLoading(false);
    }
  }, [projectId, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  async function generate() {
    if (!prompt.trim() || generating) return;
    setGenerating(true);
    try {
      await studioApi.generateImage(projectId, {
        prompt: prompt.trim(),
        aspect_ratio: aspect,
        style,
        chapter_id: activeChapterId,
      });
      setPrompt("");
      toast({
        title: "Image queued",
        description: "Generation started — it will appear in the list when ready.",
        variant: "success",
      });
      await load();
    } catch (e) {
      toast(toastError(e));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-2 p-1">
      <Textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Describe the image you want…"
        className="min-h-[72px]"
      />
      <div className="flex gap-1">
        <select
          className="w-1/2 rounded border border-input bg-background px-2 py-1 text-xs"
          value={aspect}
          onChange={(e) => setAspect(e.target.value)}
          aria-label="Aspect ratio"
        >
          {ASPECTS.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </select>
        <select
          className="w-1/2 rounded border border-input bg-background px-2 py-1 text-xs"
          value={style}
          onChange={(e) => setStyle(e.target.value)}
          aria-label="Style"
        >
          {STYLES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>
      <Button
        size="sm"
        className="w-full"
        disabled={!prompt.trim() || generating}
        onClick={() => void generate()}
      >
        {generating ? <Spinner className="h-3 w-3" /> : <IconImage className="mr-1 h-3 w-3" />}{" "}
        Generate image
      </Button>
      <div className="border-t border-border pt-2">
        <p className="mb-1 text-[10px] font-medium text-muted-foreground">Generated images</p>
        {loading ? (
          <p className="text-xs text-muted-foreground p-1">Loading images…</p>
        ) : images.length === 0 ? (
          <p className="text-xs text-muted-foreground p-1">
            No images yet — generate your first one above.
          </p>
        ) : (
          <div className="space-y-2">
            {images.map((img) => (
              <div key={img.id} className="overflow-hidden rounded border border-border">
                {img.file_url ? (
                  <img
                    src={img.file_url}
                    alt={img.prompt}
                    loading="lazy"
                    decoding="async"
                    className="h-24 w-full object-cover"
                  />
                ) : (
                  <div className="flex h-24 w-full items-center justify-center bg-muted text-[10px] text-muted-foreground">
                    Generating…
                  </div>
                )}
                <div className="flex items-center justify-between gap-2 p-1.5">
                  <p className="truncate text-[10px] text-muted-foreground">{img.prompt}</p>
                  {onInsertImage && img.file_url && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-6 shrink-0 px-2 text-[10px]"
                      onClick={() => onInsertImage(`![${img.prompt.slice(0, 40)}](${img.file_url})`)}
                    >
                      Insert
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
