"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { useProjectBook } from "@/hooks/use-books";
import { bookWritingApi } from "@/lib/api/bookWriting";
import { editingApi } from "@/lib/api/editing";
import { jobsApi } from "@/lib/api/jobs";
import { JobProgressCard } from "@/components/shared/job-progress-card";
import type { WritingChapter } from "@/types/api";
import {
  IconBook, IconSparkles, IconExport, IconPlus, IconChevronRight,
  IconChevronLeft, IconImage, IconCover, IconCheck, IconTranslate,
  IconMarketing, IconProof,
} from "@/components/ui/icons";

type LeftTab = "chapters" | "outline" | "versions";
type RightTool = "export" | "images" | "cover" | "validator" | "translate" | "marketing" | "proofread" | null;

interface Tool { key: RightTool; label: string; icon: React.FC<React.SVGProps<SVGSVGElement>> }

const TOOLS: Tool[] = [
  { key: "export", label: "Export", icon: IconExport },
  { key: "images", label: "Images", icon: IconImage },
  { key: "cover", label: "Book Cover", icon: IconCover },
  { key: "validator", label: "KDP Validator", icon: IconCheck },
  { key: "proofread", label: "Proofreader", icon: IconProof },
  { key: "translate", label: "Translate", icon: IconTranslate },
  { key: "marketing", label: "Marketing", icon: IconMarketing },
];

// ---- Version History sub-component ------------------------------------------
function VersionHistory({ chapterId }: { chapterId: string }) {
  const { data: versions } = useQuery({
    queryKey: ["chapter-versions", chapterId],
    queryFn: () => bookWritingApi.listVersions(chapterId),
    enabled: Boolean(chapterId),
  });
  if (!versions || versions.length === 0) return <p className="text-xs text-muted-foreground p-2">No versions yet.</p>;
  return versions.slice(0, 10).map(v => (
    <div key={v.id} className="rounded border border-border p-2 text-[10px]">
      <span className="font-medium">v{v.version_number}</span>
      <Badge variant="outline" className="ml-2 text-[9px]">{v.version_type}</Badge>
      <span className="ml-2 text-muted-foreground">{v.word_count}w</span>
    </div>
  ));
}

// ---- Right panel tool sub-components ----------------------------------------
function ExportPanel({ bookId }: { bookId: string }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [fmt, setFmt] = useState("docx");
  const toast = useToast();
  async function start() {
    try { const r = await jobsApi.startExport(bookId, fmt as "docx" | "pdf" | "epub"); setJobId(r.id); }
    catch (e) { toast({ title: "Export failed", description: String(e), variant: "error" }); }
  }
  return (
    <div className="space-y-2 p-1">
      <div className="flex gap-1">
        {(["docx", "pdf", "epub"] as const).map(f => (
          <button key={f} onClick={() => setFmt(f)} className={`rounded px-2 py-1 text-[10px] font-medium ${fmt === f ? "bg-primary text-primary-foreground" : "bg-secondary"}`}>.{f.toUpperCase()}</button>
        ))}
      </div>
      <Button size="sm" className="w-full" onClick={start}><IconExport className="mr-1 h-3 w-3" /> Export {fmt.toUpperCase()}</Button>
      {jobId && <JobProgressCard jobId={jobId} title={`${fmt.toUpperCase()} export`} />}
    </div>
  );
}

function CoverPanel({ bookId }: { bookId: string }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const toast = useToast();
  async function generate() {
    try { const r = await jobsApi.startCover(bookId); setJobId(r.id); }
    catch (e) { toast({ title: "Cover failed", description: String(e), variant: "error" }); }
  }
  return (
    <div className="space-y-2 p-1">
      <p className="text-xs text-muted-foreground">Generate a professional book cover</p>
      <Button size="sm" className="w-full" onClick={generate}><IconCover className="mr-1 h-3 w-3" /> Generate cover</Button>
      {jobId && <JobProgressCard jobId={jobId} title="Cover generation" />}
    </div>
  );
}

function KdpPanel({ bookId }: { bookId: string }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const toast = useToast();
  async function run() {
    try { const r = await jobsApi.startKdpValidate(bookId); setJobId(r.id); }
    catch (e) { toast({ title: "Validation failed", description: String(e), variant: "error" }); }
  }
  return (
    <div className="space-y-2 p-1">
      <p className="text-xs text-muted-foreground">Check your book against KDP requirements</p>
      <Button size="sm" className="w-full" onClick={run}><IconCheck className="mr-1 h-3 w-3" /> Run validation</Button>
      {jobId && <JobProgressCard jobId={jobId} title="KDP validation" />}
    </div>
  );
}

function ProofreadPanel({ chapterId }: { chapterId: string | null }) {
  const toast = useToast();
  const qc = useQueryClient();
  const { data: suggestions } = useQuery({
    queryKey: ["editing-suggestions", chapterId],
    queryFn: () => editingApi.listSuggestions(chapterId!, { status: "pending" }),
    enabled: Boolean(chapterId),
  });
  async function run() {
    if (!chapterId) return;
    try {
      await editingApi.review(chapterId, { mode: "proofreading" });
      void qc.invalidateQueries({ queryKey: ["editing-suggestions", chapterId] });
      toast({ title: "Review complete", variant: "success" });
    } catch (e) { toast({ title: "Review failed", description: String(e), variant: "error" }); }
  }
  return (
    <div className="space-y-2 p-1">
      <p className="text-xs text-muted-foreground">Catch grammar, spelling, and style issues</p>
      <Button size="sm" className="w-full" onClick={run} disabled={!chapterId}><IconProof className="mr-1 h-3 w-3" /> Proofread chapter</Button>
      {suggestions && suggestions.length > 0 && <p className="text-[10px] text-muted-foreground">{suggestions.length} pending suggestions</p>}
    </div>
  );
}

function TranslatePanel({ bookId }: { bookId: string }) {
  const [target, setTarget] = useState("es");
  const [jobId, setJobId] = useState<string | null>(null);
  const toast = useToast();
  const langs = [{ code: "es", name: "Spanish" }, { code: "fr", name: "French" }, { code: "de", name: "German" }, { code: "pt", name: "Portuguese" }, { code: "it", name: "Italian" }, { code: "ja", name: "Japanese" }, { code: "zh", name: "Chinese" }, { code: "ar", name: "Arabic" }, { code: "ru", name: "Russian" }, { code: "ko", name: "Korean" }, { code: "nl", name: "Dutch" }];
  async function start() {
    try { const r = await jobsApi.startTranslation(bookId, "en", target); setJobId(r.id); }
    catch (e) { toast({ title: "Translation failed", description: String(e), variant: "error" }); }
  }
  return (
    <div className="space-y-2 p-1">
      <select className="w-full rounded border border-input bg-background px-2 py-1 text-xs" value={target} onChange={(e) => setTarget((e.target as HTMLSelectElement).value)}>
        {langs.map(l => <option key={l.code} value={l.code}>{l.name}</option>)}
      </select>
      <Button size="sm" className="w-full" onClick={start}><IconTranslate className="mr-1 h-3 w-3" /> Translate</Button>
      {jobId && <JobProgressCard jobId={jobId} title={`Translation to ${target}`} />}
    </div>
  );
}

function MarketingPanel({ bookId }: { bookId: string }) {
  const [asset, setAsset] = useState("amazon_description");
  const [jobId, setJobId] = useState<string | null>(null);
  const toast = useToast();
  const items = [
    { value: "amazon_description", name: "Amazon Description" },
    { value: "social_post", name: "Social Post" },
    { value: "email_blast", name: "Email Blast" },
    { value: "press_release", name: "Press Release" },
    { value: "author_bio", name: "Author Bio" },
  ];
  async function generate() {
    try { const r = await jobsApi.startMarketing(bookId, asset); setJobId(r.id); }
    catch (e) { toast({ title: "Marketing generation failed", description: String(e), variant: "error" }); }
  }
  return (
    <div className="space-y-2 p-1">
      <select className="w-full rounded border border-input bg-background px-2 py-1 text-xs" value={asset} onChange={(e) => setAsset((e.target as HTMLSelectElement).value)}>
        {items.map(a => <option key={a.value} value={a.value}>{a.name}</option>)}
      </select>
      <Button size="sm" className="w-full" onClick={generate}><IconMarketing className="mr-1 h-3 w-3" /> Generate</Button>
      {jobId && <JobProgressCard jobId={jobId} title={`Marketing: ${asset}`} />}
    </div>
  );
}

function ImagesPanel() {
  return <p className="text-xs text-muted-foreground p-2">AI image generation coming soon.</p>;
}

// ---- Main Workspace Page ----------------------------------------------------
export default function BookWorkspacePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const router = useRouter();
  const toast = useToast();
  const qc = useQueryClient();

  const { data: book } = useProjectBook(projectId);
  const writingBookId = (book?.metadata_json as Record<string, unknown> | undefined)?.writing_book_id as string | undefined;

  const [activeChapterId, setActiveChapterId] = useState<string | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [saveStatus, setSaveStatus] = useState<"saved" | "unsaved" | "saving" | "failed">("saved");
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [leftTab, setLeftTab] = useState<LeftTab>("chapters");
  const [rightTool, setRightTool] = useState<RightTool>(null);
  const [lastSaved, setLastSaved] = useState(Date.now());

  const { data: chapters } = useQuery({
    queryKey: ["writing-chapters", writingBookId],
    queryFn: () => bookWritingApi.listChapters(writingBookId!),
    enabled: Boolean(writingBookId),
  });

  const { data: blueprint } = useQuery({
    queryKey: ["writing-blueprint", writingBookId],
    queryFn: () => bookWritingApi.getBlueprint(writingBookId!),
    enabled: Boolean(writingBookId) && leftTab === "outline",
  });

  const { data: brief } = useQuery({
    queryKey: ["writing-brief", writingBookId],
    queryFn: () => bookWritingApi.getBrief(writingBookId!),
    enabled: Boolean(writingBookId) && leftTab === "outline",
  });

  useEffect(() => {
    if (chapters && chapters.length > 0 && !activeChapterId) {
      setActiveChapterId(chapters[0].id);
      setEditorContent(chapters[0].content);
    }
  }, [chapters, activeChapterId]);

  const createChapterM = useMutation({
    mutationFn: (title: string) => bookWritingApi.createChapter(writingBookId!, { title }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["writing-chapters", writingBookId] });
      toast({ title: "Chapter added", variant: "success" });
    },
  });

  const autosaveM = useMutation({
    mutationFn: ({ cid, content }: { cid: string; content: string }) =>
      bookWritingApi.autosave(writingBookId!, cid, content),
    onSuccess: () => { setSaveStatus("saved"); setLastSaved(Date.now()); },
    onError: () => setSaveStatus("failed"),
  });

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const doSave = useCallback((cid: string, content: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSaveStatus("saving");
      autosaveM.mutate({ cid, content });
    }, 1500);
  }, [autosaveM]);

  const handleChange = (val: string) => {
    setEditorContent(val);
    setSaveStatus("unsaved");
    if (activeChapterId) doSave(activeChapterId, val);
  };

  const handleAiAction = async (action: string) => {
    if (!activeChapterId) return;
    try {
      let result: WritingChapter;
      switch (action) {
        case "generate": result = await bookWritingApi.generateChapter(activeChapterId); break;
        case "continue": result = await bookWritingApi.continueChapter(activeChapterId); break;
        case "rewrite": result = await bookWritingApi.rewriteChapter(activeChapterId, {}); break;
        case "expand": result = await bookWritingApi.expandChapter(activeChapterId, {}); break;
        default: return;
      }
      setEditorContent(result.content);
      qc.invalidateQueries({ queryKey: ["writing-chapters", writingBookId] });
      toast({ title: "Chapter updated", variant: "success" });
    } catch (e) { toast({ title: "Failed", description: String(e), variant: "error" }); }
  };

  if (!writingBookId) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <IconBook className="h-12 w-12 text-muted-foreground" />
        <h2 className="text-lg font-semibold">No book in this project</h2>
        <p className="text-sm text-muted-foreground text-center">Generate a book from the new book page first.</p>
        <Button onClick={() => router.push("/new-book")}><IconPlus className="mr-2 h-4 w-4" />Create a book</Button>
      </div>
    );
  }

  const saveLabel = saveStatus === "saving" ? "Saving…" : saveStatus === "saved"
    ? `Saved ${Math.floor((Date.now() - lastSaved) / 1000)}s ago`
    : saveStatus === "unsaved" ? "Unsaved" : "Save failed";

  return (
    <div className="flex h-[calc(100vh-6rem)] -mx-4 -my-6">
      {/* ========== LEFT PANEL ========== */}
      {leftOpen && (
        <div className="flex h-full w-60 flex-shrink-0 flex-col border-r border-border bg-card">
          <div className="flex border-b border-border">
            {(["chapters", "outline", "versions"] as LeftTab[]).map(t => (
              <button key={t} onClick={() => setLeftTab(t)}
                className={`flex-1 py-2 text-xs font-medium ${
                  leftTab === t ? "border-b-2 border-primary text-foreground" : "text-muted-foreground"
                }`}>
                {t === "chapters" ? "Chapters" : t === "outline" ? "Outline" : "Versions"}
              </button>
            ))}
            <Button variant="ghost" size="sm" onClick={() => setLeftOpen(false)}><IconChevronLeft className="h-3.5 w-3.5" /></Button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {leftTab === "chapters" && (
              <div className="p-2 space-y-0.5">
                <div className="flex items-center justify-between px-2 py-1">
                  <span className="text-[10px] text-muted-foreground font-medium uppercase">Chapters</span>
                  <Button variant="ghost" size="sm" onClick={() => { const t = window.prompt("Chapter title:"); if (t) createChapterM.mutate(t); }}><IconPlus className="h-3.5 w-3.5" /></Button>
                </div>
                {chapters?.map(ch => (
                  <button key={ch.id} onClick={() => { setActiveChapterId(ch.id); setEditorContent(ch.content); }}
                    className={`w-full rounded px-2 py-1.5 text-left text-xs transition-colors ${ch.id === activeChapterId ? "bg-secondary" : "hover:bg-secondary/50"}`}>
                    <div className="font-medium truncate">{ch.chapter_number}. {ch.title}</div>
                    <div className="flex items-center gap-1 mt-0.5">
                      <Badge variant="outline" className="text-[9px] py-0 h-4">{ch.status}</Badge>
                      <span className="text-[10px] text-muted-foreground">{ch.actual_word_count}w</span>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {leftTab === "outline" && (
              <div className="p-2 space-y-3 text-xs">
                {brief?.working_title && (
                  <div className="rounded bg-secondary/30 p-2">
                    <div className="font-medium">{brief.working_title}</div>
                    {brief.subtitle && <div className="text-muted-foreground">{brief.subtitle}</div>}
                  </div>
                )}
                {brief?.book_purpose && <div><span className="font-medium text-muted-foreground">Purpose: </span>{brief.book_purpose}</div>}
                <div><span className="font-medium text-muted-foreground">Chapters: </span>{chapters?.length ?? 0}</div>
                {blueprint?.chapters && blueprint.chapters.length > 0 && (
                  <div className="space-y-1">
                    <p className="font-medium text-muted-foreground">Structure:</p>
                    {blueprint.chapters.map((ch, i) => (
                      <div key={i} className="pl-2 border-l-2 border-border">
                        <span className="font-medium">{i + 1}. {ch.title}</span>
                        {ch.objective && <p className="text-[10px] text-muted-foreground">{ch.objective}</p>}
                        {ch.estimated_word_count && <p className="text-[10px] text-muted-foreground">~{ch.estimated_word_count}w</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {leftTab === "versions" && (
              <div className="p-2 space-y-2">
                {activeChapterId ? <VersionHistory chapterId={activeChapterId} /> : <p className="text-xs text-muted-foreground p-2">Select a chapter to see version history.</p>}
              </div>
            )}
          </div>
        </div>
      )}
      {!leftOpen && (
        <Button variant="outline" size="sm" className="self-start mt-4 rounded-l-md h-8" onClick={() => setLeftOpen(true)}>
          <IconChevronRight className="h-3.5 w-3.5" />
        </Button>
      )}

      {/* ========== CENTER EDITOR ========== */}
      <div className="flex flex-1 flex-col min-w-0 border-x border-border">
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card/50 shrink-0">
          <h2 className="text-sm font-semibold truncate">{book?.title ?? "Book Workspace"}</h2>
          <span className={`text-xs ${saveStatus === "saving" ? "text-amber-600" : saveStatus === "saved" ? "text-emerald-600" : saveStatus === "failed" ? "text-red-600" : "text-muted-foreground"}`}>{saveLabel}</span>
        </div>
        <div className="flex items-center gap-1 px-4 py-1.5 border-b border-border bg-card/30 shrink-0">
          {(["generate", "continue", "rewrite", "expand"] as const).map(a => (
            <button key={a} className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-secondary" onClick={() => handleAiAction(a)} disabled={!activeChapterId}>
              <IconSparkles className="mr-1 h-3.5 w-3.5 inline" /> {a === "generate" ? "Write" : a === "continue" ? "Continue" : a === "rewrite" ? "Rewrite" : "Expand"}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {activeChapterId ? (
            <Textarea className="min-h-full w-full rounded-md border border-input bg-background px-4 py-3 text-sm leading-relaxed resize-none" value={editorContent} onChange={e => handleChange(e.target.value)} placeholder="Your chapter content…" />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Select a chapter from the left panel to start editing.</div>
          )}
        </div>
      </div>

      {/* ========== RIGHT TOOLS PANEL ========== */}
      {rightOpen && (
        <div className="flex h-full w-60 flex-shrink-0 flex-col border-l border-border bg-card">
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <h3 className="text-sm font-semibold">{rightTool ? (TOOLS.find(t => t.key === rightTool)?.label ?? "Tools") : "Tools"}</h3>
            <Button variant="ghost" size="sm" onClick={() => { setRightTool(null); setRightOpen(false); }}><IconChevronRight className="h-3.5 w-3.5" /></Button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {!rightTool ? (
              TOOLS.map(t => { const Icon = t.icon; return (
                <button key={t.key} onClick={() => setRightTool(t.key)} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-muted-foreground hover:bg-secondary hover:text-foreground"><Icon className="h-3.5 w-3.5" />{t.label}</button>
              );})
            ) : (
              <>
                {rightTool === "export" && <ExportPanel bookId={writingBookId} />}
                {rightTool === "images" && <ImagesPanel />}
                {rightTool === "cover" && <CoverPanel bookId={writingBookId} />}
                {rightTool === "validator" && <KdpPanel bookId={writingBookId} />}
                {rightTool === "proofread" && <ProofreadPanel chapterId={activeChapterId} />}
                {rightTool === "translate" && <TranslatePanel bookId={writingBookId} />}
                {rightTool === "marketing" && <MarketingPanel bookId={writingBookId} />}
                <div className="pt-2 border-t border-border">
                  <button className="text-[10px] text-muted-foreground hover:text-foreground" onClick={() => setRightTool(null)}>← Back to all tools</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
      {!rightOpen && (
        <Button variant="outline" size="sm" className="shrink-0 self-start mt-10 rounded-l-md h-8" onClick={() => setRightOpen(true)}><IconChevronRight className="h-3.5 w-3.5" /></Button>
      )}
    </div>
  );
}