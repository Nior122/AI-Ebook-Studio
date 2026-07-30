"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { bookWritingApi } from "@/lib/api/bookWriting";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton, Spinner } from "@/components/ui/skeleton";
import { IconPlus, IconSettings, IconSparkles } from "@/components/ui/icons";
import { useToast } from "@/components/ui/toast";
import type {
  BookBlueprint,
  BookBlueprintUpdatePayload,
  BookBrief,
  BookBriefUpdatePayload,
  WritingBook,
  WritingBookSettings,
  WritingBookStep,
} from "@/types/api";
import { editingApi } from "@/lib/api/editing";
import type {
  EditingMode,
  EditingSuggestion,
  ReviewSummary,
  SuggestionCategory,
  SuggestionStatus,
} from "@/types/api";

const STEPS: WritingBookStep[] = ["idea", "brief", "blueprint", "outline", "writing", "editing", "formatting", "export"];
const STEP_LABELS: Record<WritingBookStep, string> = {
  idea: "Idea", brief: "Brief", blueprint: "Blueprint", outline: "Outline",
  writing: "Writing", editing: "Editing", formatting: "Formatting", export: "Export",
};

type Tab = "editor" | "brief" | "blueprint" | "review" | "versions" | "settings";

export default function BookEditorPage({ params }: { params: Promise<{ bookId: string }> }) {
  const { bookId } = use(params);
  const toast = useToast();

  const [tab, setTab] = useState<Tab>("editor");
  const [activeChapterId, setActiveChapterId] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [saveStatus, setSaveStatus] = useState<"saved" | "unsaved" | "saving" | "failed">("saved");

  const { data: book, isLoading: bookLoad } = useQuery({
    queryKey: ["writing-book", bookId], queryFn: () => bookWritingApi.getBook(bookId),
  });
  const { data: chapters, refetch: refetchChapters } = useQuery({
    queryKey: ["writing-chapters", bookId], queryFn: () => bookWritingApi.listChapters(bookId),
  });
  const { data: settings, refetch: refetchSettings } = useQuery({
    queryKey: ["writing-settings", bookId], queryFn: () => bookWritingApi.getSettings(bookId),
  });
  const { data: brief, refetch: refetchBrief } = useQuery({
    queryKey: ["writing-brief", bookId], queryFn: () => bookWritingApi.getBrief(bookId),
    enabled: tab === "brief",
  });
  const { data: blueprint, refetch: refetchBlueprint } = useQuery({
    queryKey: ["writing-blueprint", bookId], queryFn: () => bookWritingApi.getBlueprint(bookId),
    enabled: tab === "blueprint",
  });

  useEffect(() => {
    if (chapters && chapters.length > 0 && !activeChapterId) {
      const first = chapters[0];
      setActiveChapterId(first.id);
      setEditorContent(first.content);
    }
  }, [chapters, activeChapterId]);

  const generateBriefM = useMutation({
    mutationFn: () => bookWritingApi.generateBrief(bookId),
    onSuccess: () => { refetchBrief(); toast({ title: "Brief generated", variant: "success" }); },
  });
  const updateBriefM = useMutation({
    mutationFn: (p: BookBriefUpdatePayload) => bookWritingApi.updateBrief(bookId, p),
    onSuccess: () => { refetchBrief(); toast({ title: "Brief saved", variant: "success" }); },
  });
  const generateBlueprintM = useMutation({
    mutationFn: () => bookWritingApi.generateBlueprint(bookId),
    onSuccess: () => { refetchBlueprint(); toast({ title: "Blueprint generated", variant: "success" }); },
  });
  const updateBlueprintM = useMutation({
    mutationFn: (p: BookBlueprintUpdatePayload) => bookWritingApi.updateBlueprint(bookId, p),
    onSuccess: () => { refetchBlueprint(); toast({ title: "Blueprint saved", variant: "success" }); },
  });
  const createChapterM = useMutation({
    mutationFn: (title: string) => bookWritingApi.createChapter(bookId, { title }),
    onSuccess: () => { refetchChapters(); toast({ title: "Chapter created", variant: "success" }); },
  });
  const generateOutlineM = useMutation({
    mutationFn: (cid: string) => bookWritingApi.generateOutline(cid),
    onSuccess: () => { refetchChapters(); },
  });
  const generateChapterM = useMutation({
    mutationFn: (cid: string) => bookWritingApi.generateChapter(cid),
    onSuccess: () => {},
  });
  const rewriteM = useMutation({
    mutationFn: ({ cid, sel }: { cid: string; sel?: string }) => bookWritingApi.rewriteChapter(cid, { selected_text: sel }),
    onSuccess: () => {},
  });
  const expandM = useMutation({
    mutationFn: ({ cid, sel }: { cid: string; sel?: string }) => bookWritingApi.expandChapter(cid, { selected_text: sel }),
    onSuccess: () => {},
  });
  const autosaveM = useMutation({
    mutationFn: ({ cid, content }: { cid: string; content: string }) => bookWritingApi.autosave(bookId, cid, content),
    onSuccess: () => setSaveStatus("saved"),
    onError: () => setSaveStatus("failed"),
  });

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveTimer = useCallback(
    (cid: string, content: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        setSaveStatus("saving");
        autosaveM.mutate({ cid, content });
      }, 1500);
    },
    [autosaveM],
  );

  const handleContentChange = (val: string) => {
    setEditorContent(val);
    setSaveStatus("unsaved");
    if (activeChapterId) saveTimer(activeChapterId, val);
  };

  const activeChapter = useMemo(
    () => chapters?.find((c) => c.id === activeChapterId) ?? null,
    [chapters, activeChapterId],
  );
  const selectedText = useRef("");

  const handleAiAction = async (
    action: "outline" | "generate" | "continue" | "rewrite" | "expand",
  ) => {
    if (!activeChapter) return;
    try {
      let ch;
      switch (action) {
        case "outline":
          ch = await bookWritingApi.generateOutline(activeChapter.id);
          break;
        case "generate":
          ch = await bookWritingApi.generateChapter(activeChapter.id);
          break;
        case "continue":
          ch = await bookWritingApi.continueChapter(activeChapter.id);
          break;
        case "rewrite":
          ch = await bookWritingApi.rewriteChapter(activeChapter.id, {
            selected_text: selectedText.current || undefined,
          });
          break;
        case "expand":
          ch = await bookWritingApi.expandChapter(activeChapter.id, {
            selected_text: selectedText.current || undefined,
          });
          break;
      }
      setEditorContent(ch.content);
      await refetchChapters();
      toast({ title: `${action} complete`, variant: "success" });
    } catch (e: unknown) {
      toast({ title: `${action} failed`, description: String(e), variant: "error" });
    }
  };

  if (bookLoad) return <div className="space-y-4">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}</div>;
  if (!book) return <p className="text-destructive">Book not found.</p>;

  const stepIdx = STEPS.indexOf(book.current_step);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{book.title}</h1>
          {book.author_name && <p className="text-sm text-muted-foreground">by {book.author_name}</p>}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={stepIdx >= 0 ? "success" : "muted"}>{book.current_step}</Badge>
          <Button variant="outline" size="sm" onClick={() => setTab("settings")}><IconSettings className="mr-1 size-4" /> Style</Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {STEPS.map((step, i) => {
          const done = i < stepIdx;
          const current = i === stepIdx;
          return (
            <button
              key={step}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                current ? "bg-primary text-primary-foreground" : done ? "bg-secondary text-foreground" : "text-muted-foreground"
              }`}
              onClick={() => setTab(step === "brief" ? "brief" : step === "blueprint" ? "blueprint" : step === "editing" ? "review" : "editor")}
            >
              {STEP_LABELS[step]}
            </button>
          );
        })}
      </div>

      <div className="flex gap-2 border-b border-border pb-2">
        {(["editor", "brief", "blueprint", "review", "versions", "settings"] as const).map((t) => (
          <button
            key={t}
            className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
              tab === t ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => setTab(t)}
          >
            {t === "editor" ? "Editor" : t === "brief" ? "Brief" : t === "blueprint" ? "Blueprint" : t === "review" ? "Review" : t === "versions" ? "Versions" : "Style"}
          </button>
        ))}
      </div>

      {tab === "brief" && (
        <BriefTab
          bookId={bookId}
          brief={brief}
          onGenerate={() => generateBriefM.mutate()}
          onSave={(p) => updateBriefM.mutate(p)}
          generating={generateBriefM.isPending}
          saving={updateBriefM.isPending}
        />
      )}
      {tab === "blueprint" && (
        <BlueprintTab
          bookId={bookId}
          blueprint={blueprint}
          onGenerate={() => generateBlueprintM.mutate()}
          onSave={(p) => updateBlueprintM.mutate(p)}
          generating={generateBlueprintM.isPending}
          saving={updateBlueprintM.isPending}
        />
      )}
      {tab === "versions" && <VersionsTab chapterId={activeChapterId} />}
      {tab === "settings" && (
        <SettingsTab book={book} settings={settings ?? null} onSaved={() => { refetchSettings(); }} />
      )}
      {tab === "review" && activeChapterId && (
        <ReviewTab chapterId={activeChapterId} onChapterChanged={() => refetchChapters()} />
      )}

      {tab === "editor" && (
        <div className="flex gap-6">
          <div className="w-64 shrink-0 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-muted-foreground">Chapters</h3>
              <Button variant="ghost" size="sm" onClick={() => { const t = prompt("Chapter title:"); if (t) createChapterM.mutate(t); }}>
                <IconPlus className="size-4" />
              </Button>
            </div>
            {chapters?.map((ch) => (
              <button
                key={ch.id}
                className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                  ch.id === activeChapterId ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary/50"
                }`}
                onClick={() => { setActiveChapterId(ch.id); setEditorContent(ch.content); }}
              >
                <div className="font-medium">{ch.chapter_number}. {ch.title}</div>
                <div className="flex gap-1 mt-1">
                  <Badge variant={ch.status === "approved" ? "success" : ch.status === "draft" ? "secondary" : "outline"} className="text-[10px]">{ch.status}</Badge>
                  <span className="text-[10px]">{ch.actual_word_count}w</span>
                </div>
              </button>
            ))}
          </div>

          <div className="flex-1 space-y-4">
            {activeChapter ? (
              <>
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">{activeChapter.title}</h2>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs ${saveStatus === "saving" ? "text-yellow-600" : saveStatus === "saved" ? "text-emerald-600" : "text-muted-foreground"}`}>
                      {saveStatus === "saving" ? "Saving…" : saveStatus === "saved" ? "Saved" : saveStatus === "unsaved" ? "Unsaved" : "Save failed"}
                    </span>
                    {(["outline", "generate", "continue", "rewrite", "expand"] as const).map((action) => (
                      <Button key={action} size="sm" variant="outline" onClick={() => handleAiAction(action)}>
                        {action === "outline" ? "Outline" : action === "generate" ? "Generate" : action === "continue" ? "Continue" : action === "rewrite" ? "Rewrite" : "Expand"}
                      </Button>
                    ))}
                  </div>
                </div>
                <Textarea
                  className="min-h-[500px] w-full rounded-md border border-input bg-background px-4 py-3 text-sm leading-relaxed"
                  value={editorContent}
                  onChange={(e) => handleContentChange(e.target.value)}
                  onMouseUp={() => {
                    const sel = window.getSelection()?.toString();
                    selectedText.current = sel ?? "";
                  }}
                  placeholder="Write your chapter content here…"
                />
              </>
            ) : (
              <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
                No chapters yet. Create one to start writing.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function BriefTab({
  bookId, brief, onGenerate, onSave, generating, saving,
}: {
  bookId: string; brief: BookBrief | undefined;
  onGenerate: () => void; onSave: (p: BookBriefUpdatePayload) => void;
  generating: boolean; saving: boolean;
}) {
  const [form, setForm] = useState<Record<string, unknown>>({});
  const toast = useToast();

  useEffect(() => {
    if (brief) setForm(brief as unknown as Record<string, unknown>);
  }, [brief]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Book Brief</h3>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onGenerate} disabled={generating}>
            {generating ? "Generating…" : brief ? "Regenerate" : "Generate with AI"}
          </Button>
          <Button onClick={() => { onSave(form as BookBriefUpdatePayload); toast({ title: "Brief saved", variant: "success" }); }} disabled={saving}>Save</Button>
        </div>
      </div>
      {brief ? (
        <div className="grid grid-cols-2 gap-4">
          <Field label="Working title" htmlFor="bw-working-title"><Input id="bw-working-title" value={String(form.working_title ?? "")} onChange={(e) => setForm({ ...form, working_title: e.target.value })} /></Field>
          <Field label="Subtitle" htmlFor="bw-subtitle"><Input id="bw-subtitle" value={String(form.subtitle ?? "")} onChange={(e) => setForm({ ...form, subtitle: e.target.value })} /></Field>
          <Field label="Purpose" htmlFor="bw-purpose" className="col-span-2"><Textarea id="bw-purpose" value={String(form.book_purpose ?? "")} onChange={(e) => setForm({ ...form, book_purpose: e.target.value })} /></Field>
          <Field label="Target reader" htmlFor="bw-target"><Input id="bw-target" value={String(form.target_reader ?? "")} onChange={(e) => setForm({ ...form, target_reader: e.target.value })} /></Field>
          <Field label="Promised transformation" htmlFor="bw-transform"><Input id="bw-transform" value={String(form.promised_transformation ?? "")} onChange={(e) => setForm({ ...form, promised_transformation: e.target.value })} /></Field>
          <Field label="Tone" htmlFor="bw-tone"><Input id="bw-tone" value={String(form.tone ?? "")} onChange={(e) => setForm({ ...form, tone: e.target.value })} /></Field>
          <Field label="Writing style" htmlFor="bw-style"><Input id="bw-style" value={String(form.writing_style ?? "")} onChange={(e) => setForm({ ...form, writing_style: e.target.value })} /></Field>
          <Field label="Estimated chapters" htmlFor="bw-est-chapters"><Input id="bw-est-chapters" type="number" value={String(form.estimated_chapter_count ?? "")} onChange={(e) => setForm({ ...form, estimated_chapter_count: e.target.value ? Number(e.target.value) : null })} /></Field>
          <Field label="Estimated words" htmlFor="bw-est-words"><Input id="bw-est-words" type="number" value={String(form.estimated_word_count ?? "")} onChange={(e) => setForm({ ...form, estimated_word_count: e.target.value ? Number(e.target.value) : null })} /></Field>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Generate a brief with AI or fill in manually.</p>
      )}
    </div>
  );
}

function BlueprintTab({
  bookId, blueprint, onGenerate, onSave, generating, saving,
}: {
  bookId: string; blueprint: BookBlueprint | undefined;
  onGenerate: () => void; onSave: (p: BookBlueprintUpdatePayload) => void;
  generating: boolean; saving: boolean;
}) {
  const [chapters, setChapters] = useState<BookBlueprint["chapters"]>([]);
  const [intro, setIntro] = useState("");
  const toast = useToast();

  useEffect(() => {
    if (blueprint) { setChapters(blueprint.chapters); setIntro(blueprint.introduction_purpose ?? ""); }
  }, [blueprint]);

  const moveUp = (i: number) => {
    if (i <= 0) return;
    const next = [...chapters];
    [next[i - 1], next[i]] = [next[i], next[i - 1]];
    setChapters(next);
  };
  const moveDown = (i: number) => {
    if (i >= chapters.length - 1) return;
    const next = [...chapters];
    [next[i], next[i + 1]] = [next[i + 1], next[i]];
    setChapters(next);
  };
  const remove = (i: number) => setChapters(chapters.filter((_, idx) => idx !== i));
  const add = () => {
    const t = prompt("Chapter title:");
    if (t) setChapters([...chapters, { title: t }]);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Book Blueprint</h3>
        <div className="flex gap-2">
          <Button variant="outline" onClick={add}>Add Chapter</Button>
          <Button variant="outline" onClick={onGenerate} disabled={generating}>
            {generating ? "Generating…" : blueprint ? "Regenerate" : "Generate with AI"}
          </Button>
          <Button onClick={() => { onSave({ introduction_purpose: intro, chapters }); toast({ title: "Blueprint saved", variant: "success" }); }} disabled={saving}>Save</Button>
        </div>
      </div>
      <Field label="Introduction purpose" htmlFor="bw-intro">
        <Textarea id="bw-intro" value={intro} onChange={(e) => setIntro(e.target.value)} placeholder="What does the introduction cover?" />
      </Field>
      <div className="space-y-2">
        {chapters.map((ch, i) => (
          <Card key={i} className="relative">
            <CardContent className="flex items-center justify-between p-3">
              <div className="flex-1">
                <span className="text-xs text-muted-foreground mr-2">#{i + 1}</span>
                <span className="font-medium">{ch.title}</span>
                {ch.estimated_word_count && <span className="ml-2 text-xs text-muted-foreground">~{ch.estimated_word_count}w</span>}
              </div>
              <div className="flex gap-1">
                <Button size="sm" variant="ghost" onClick={() => moveUp(i)} disabled={i === 0}>↑</Button>
                <Button size="sm" variant="ghost" onClick={() => moveDown(i)} disabled={i === chapters.length - 1}>↓</Button>
                <Button size="sm" variant="ghost" onClick={() => remove(i)} className="text-destructive">×</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function VersionsTab({ chapterId }: { chapterId: string | null }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: versions } = useQuery({
    queryKey: ["chapter-versions", chapterId],
    queryFn: () => (chapterId ? bookWritingApi.listVersions(chapterId) : Promise.resolve([])),
    enabled: Boolean(chapterId),
  });
  const restoreMutation = useMutation({
    mutationFn: (versionId: string) => bookWritingApi.restoreVersion(chapterId!, versionId),
    onSuccess: () => {
      toast({ title: "Version restored", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["chapter-versions", chapterId] });
      queryClient.invalidateQueries({ queryKey: ["chapters", chapterId] });
    },
    onError: (err: Error) => toast({ title: "Restore failed", description: err.message, variant: "error" }),
  });
  if (!chapterId) return <p className="text-sm text-muted-foreground">Select a chapter to see version history.</p>;
  return (
    <div className="space-y-2">
      <h3 className="text-lg font-semibold">Version History</h3>
      {versions && versions.length === 0 && <p className="text-sm text-muted-foreground">No versions yet.</p>}
      {versions?.map((v) => (
        <Card key={v.id}>
          <CardContent className="flex items-center justify-between p-3">
            <div>
              <span className="text-xs text-muted-foreground">v{v.version_number}</span>
              <Badge variant="outline" className="ml-2 text-[10px]">{v.version_type}</Badge>
              <span className="ml-2 text-xs text-muted-foreground">{v.word_count}w</span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => restoreMutation.mutate(v.id)}
              disabled={restoreMutation.isPending}
            >
              {restoreMutation.isPending && restoreMutation.variables === v.id ? <Spinner label="Restoring…" /> : "Restore"}
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function SettingsTab({ book, settings, onSaved }: {
  book: WritingBook; settings: WritingBookSettings | null; onSaved: () => void;
}) {
  const [form, setForm] = useState<Partial<WritingBookSettings>>({});
  const toast = useToast();

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  const updateM = useMutation({
    mutationFn: (p: Parameters<typeof bookWritingApi.updateSettings>[1]) => bookWritingApi.updateSettings(book.id, p),
    onSuccess: () => { onSaved(); toast({ title: "Settings saved", variant: "success" }); },
  });

  const set = (k: string, v: unknown) => setForm({ ...form, [k]: v });
  const save = () => updateM.mutate(form as Parameters<typeof bookWritingApi.updateSettings>[1]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Writing Style Profile</h3>
        <Button onClick={save} disabled={updateM.isPending}>Save</Button>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <Field label="Tone" htmlFor="st-tone"><Input id="st-tone" value={String(form.tone ?? "")} onChange={(e) => set("tone", e.target.value)} /></Field>
        <Field label="Formality" htmlFor="st-formality"><Input id="st-formality" value={String(form.formality ?? "")} onChange={(e) => set("formality", e.target.value)} /></Field>
        <Field label="Reading level" htmlFor="st-reading"><Input id="st-reading" value={String(form.reading_level ?? "")} onChange={(e) => set("reading_level", e.target.value)} /></Field>
        <Field label="Point of view" htmlFor="st-pov"><Select id="st-pov" value={String(form.point_of_view ?? "second_person")} onChange={(e) => set("point_of_view", e.target.value)}>
          <option value="first_person">First person</option>
          <option value="second_person">Second person (you)</option>
          <option value="third_person">Third person</option>
        </Select></Field>
        <Field label="Use examples" htmlFor="st-examples"><Select id="st-examples" value={String(form.use_examples ?? "medium")} onChange={(e) => set("use_examples", e.target.value)}>
          <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
        </Select></Field>
        <Field label="Use stories" htmlFor="st-stories"><Select id="st-stories" value={String(form.use_stories ?? "medium")} onChange={(e) => set("use_stories", e.target.value)}>
          <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option>
        </Select></Field>
        <Field label="Sentence complexity" htmlFor="st-sent"><Input id="st-sent" value={String(form.sentence_complexity ?? "")} onChange={(e) => set("sentence_complexity", e.target.value)} /></Field>
        <Field label="Paragraph length" htmlFor="st-para"><Input id="st-para" value={String(form.paragraph_length ?? "")} onChange={(e) => set("paragraph_length", e.target.value)} /></Field>
        <Field label="Style notes" htmlFor="st-notes" className="col-span-3"><Textarea id="st-notes" value={String(form.style_notes ?? "")} onChange={(e) => set("style_notes", e.target.value)} /></Field>
      </div>
    </div>
  );
}

function ReviewTab({ chapterId, onChapterChanged }: { chapterId: string; onChapterChanged: () => void }) {
  const toast = useToast();
  const [mode, setMode] = useState<EditingMode>("proofreading");
  const [reviewing, setReviewing] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [activeSugId, setActiveSugId] = useState<string | null>(null);

  const { data: suggestions, refetch: refetchSuggestions } = useQuery({
    queryKey: ["editing-suggestions", chapterId, statusFilter],
    queryFn: () => editingApi.listSuggestions(chapterId, { status: statusFilter || undefined }),
    enabled: true,
  });
  const { data: summary, refetch: refetchSummary } = useQuery({
    queryKey: ["editing-summary", chapterId],
    queryFn: () => editingApi.reviewSummary(chapterId),
  });

  const runReview = async () => {
    setReviewing(true);
    try {
      await editingApi.review(chapterId, { mode, selected_text: null, instruction: null, provider: null, model: null });
      await refetchSuggestions();
      await refetchSummary();
      toast({ title: "Review completed", variant: "success" });
    } catch (e: unknown) {
      toast({ title: "Review failed", description: String(e), variant: "error" });
    } finally {
      setReviewing(false);
    }
  };

  const onAccept = async (sugId: string) => {
    try {
      await editingApi.acceptSuggestion(sugId);
      await refetchSuggestions();
      await refetchSummary();
      onChapterChanged();
      toast({ title: "Accepted", variant: "success" });
    } catch (e: unknown) { toast({ title: "Failed", description: String(e), variant: "error" }); }
  };
  const onReject = async (sugId: string) => {
    try {
      await editingApi.rejectSuggestion(sugId);
      await refetchSuggestions();
      await refetchSummary();
      toast({ title: "Rejected", variant: "success" });
    } catch (e: unknown) { toast({ title: "Failed", description: String(e), variant: "error" }); }
  };
  const onIgnore = async (sugId: string) => {
    try {
      await editingApi.ignoreSuggestion(sugId);
      await refetchSuggestions();
      await refetchSummary();
      toast({ title: "Ignored", variant: "success" });
    } catch (e: unknown) { toast({ title: "Failed", description: String(e), variant: "error" }); }
  };
  const onRegenerate = async (sugId: string) => {
    try {
      await editingApi.regenerateSuggestion(sugId);
      await refetchSuggestions();
      await refetchSummary();
      toast({ title: "Regenerated", variant: "success" });
    } catch (e: unknown) { toast({ title: "Failed", description: String(e), variant: "error" }); }
  };
  const onAcceptAll = async () => {
    try {
      await editingApi.acceptAll(chapterId);
      await refetchSuggestions();
      await refetchSummary();
      onChapterChanged();
      toast({ title: "All accepted", variant: "success" });
    } catch (e: unknown) { toast({ title: "Failed", description: String(e), variant: "error" }); }
  };
  const onRejectAll = async () => {
    try {
      await editingApi.rejectAll(chapterId);
      await refetchSuggestions();
      await refetchSummary();
      toast({ title: "All rejected", variant: "success" });
    } catch (e: unknown) { toast({ title: "Failed", description: String(e), variant: "error" }); }
  };

  const filtered = useMemo(() => {
    if (!suggestions) return [];
    return suggestions.filter((s) => {
      if (categoryFilter && s.category !== categoryFilter) return false;
      if (severityFilter && s.severity !== severityFilter) return false;
      return true;
    });
  }, [suggestions, categoryFilter, severityFilter]);

  const categories = [...new Set(suggestions?.map((s) => s.category) ?? [])];

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2">
        <Select id="rw-mode" value={mode} onChange={(e) => setMode(e.target.value as EditingMode)} className="w-48">
          <option value="proofreading">Proofread</option>
          <option value="clarity_editing">Clarity</option>
          <option value="style_editing">Style</option>
          <option value="consistency_check">Consistency</option>
          <option value="repetition_check">Repetition</option>
          <option value="full_review">Full Review</option>
        </Select>
        <Button onClick={runReview} disabled={reviewing}>{reviewing ? "Reviewing…" : "Run Review"}</Button>
        <span className="mx-2 text-muted-foreground">|</span>
        {categories.map((c) => (
          <Badge key={c} variant={categoryFilter === c ? "default" : "outline"}
                 className="cursor-pointer text-[10px]" onClick={() => setCategoryFilter(categoryFilter === c ? "" : c)}>
            {c}
          </Badge>
        ))}
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-32 ml-auto">
          <option value="pending">Pending</option><option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option><option value="ignored">Ignored</option>
          <option value="">All</option>
        </Select>
      </div>

      {/* Bulk actions */}
      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={onAcceptAll}>Accept all</Button>
        <Button size="sm" variant="outline" onClick={onRejectAll}>Reject all</Button>
      </div>

      {/* Summary dashboard */}
      {summary && (
        <div className="flex flex-wrap gap-3 rounded-md border border-border bg-background p-3 text-xs">
          <span>Total: <strong>{summary.total}</strong></span>
          {Object.entries(summary.by_category ?? {}).map(([k, v]) => (
            <span key={k}>{k}: <strong>{v}</strong></span>
          ))}
          <span className="ml-auto">{summary.high_severity > 0 ? `High: ${summary.high_severity}` : ""}</span>
          <span className="text-muted-foreground ml-2">Pending: {summary.pending} | Acc: {summary.accepted} | Rej: {summary.rejected}</span>
        </div>
      )}

      {/* Suggestions list */}
      <div className="space-y-2 max-h-[60vh] overflow-y-auto">
        {reviewing ? <Skeleton className="h-32 w-full" /> : null}
        {!reviewing && filtered.length === 0 && (
          <p className="text-sm text-muted-foreground">No suggestions to show. Select a mode and run a review.</p>
        )}
        {filtered.map((sug) => (
          <Card key={sug.id}>
            <CardContent className="p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant={sug.severity === "high" ? "destructive" : sug.severity === "medium" ? "warning" : "outline"} className="text-[10px]">{sug.category}</Badge>
                  <span className="text-[10px] text-muted-foreground">{sug.severity}</span>
                </div>
                <span className="text-[10px] text-muted-foreground">{sug.status}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <p className="text-[10px] font-medium text-muted-foreground mb-1">Original</p>
                  <p className="rounded bg-destructive/10 px-2 py-1 text-xs">{sug.original_text}</p>
                </div>
                {sug.suggested_text && (
                  <div>
                    <p className="text-[10px] font-medium text-muted-foreground mb-1">Suggested</p>
                    <p className="rounded bg-emerald-100 dark:bg-emerald-950 px-2 py-1 text-xs">{sug.suggested_text}</p>
                  </div>
                )}
              </div>
              {sug.explanation && <p className="text-xs text-muted-foreground">{sug.explanation}</p>}
              {sug.status === "pending" && (
                <div className="flex gap-2 pt-1">
                  <Button size="sm" variant="default" onClick={() => onAccept(sug.id)}>Accept</Button>
                  <Button size="sm" variant="outline" onClick={() => onReject(sug.id)}>Reject</Button>
                  <Button size="sm" variant="ghost" onClick={() => onIgnore(sug.id)}>Ignore</Button>
                  <Button size="sm" variant="ghost" onClick={() => onRegenerate(sug.id)}>↻ Regenerate</Button>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
