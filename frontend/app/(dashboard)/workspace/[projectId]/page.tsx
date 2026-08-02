"use client";

// Unified book workspace — the single place to review, write, and publish a book.
// Left: chapters / outline / bookmarks / versions / activity.
// Center: rich text editor with autosave + AI quick actions.
// Right: AI assistant, proofreader, images, cover, marketing, translation,
// validator, export. A floating progress panel tracks background generation.
//
// Everything is wired end-to-end: UI -> API -> backend -> database, with live
// WebSocket updates for progress, activities, notifications, and versions.

import { use, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useProject } from "@/hooks/use-projects";
import { useProjectBook } from "@/hooks/use-books";
import { bookWritingApi } from "@/lib/api/bookWriting";
import { studioApi, type ProjectStage } from "@/lib/api/studio";
import { toastError } from "@/lib/errors";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/skeleton";
import {
  IconMenu,
  IconClose,
  IconSparkles,
  IconBook,
  IconHistory,
  IconProof,
  IconExport,
  IconImage,
  IconCover,
  IconCheck,
  IconTranslate,
  IconMarketing,
  IconPen,
} from "@/components/ui/icons";
import { useAutosave } from "@/hooks/use-autosave";
import { useShortcuts } from "@/hooks/use-shortcuts";
import { useStudioSocket, type StudioWsEvent } from "@/hooks/use-studio-ws";
import { RichEditor } from "@/components/studio/rich-editor";
import { ProgressPanel } from "@/components/studio/progress-panel";
import { NotificationCenter } from "@/components/studio/notification-center";
import { StageBadge } from "@/components/studio/stage-badge";
import { ActivityTimeline } from "@/components/studio/activity-timeline";
import { SearchBox } from "@/components/studio/search-box";
import dynamic from "next/dynamic";

// Right-panel tools are only needed when the workspace is open — load them
// lazily so the dashboard and wizard stay light.
const loadPanel = () => import("@/components/studio/panels");
function PanelFallback() {
  return (
    <div className="flex justify-center p-6">
      <Spinner className="h-4 w-4" />
    </div>
  );
}
const AssistantPanel = dynamic(() => loadPanel().then((m) => m.AssistantPanel), { ssr: false, loading: PanelFallback });
const ExportPanel = dynamic(() => loadPanel().then((m) => m.ExportPanel), { ssr: false, loading: PanelFallback });
const ImagesPanel = dynamic(() => loadPanel().then((m) => m.ImagesPanel), { ssr: false, loading: PanelFallback });
const CoverPanel = dynamic(() => loadPanel().then((m) => m.CoverPanel), { ssr: false, loading: PanelFallback });
const ValidatorPanel = dynamic(() => loadPanel().then((m) => m.ValidatorPanel), { ssr: false, loading: PanelFallback });
const ProofreaderPanel = dynamic(() => loadPanel().then((m) => m.ProofreaderPanel), { ssr: false, loading: PanelFallback });
const TranslationPanel = dynamic(() => loadPanel().then((m) => m.TranslationPanel), { ssr: false, loading: PanelFallback });
const MarketingPanel = dynamic(() => loadPanel().then((m) => m.MarketingPanel), { ssr: false, loading: PanelFallback });

type LeftTab = "chapters" | "outline" | "bookmarks" | "versions" | "activity";

const LEFT_TABS: Array<{ key: LeftTab; label: string }> = [
  { key: "chapters", label: "Chapters" },
  { key: "outline", label: "Outline" },
  { key: "bookmarks", label: "Bookmarks" },
  { key: "versions", label: "Versions" },
  { key: "activity", label: "Activity" },
];

const TOOLS: Array<{ key: string; label: string; icon: React.FC<React.SVGProps<SVGSVGElement>> }> = [
  { key: "assistant", label: "AI Assistant", icon: IconSparkles },
  { key: "proofreader", label: "Proofreader", icon: IconProof },
  { key: "images", label: "Images", icon: IconImage },
  { key: "cover", label: "Cover", icon: IconCover },
  { key: "marketing", label: "Marketing", icon: IconMarketing },
  { key: "translation", label: "Translate", icon: IconTranslate },
  { key: "validator", label: "KDP Validator", icon: IconCheck },
  { key: "export", label: "Export", icon: IconExport },
];

const AI_ACTIONS: Array<{ key: "fix_grammar" | "shorten" | "expand" | "continue" | "rewrite"; label: string }> = [
  { key: "fix_grammar", label: "Fix grammar" },
  { key: "shorten", label: "Shorten" },
  { key: "expand", label: "Expand" },
  { key: "continue", label: "Continue" },
  { key: "rewrite", label: "Rewrite" },
];

const SAVE_LABELS: Record<string, string> = {
  idle: "All changes saved",
  saving: "Saving…",
  saved: "Saved",
  failed: "Save failed — retrying",
};

export default function WorkspacePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data: project } = useProject(projectId);
  const { data: book } = useProjectBook(projectId);

  const [leftTab, setLeftTab] = useState<LeftTab>("chapters");
  const [rightTool, setRightTool] = useState<string | null>(searchParams.get("tool") ?? "assistant");
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [activeChapterId, setActiveChapterId] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [wsTick, setWsTick] = useState(0);
  const [versionDraft, setVersionDraft] = useState("");
  const [activeJobId, setActiveJobId] = useState<string | null>(searchParams.get("generating"));
  const insertMarkdownRef = useRef<((markdown: string) => void) | null>(null);

  const bookId = book?.metadata_json?.writing_book_id ?? null;

  const { data: chapters = [], isLoading: chaptersLoading } = useQuery({
    queryKey: ["writing-chapters", projectId],
    queryFn: () => bookWritingApi.listChapters(bookId as string),
    enabled: Boolean(bookId),
  });
  const writingBookId = bookId ?? chapters[0]?.book_id ?? null;

  const activeChapter = chapters.find((chapter) => chapter.id === activeChapterId) ?? null;

  // Load chapter content into the editor when switching chapters.
  useEffect(() => {
    if (activeChapter) setEditorContent(activeChapter.content ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChapterId]);

  const autosave = useAutosave(projectId, activeChapterId ?? undefined, editorContent);

  const selectChapter = useCallback(
    async (chapterId: string) => {
      await autosave.saveNow();
      setActiveChapterId(chapterId);
    },
    [autosave],
  );

  const refreshProjectData = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["writing-chapters", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["project-book", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["projects", "detail", projectId] });
  }, [queryClient, projectId]);

  const handleWsEvent = useCallback(
    (event: StudioWsEvent) => {
      if (event.type === "job.progress") {
        const jobId = event.payload.job_id;
        if (typeof jobId === "string") setActiveJobId(jobId);
        return;
      }
      if (event.type === "job.terminal") {
        const status = event.payload.status;
        const title = String(event.payload.title ?? "Job finished");
        if (status === "COMPLETED") {
          toast({ title, variant: "success" });
          refreshProjectData();
        } else if (status === "FAILED") {
          toast({ title, description: String(event.payload.body ?? ""), variant: "error" });
        }
        setWsTick((tick) => tick + 1);
        return;
      }
      if (event.type === "activity.created" || event.type === "notification.created") {
        setWsTick((tick) => tick + 1);
        return;
      }
      if (event.type === "version.restored") {
        refreshProjectData();
        toast({ title: "Version restored", variant: "success" });
        return;
      }
      if (event.type === "generation.completed") {
        refreshProjectData();
        toast({
          title: "Book generation complete",
          description: "Your book is ready to review in the editor.",
          variant: "success",
        });
        return;
      }
      if (event.type === "stage.changed") {
        void queryClient.invalidateQueries({ queryKey: ["projects", "detail", projectId] });
      }
    },
    [queryClient, projectId, refreshProjectData, toast],
  );
  useStudioSocket(projectId, handleWsEvent);

  useShortcuts({
    onSave: () => {
      void autosave.saveNow();
    },
    onSearch: () => {
      document.querySelector<HTMLInputElement>("[data-search-input]")?.focus();
    },
  });

  const runAiAction = useCallback(
    async (action: "fix_grammar" | "shorten" | "expand" | "continue" | "rewrite") => {
      if (!activeChapterId) {
        toast({ title: "Select a chapter first", variant: "info" });
        return;
      }
      try {
        const response = await studioApi.assistant(projectId, {
          message: `Apply ${action.replace("_", " ")} to this chapter.`,
          chapter_id: activeChapterId,
          action,
        });
        if (response.applied && response.new_content) {
          setEditorContent(response.new_content);
          toast({ title: `${action.replace("_", " ")} applied`, variant: "success" });
        } else {
          toast({ title: response.reply, variant: "info" });
        }
      } catch (error) {
        toast(toastError(error));
      }
    },
    [activeChapterId, projectId, toast],
  );

  const onGenerationDone = useCallback(
    (job: { status: string }) => {
      if (job.status === "COMPLETED") {
        refreshProjectData();
        toast({ title: "Book generation complete", variant: "success" });
      }
      setActiveJobId(null);
      router.replace(`/workspace/${projectId}`);
    },
    [projectId, refreshProjectData, router, toast],
  );

  const stage = (project?.stage ?? "draft") as ProjectStage;
  const saveLabel = SAVE_LABELS[autosave.status] ?? SAVE_LABELS.idle;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] min-h-0 flex-col bg-background">
      {/* ===== Header ===== */}
      <header className="flex shrink-0 items-center gap-3 border-b border-border bg-card/60 px-4 py-2">
        <Button
          variant="ghost"
          size="sm"
          className="lg:hidden"
          onClick={() => setLeftOpen((open) => !open)}
          aria-label="Toggle chapters panel"
        >
          <IconMenu className="h-4 w-4" />
        </Button>
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold text-foreground">
            {project?.title ?? "Book Workspace"}
          </h1>
          <p className="text-[10px] text-muted-foreground">
            {saveLabel}
            {autosave.lastSavedAt
              ? ` · Last saved ${autosave.lastSavedAt.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`
              : ""}
          </p>
        </div>

        <div className="ml-2 hidden md:block">
          <StageBadge
            projectId={projectId}
            stage={stage}
            onChanged={() => void queryClient.invalidateQueries({ queryKey: ["projects", "detail", projectId] })}
          />
        </div>

        <div className="ml-auto flex items-center gap-2">
          <div className="hidden sm:block">
            <SearchBox
              projectId={projectId}
              onSelectChapter={(chapterId) => void selectChapter(chapterId)}
              onInsertImage={(markdown) => insertMarkdownRef.current?.(markdown)}
            />
          </div>
          <NotificationCenter refreshSignal={wsTick} />
          <Button
            variant="ghost"
            size="sm"
            className="lg:hidden"
            onClick={() => setRightOpen((open) => !open)}
            aria-label="Toggle tools panel"
          >
            <IconSparkles className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {/* ===== Body: three panels ===== */}
      <div className="flex min-h-0 flex-1">
        {/* ===== LEFT PANEL ===== */}
        {leftOpen ? (
          <aside className="fixed inset-y-[3.5rem] left-0 z-40 flex w-64 flex-col border-r border-border bg-card lg:static lg:z-auto lg:inset-auto lg:w-60">
            <div className="flex items-center justify-between border-b border-border px-2 py-1.5">
              <nav className="flex gap-0.5 overflow-x-auto">
                {LEFT_TABS.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setLeftTab(tab.key)}
                    className={`shrink-0 rounded-md px-2 py-1 text-xs font-medium ${
                      leftTab === tab.key
                        ? "bg-secondary text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
              <Button variant="ghost" size="sm" className="lg:hidden" onClick={() => setLeftOpen(false)}>
                <IconClose className="h-3.5 w-3.5" />
              </Button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-2">
              {leftTab === "chapters" ? (
                chaptersLoading ? (
                  <Spinner label="Loading chapters…" />
                ) : chapters.length === 0 ? (
                  <p className="p-3 text-xs text-muted-foreground">
                    No chapters yet — press <span className="font-medium">Generate Book</span> from the
                    New Book page and the editor will open here automatically.
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {chapters.map((chapter) => (
                      <li key={chapter.id}>
                        <button
                          onClick={() => void selectChapter(chapter.id)}
                          className={`flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left text-xs ${
                            chapter.id === activeChapterId
                              ? "bg-primary/10 text-foreground"
                              : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                          }`}
                        >
                          <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded bg-secondary text-[9px] font-semibold text-muted-foreground">
                            {chapter.chapter_number}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate font-medium text-foreground">{chapter.title}</span>
                            <span className="text-[10px] text-muted-foreground">
                              {chapter.actual_word_count.toLocaleString()} words
                              {chapter.status === "failed" ? " · failed" : ""}
                            </span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )
              ) : null}

              {leftTab === "outline" ? (
                <ul className="space-y-2">
                  {chapters.map((chapter) => (
                    <li
                      key={chapter.id}
                      className="rounded-lg border border-border p-2"
                      onClick={() => void selectChapter(chapter.id)}
                    >
                      <p className="text-xs font-medium text-foreground">
                        {chapter.chapter_number}. {chapter.title}
                      </p>
                      {chapter.objective ? (
                        <p className="mt-0.5 line-clamp-3 text-[11px] text-muted-foreground">
                          {chapter.objective}
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}

              {leftTab === "bookmarks" ? <BookmarksTab projectId={projectId} activeChapter={activeChapter} onSelectChapter={selectChapter} /> : null}
              {leftTab === "versions" ? (
                <VersionsTab projectId={projectId} refreshSignal={wsTick} />
              ) : null}
              {leftTab === "activity" ? <ActivityTimeline projectId={projectId} refreshSignal={wsTick} /> : null}
            </div>
          </aside>
        ) : null}

        {/* ===== CENTER: EDITOR ===== */}
        <div className="flex min-w-0 flex-1 flex-col border-x border-border">
          {activeChapter ? (
            <div className="flex shrink-0 flex-wrap items-center gap-1 border-b border-border bg-card/30 px-3 py-1.5">
              <span className="mr-1 flex items-center gap-1 text-xs font-medium text-foreground">
                <IconPen className="h-3.5 w-3.5" />
                <span className="max-w-[16rem] truncate">{activeChapter.title}</span>
              </span>
              {AI_ACTIONS.map((action) => (
                <button
                  key={action.key}
                  onClick={() => void runAiAction(action.key)}
                  className="rounded px-2 py-1 text-[11px] text-muted-foreground hover:bg-secondary hover:text-foreground"
                >
                  <IconSparkles className="mr-1 inline h-3 w-3" />
                  {action.label}
                </button>
              ))}
            </div>
          ) : null}

          <div className="min-h-0 flex-1">
            {activeChapter ? (
              <RichEditor
                value={editorContent}
                onChange={setEditorContent}
                insertMarkdownRef={insertMarkdownRef}
                placeholder="Start writing your chapter…"
              />
            ) : chapters.length > 0 ? (
              <div className="flex h-full items-center justify-center p-6 text-center">
                <div>
                  <IconBook className="mx-auto h-8 w-8 text-muted-foreground" />
                  <p className="mt-2 text-sm text-muted-foreground">
                    Select a chapter from the left panel to start editing.
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex h-full items-center justify-center p-6 text-center">
                <div>
                  <IconSparkles className="mx-auto h-8 w-8 text-muted-foreground" />
                  <p className="mt-2 text-sm text-muted-foreground">
                    This book has no chapters yet. Go to{" "}
                    <button
                      className="font-medium text-primary hover:underline"
                      onClick={() => router.push("/new-book")}
                    >
                      New Book
                    </button>{" "}
                    and generate one — the editor will open automatically.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ===== RIGHT TOOLS PANEL ===== */}
        {rightOpen ? (
          <aside className="fixed inset-y-[3.5rem] right-0 z-40 flex w-64 flex-col border-l border-border bg-card lg:static lg:z-auto lg:inset-auto lg:w-72">
            <div className="flex shrink-0 items-center justify-between border-b border-border px-3 py-2">
              <h3 className="text-sm font-semibold text-foreground">
                {TOOLS.find((tool) => tool.key === rightTool)?.label ?? "Tools"}
              </h3>
              <Button variant="ghost" size="sm" className="lg:hidden" onClick={() => setRightOpen(false)}>
                <IconClose className="h-3.5 w-3.5" />
              </Button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-2">
              {!rightTool ? (
                <ul className="space-y-1">
                  {TOOLS.map((tool) => {
                    const Icon = tool.icon;
                    return (
                      <li key={tool.key}>
                        <button
                          onClick={() => setRightTool(tool.key)}
                          className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground"
                        >
                          <Icon className="h-3.5 w-3.5" />
                          {tool.label}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <>
                  {rightTool === "assistant" && (
                    <AssistantPanel
                      projectId={projectId}
                      writingBookId={writingBookId ?? ""}
                      activeChapterId={activeChapterId}
                      onApplyEdit={(content) => setEditorContent(content)}
                    />
                  )}
                  {rightTool === "proofreader" && (
                    <ProofreaderPanel
                      projectId={projectId}
                      writingBookId={writingBookId ?? ""}
                      activeChapterId={activeChapterId}
                    />
                  )}
                  {rightTool === "images" && (
                    <ImagesPanel
                      projectId={projectId}
                      writingBookId={writingBookId ?? ""}
                      activeChapterId={activeChapterId}
                      onInsertImage={(markdown) => insertMarkdownRef.current?.(markdown)}
                    />
                  )}
                  {rightTool === "cover" && (
                    <CoverPanel
                      projectId={projectId}
                      writingBookId={writingBookId ?? ""}
                      activeChapterId={activeChapterId}
                    />
                  )}
                  {rightTool === "marketing" && (
                    <MarketingPanel
                      projectId={projectId}
                      writingBookId={writingBookId ?? ""}
                      activeChapterId={activeChapterId}
                    />
                  )}
                  {rightTool === "translation" && (
                    <TranslationPanel
                      projectId={projectId}
                      writingBookId={writingBookId ?? ""}
                      activeChapterId={activeChapterId}
                    />
                  )}
                  {rightTool === "validator" && (
                    <ValidatorPanel
                      projectId={projectId}
                      writingBookId={writingBookId ?? ""}
                      activeChapterId={activeChapterId}
                    />
                  )}
                  {rightTool === "export" && (
                    <ExportPanel
                      projectId={projectId}
                      writingBookId={writingBookId ?? ""}
                      activeChapterId={activeChapterId}
                    />
                  )}
                </>
              )}
            </div>
          </aside>
        ) : null}
      </div>

      {/* ===== Floating generation progress ===== */}
      {activeJobId ? (
        <ProgressPanel
          projectId={projectId}
          jobId={activeJobId}
          onDone={onGenerationDone}
          onDismiss={() => {
            setActiveJobId(null);
            router.replace(`/workspace/${projectId}`);
          }}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bookmarks tab
// ---------------------------------------------------------------------------
function BookmarksTab({
  projectId,
  activeChapter,
  onSelectChapter,
}: {
  projectId: string;
  activeChapter: { id: string; title: string } | null;
  onSelectChapter: (chapterId: string) => Promise<void>;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data: bookmarks = [], isLoading } = useQuery({
    queryKey: ["bookmarks", projectId],
    queryFn: () => studioApi.listBookmarks(projectId),
  });

  const add = async () => {
    if (!activeChapter) {
      toast({ title: "Select a chapter first", variant: "info" });
      return;
    }
    try {
      await studioApi.createBookmark(projectId, {
        chapter_id: activeChapter.id,
        title: activeChapter.title,
        note: "Bookmarked from the workspace",
      });
      toast({ title: "Bookmark added", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: ["bookmarks", projectId] });
    } catch (error) {
      toast(toastError(error));
    }
  };

  const remove = async (bookmarkId: string) => {
    try {
      await studioApi.deleteBookmark(bookmarkId);
      void queryClient.invalidateQueries({ queryKey: ["bookmarks", projectId] });
    } catch (error) {
      toast(toastError(error));
    }
  };

  if (isLoading) return <Spinner label="Loading bookmarks…" />;

  return (
    <div className="space-y-2">
      <Button size="sm" className="w-full" onClick={() => void add()}>
        <IconBook className="mr-1 h-3.5 w-3.5" /> Bookmark this chapter
      </Button>
      {bookmarks.length === 0 ? (
        <p className="p-3 text-xs text-muted-foreground">
          No bookmarks yet — pin chapters you want to revisit.
        </p>
      ) : (
        bookmarks.map((bookmark) => (
          <div key={bookmark.id} className="rounded-lg border border-border p-2">
            <button
              className="block w-full text-left text-xs font-medium text-foreground hover:text-primary"
              onClick={() => bookmark.chapter_id && void onSelectChapter(bookmark.chapter_id)}
            >
              {bookmark.title}
            </button>
            {bookmark.note ? (
              <p className="mt-0.5 text-[11px] text-muted-foreground">{bookmark.note}</p>
            ) : null}
            <button
              className="mt-1 text-[10px] text-muted-foreground hover:text-destructive"
              onClick={() => void remove(bookmark.id)}
            >
              Remove
            </button>
          </div>
        ))
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Versions tab (restore points)
// ---------------------------------------------------------------------------
function VersionsTab({ projectId, refreshSignal }: { projectId: string; refreshSignal: number }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");

  const { data: versions = [], isLoading } = useQuery({
    queryKey: ["versions", projectId, refreshSignal],
    queryFn: () => studioApi.listVersions(projectId),
  });

  const saveVersion = async () => {
    const trimmed = label.trim();
    if (!trimmed) {
      toast({ title: "Give the version a name", variant: "info" });
      return;
    }
    try {
      await studioApi.createVersion(projectId, trimmed, "Manual restore point");
      setLabel("");
      toast({ title: "Version saved", variant: "success" });
      void queryClient.invalidateQueries({ queryKey: ["versions", projectId] });
    } catch (error) {
      toast(toastError(error));
    }
  };

  const restore = async (versionId: string, versionLabel: string) => {
    if (!window.confirm(`Restore "${versionLabel}"? A safety snapshot of the current state will be saved first.`)) {
      return;
    }
    try {
      const result = await studioApi.restoreVersion(versionId);
      toast({ title: result.message, variant: "success" });
      void queryClient.invalidateQueries({ queryKey: ["versions", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["writing-chapters", projectId] });
    } catch (error) {
      toast(toastError(error));
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-1">
        <input
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          placeholder="Version name (e.g. Before proofread)"
          className="min-w-0 flex-1 rounded-md border border-input bg-background px-2 py-1 text-xs outline-none focus:border-ring"
        />
        <Button size="sm" onClick={() => void saveVersion()}>
          Save
        </Button>
      </div>
      {isLoading ? (
        <Spinner label="Loading versions…" />
      ) : versions.length === 0 ? (
        <p className="p-3 text-xs text-muted-foreground">
          Restore points are created automatically after generation, proofreading,
          formatting, and translation — and you can save one anytime.
        </p>
      ) : (
        versions.map((version) => (
          <div key={version.id} className="rounded-lg border border-border p-2">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="flex items-center gap-1 text-xs font-medium text-foreground">
                  <IconHistory className="h-3 w-3 shrink-0 text-muted-foreground" />
                  <span className="truncate">{version.label}</span>
                </p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  {version.created_by === "auto" ? "Automatic · " : ""}
                  {new Date(version.created_at).toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
              <button
                onClick={() => void restore(version.id, version.label)}
                className="shrink-0 text-[10px] font-medium text-primary hover:underline"
              >
                Restore
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
