"use client";

// Book settings (formatting) page. Lets the author choose the physical format
// and typographic style BEFORE final conversion. All values are read from and
// saved to the backend via the book-settings API — nothing is hardcoded. The
// default (6×9 trim, 16:9 images) comes from the backend, not the frontend.

import { useEffect, use, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input, Select, Checkbox } from "@/components/ui/input";
import { Spinner } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/states/states";
import { IconLayout } from "@/components/ui/icons";
import { useProjectBook, useBookSettings, useUpdateBookSettings } from "@/hooks/use-books";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api";
import type { BookSettings, TrimSize, ImageAlignment } from "@/types";

const TRIM_SIZES: { value: TrimSize; label: string }[] = [
  { value: "6x9", label: "6 × 9 in" },
  { value: "8x10", label: "8 × 10 in" },
  { value: "A4", label: "A4" },
  { value: "Letter", label: "Letter" },
  { value: "custom", label: "Custom" },
];

const FONTS = ["Georgia", "Times New Roman", "Arial", "Helvetica", "Garamond", "Palatino"];

function num(value: string): number {
  const n = parseFloat(value);
  return Number.isFinite(n) ? n : 0;
}

export default function FormattingPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const { data: book, isLoading: bookLoading } = useProjectBook(projectId);
  const { data: settings, isLoading, isError, refetch } = useBookSettings(book?.id);
  const updateSettings = useUpdateBookSettings();
  const toast = useToast();

  const [form, setForm] = useState<BookSettings | null>(null);

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  if (bookLoading || (book && isLoading)) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner label="Loading settings…" />
      </div>
    );
  }

  if (!book) {
    return (
      <ErrorState
        title="No book yet"
        message="Create a book for this project before configuring formatting."
      />
    );
  }

  if (isError || !form) {
    return <ErrorState message="We couldn't load book settings." onRetry={() => void refetch()} />;
  }

  function set<K extends keyof BookSettings>(key: K, value: BookSettings[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function onSave() {
    if (!book) return;
    try {
      await updateSettings.mutateAsync({ bookId: book.id, payload: { ...form } });
      toast({ title: "Settings saved", variant: "success" });
    } catch (err) {
      toast({
        title: "Could not save settings",
        description: err instanceof ApiError ? err.message : undefined,
        variant: "error",
      });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-foreground">
          <IconLayout className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Book formatting</h2>
          <p className="text-sm text-muted-foreground">
            Choose your book format before generating the final document.
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Page size */}
        <Card>
          <CardHeader>
            <CardTitle>Page size</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="KDP trim size" htmlFor="trim">
              <Select
                id="trim"
                value={form.kdp_trim_size}
                onChange={(e) => set("kdp_trim_size", e.target.value as TrimSize)}
              >
                {TRIM_SIZES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Custom width (in)" htmlFor="pw">
                <Input
                  id="pw"
                  type="number"
                  step="0.1"
                  min="0"
                  value={form.page_width}
                  onChange={(e) => set("page_width", num(e.target.value))}
                />
              </Field>
              <Field label="Custom height (in)" htmlFor="ph">
                <Input
                  id="ph"
                  type="number"
                  step="0.1"
                  min="0"
                  value={form.page_height}
                  onChange={(e) => set("page_height", num(e.target.value))}
                />
              </Field>
            </div>
          </CardContent>
        </Card>

        {/* Margins */}
        <Card>
          <CardHeader>
            <CardTitle>Margins (in)</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            <Field label="Top" htmlFor="mt">
              <Input id="mt" type="number" step="0.05" min="0" value={form.margin_top} onChange={(e) => set("margin_top", num(e.target.value))} />
            </Field>
            <Field label="Bottom" htmlFor="mb">
              <Input id="mb" type="number" step="0.05" min="0" value={form.margin_bottom} onChange={(e) => set("margin_bottom", num(e.target.value))} />
            </Field>
            <Field label="Left" htmlFor="ml">
              <Input id="ml" type="number" step="0.05" min="0" value={form.margin_left} onChange={(e) => set("margin_left", num(e.target.value))} />
            </Field>
            <Field label="Right" htmlFor="mr">
              <Input id="mr" type="number" step="0.05" min="0" value={form.margin_right} onChange={(e) => set("margin_right", num(e.target.value))} />
            </Field>
          </CardContent>
        </Card>

        {/* Typography */}
        <Card>
          <CardHeader>
            <CardTitle>Typography</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Body font" htmlFor="bf">
                <Select id="bf" value={form.body_font} onChange={(e) => set("body_font", e.target.value)}>
                  {FONTS.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Body font size (pt)" htmlFor="bfs">
                <Input id="bfs" type="number" step="0.5" min="0" value={form.body_font_size} onChange={(e) => set("body_font_size", num(e.target.value))} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Heading font" htmlFor="hf">
                <Select id="hf" value={form.heading_font} onChange={(e) => set("heading_font", e.target.value)}>
                  {FONTS.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Line spacing" htmlFor="ls">
                <Input id="ls" type="number" step="0.05" min="0" value={form.line_spacing} onChange={(e) => set("line_spacing", num(e.target.value))} />
              </Field>
            </div>
            <Field label="Paragraph spacing (pt)" htmlFor="ps">
              <Input id="ps" type="number" step="0.5" min="0" value={form.paragraph_spacing} onChange={(e) => set("paragraph_spacing", num(e.target.value))} />
            </Field>
          </CardContent>
        </Card>

        {/* Images */}
        <Card>
          <CardHeader>
            <CardTitle>Images</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Image width (in)" htmlFor="iw">
                <Input id="iw" type="number" step="0.1" min="0" value={form.image_width} onChange={(e) => set("image_width", num(e.target.value))} />
              </Field>
              <Field label="Image alignment" htmlFor="ia">
                <Select id="ia" value={form.image_alignment} onChange={(e) => set("image_alignment", e.target.value as ImageAlignment)}>
                  <option value="left">Left</option>
                  <option value="center">Center</option>
                  <option value="right">Right</option>
                </Select>
              </Field>
            </div>
            <Field label="Image aspect ratio" htmlFor="iar">
              <Select id="iar" value={form.image_aspect_ratio} onChange={(e) => set("image_aspect_ratio", e.target.value)}>
                <option value="16:9">16:9</option>
                <option value="4:3">4:3</option>
                <option value="1:1">1:1</option>
                <option value="3:4">3:4</option>
                <option value="2:3">2:3</option>
              </Select>
            </Field>
            <Field label="Image style" htmlFor="istyle">
              <Input id="istyle" value={form.image_style} onChange={(e) => set("image_style", e.target.value)} placeholder="realistic" />
            </Field>
            <Field label="Caption font size (pt)" htmlFor="cfs">
              <Input id="cfs" type="number" step="0.5" min="0" value={form.caption_font_size} onChange={(e) => set("caption_font_size", num(e.target.value))} />
            </Field>
          </CardContent>
        </Card>
      </div>

      {/* Document options */}
      <Card>
        <CardHeader>
          <CardTitle>Document</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={form.toc_enabled}
              onChange={(e) => set("toc_enabled", e.target.checked)}
            />
            Table of contents enabled
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={form.chapter_page_breaks}
              onChange={(e) => set("chapter_page_breaks", e.target.checked)}
            />
            Chapter page breaks
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={form.caption_enabled}
              onChange={(e) => set("caption_enabled", e.target.checked)}
            />
            Captions enabled
          </label>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => void onSave()} disabled={updateSettings.isPending}>
          {updateSettings.isPending ? <Spinner label="Saving…" /> : "Save settings"}
        </Button>
      </div>
    </div>
  );
}
