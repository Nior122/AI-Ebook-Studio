"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox, Input, Select, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  IconAlert,
  IconBook,
  IconChevronLeft,
  IconChevronRight,
  IconLayout,
  IconPen,
  IconSettings,
  IconSparkles,
} from "@/components/ui/icons";
import { cn } from "@/lib/utils";
import { generationApi, estimateChapters, WORD_COUNT_PRESETS, type BookSetup } from "@/lib/api/generation";
import { studioApi } from "@/lib/api/studio";
import { toastError } from "@/lib/errors";

// ---------------------------------------------------------------------------
// Constants (ported from the original single-page form)
// ---------------------------------------------------------------------------

const TONES = [
  { value: "conversational", label: "Conversational — friendly, like talking to a friend" },
  { value: "authoritative", label: "Authoritative — expert, confident" },
  { value: "friendly", label: "Friendly — warm and approachable" },
  { value: "professional", label: "Professional — business-like" },
  { value: "academic", label: "Academic — scholarly and rigorous" },
  { value: "humorous", label: "Humorous — light-hearted and witty" },
  { value: "inspirational", label: "Inspirational — motivating and uplifting" },
  { value: "neutral", label: "Neutral — balanced and objective" },
];

const STYLES = [
  { value: "practical_guide", label: "Practical guide" },
  { value: "storytelling", label: "Storytelling" },
  { value: "instructional", label: "Instructional" },
  { value: "analytical", label: "Analytical" },
  { value: "descriptive", label: "Descriptive" },
  { value: "persuasive", label: "Persuasive" },
];

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

const PROVIDERS = [
  { value: "openrouter", label: "OpenRouter (recommended)" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Google Gemini" },
  { value: "groq", label: "Groq (fast)" },
];

const CREATIVITIES = [
  { value: "balanced", label: "Balanced — good for most books" },
  { value: "precise", label: "Precise — factual, consistent" },
  { value: "creative", label: "Creative — more variety and flair" },
  { value: "fast", label: "Fast — quicker generation" },
];

const READING_LEVELS = [
  { value: "basic", label: "Basic — simple words and short sentences" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced — assumes prior knowledge" },
  { value: "general", label: "General — broad audience" },
];

const WRITING_QUALITIES = [
  { value: "draft", label: "Draft — get it written fast" },
  { value: "polished", label: "Polished — clean and consistent" },
  { value: "publication", label: "Publication — near-ready prose" },
];

const PAGE_SIZES = ["6x9", "8x10", "A4", "custom"] as const;

const PAGE_SIZE_LABELS: Record<string, string> = {
  "6x9": "6x9 (Trade)",
  "8x10": "8x10",
  A4: "A4",
  custom: "Custom size",
};

const FONTS = ["Georgia", "Merriweather", "Palatino", "Garamond", "Times New Roman", "Arial", "Helvetica"];

const IMAGE_STYLES = ["realistic", "illustration", "watercolor", "sketch", "comic"];

const IMAGE_RATIOS = [
  { value: "16:9", label: "16:9 (Landscape)" },
  { value: "square", label: "1:1 (Square)" },
  { value: "portrait", label: "3:4 (Portrait)" },
  { value: "4:3", label: "4:3" },
];

const CHAPTER_HEADING_STYLES = [
  { value: "numbered", label: "Numbered — Chapter 1, Chapter 2, …" },
  { value: "plain", label: "Plain — no numbers" },
  { value: "decorative", label: "Decorative — ornamented headings" },
];

/** Default model per provider (ported from the original form). */
const MODEL_MAP: Record<string, string> = {
  openrouter: "openai/gpt-4o-mini",
  openai: "gpt-4o-mini",
  gemini: "gemini-2.0-flash",
  groq: "llama-3.3-70b",
};

/** Per-provider model pick lists for the model select. */
const MODELS: Record<string, string[]> = {
  openrouter: [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "anthropic/claude-3-5-haiku",
    "google/gemini-1.5-flash",
    "meta-llama/llama-3.3-70b",
  ],
  openai: ["gpt-4o-mini", "gpt-4o"],
  gemini: ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-pro"],
  groq: ["llama-3.3-70b", "llama-3.1-8b-instant"],
};

/**
 * Word-count preset buttons. WORD_COUNT_PRESETS ships 5000/10000/15000/25000/50000;
 * we add 20000 and 30000 as extra client-side presets and keep them sorted.
 */
const WORD_PRESETS = Array.from(new Set<number>([...WORD_COUNT_PRESETS, 20000, 30000])).sort((a, b) => a - b);

// ---------------------------------------------------------------------------
// Wizard structure
// ---------------------------------------------------------------------------

type Step = "idle" | "submitting";

const SECTIONS = [
  { label: "Book details", description: "What is your book about, and who is it for?", icon: IconBook },
  { label: "Size", description: "How long should the book be?", icon: IconPen },
  { label: "Formatting", description: "Page, typography and image settings", icon: IconLayout },
  { label: "AI settings", description: "Provider, model and writing behaviour", icon: IconSettings },
  { label: "Special instructions", description: "Rules the AI follows throughout", icon: IconSparkles },
] as const;

type ClarifyQuestion = { id: string; question: string; placeholder: string };

export default function NewBookPage() {
  const router = useRouter();
  const toast = useToast();

  const [step, setStep] = useState<Step>("idle");
  const [serverError, setServerError] = useState<string | null>(null);

  // Clarification Q&A (inline panel)
  const [clarifyQuestions, setClarifyQuestions] = useState<ClarifyQuestion[]>([]);
  const [clarifyAnswers, setClarifyAnswers] = useState<Record<string, string>>({});

  // -- Section 1: Book details
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [author, setAuthor] = useState("");
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [language, setLanguage] = useState("en");
  const [tone, setTone] = useState("conversational");
  const [style, setStyle] = useState("practical_guide");
  const [bookPurpose, setBookPurpose] = useState("");

  // -- Section 2: Size
  const [wordCount, setWordCount] = useState(10000);
  const [customWords, setCustomWords] = useState("");
  const [useCustomWords, setUseCustomWords] = useState(false);
  const [chaptersOverride, setChaptersOverride] = useState("");

  // -- Section 3: Formatting
  const [pageSize, setPageSize] = useState("6x9");
  const [customPageWidth, setCustomPageWidth] = useState("");
  const [customPageHeight, setCustomPageHeight] = useState("");
  const [marginTop, setMarginTop] = useState(1.0);
  const [marginBottom, setMarginBottom] = useState(1.0);
  const [marginLeft, setMarginLeft] = useState(1.0);
  const [marginRight, setMarginRight] = useState(1.0);
  const [headerFont, setHeaderFont] = useState("Georgia");
  const [headerSize, setHeaderSize] = useState(14);
  const [bodyFont, setBodyFont] = useState("Georgia");
  const [bodySize, setBodySize] = useState(12);
  const [lineSpacing, setLineSpacing] = useState(1.5);
  const [paragraphSpacing, setParagraphSpacing] = useState(1.0);
  const [chapterHeadingStyle, setChapterHeadingStyle] = useState("numbered");
  const [imageWidth, setImageWidth] = useState(6.0);
  const [imageRatio, setImageRatio] = useState("16:9");
  const [imageStyle, setImageStyle] = useState("realistic");

  // -- Section 4: AI settings
  const [provider, setProvider] = useState("openrouter");
  const [model, setModel] = useState(MODEL_MAP.openrouter);
  const [apiKey, setApiKey] = useState("");
  const [creativity, setCreativity] = useState("balanced");
  const [readingLevel, setReadingLevel] = useState("general");
  const [writingQuality, setWritingQuality] = useState("polished");
  const [useCitations, setUseCitations] = useState(false);
  const [generateExercises, setGenerateExercises] = useState(false);
  const [generateSummaries, setGenerateSummaries] = useState(false);

  // -- Section 5: Special instructions
  const [instructions, setInstructions] = useState("");

  // Section nav (refs + scroll listener)
  const sectionRefs = useRef<Array<HTMLDivElement | null>>([]);
  const [activeSection, setActiveSection] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      let current = 0;
      sectionRefs.current.forEach((el, i) => {
        if (el && el.getBoundingClientRect().top <= 140) current = i;
      });
      setActiveSection(current);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function scrollToSection(index: number) {
    const el = sectionRefs.current[index];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveSection(index);
    }
  }

  // Derived values
  const actualWords = useCustomWords && customWords ? Number(customWords) || 10000 : wordCount;
  const overrideChapters = chaptersOverride ? Number(chaptersOverride) || 0 : 0;
  const effectiveChapters = overrideChapters > 0 ? overrideChapters : estimateChapters(actualWords);

  // -------------------------------------------------------------------------
  // Smart checks (client-side, non-blocking warnings)
  // -------------------------------------------------------------------------

  function runSmartChecks(): string[] {
    const warnings: string[] = [];

    if (overrideChapters > 0 && actualWords > 0) {
      const perChapter = Math.round(actualWords / overrideChapters);
      if (perChapter < 400 || perChapter > 4000) {
        warnings.push(
          `Word count and chapter count don't match (~${perChapter.toLocaleString()} words/chapter). Consider adjusting the word count or the chapter count.`,
        );
      }
    }

    const audienceText = audience.toLowerCase();
    if (readingLevel === "basic" && /expert|advanced|professional/.test(audienceText)) {
      warnings.push(
        "Audience/reading-level mismatch: a basic reading level may not fit an expert or professional audience.",
      );
    }
    if (readingLevel === "advanced" && /beginner|novice/.test(audienceText)) {
      warnings.push(
        "Audience/reading-level mismatch: an advanced reading level may be too demanding for beginner or novice readers.",
      );
    }

    if (!bookPurpose.trim()) {
      warnings.push("Add a book purpose so the AI can focus every chapter.");
    }

    return warnings;
  }

  const warnings = runSmartChecks();

  // -------------------------------------------------------------------------
  // Payload building (matches backend keys exactly)
  // -------------------------------------------------------------------------

  function buildSetup(extraInstructions = ""): BookSetup {
    const instructionsText = [instructions.trim(), extraInstructions.trim()].filter(Boolean).join("\n\n");

    return {
      details: {
        title: title.trim(),
        subtitle: subtitle.trim() || null,
        topic: topic.trim(),
        target_audience: audience.trim(),
        tone,
        writing_style: style,
        language,
        author: author.trim() || null,
        book_purpose: bookPurpose.trim() || null,
      },
      size: {
        total_word_count: actualWords,
        custom: useCustomWords,
        chapters_override: overrideChapters > 0 ? overrideChapters : null,
      },
      layout: {
        page_size: pageSize,
        custom_page_size:
          pageSize === "custom" ? { width: Number(customPageWidth) || 6, height: Number(customPageHeight) || 9 } : null,
        margins: { top: marginTop, bottom: marginBottom, left: marginLeft, right: marginRight },
        header_font: headerFont,
        header_size: headerSize,
        body_font: bodyFont,
        body_size: bodySize,
        line_spacing: lineSpacing,
        paragraph_spacing: paragraphSpacing,
        image_width: imageWidth,
        image_ratio: imageRatio,
        default_image_style: imageStyle,
        chapter_heading_style: chapterHeadingStyle,
      },
      ai: {
        provider,
        model: model || MODEL_MAP[provider] || "openai/gpt-4o-mini",
        creativity,
        reading_level: readingLevel,
        writing_quality: writingQuality,
        use_citations: useCitations,
        generate_exercises: generateExercises,
        generate_summaries: generateSummaries,
      },
      special_instructions: {
        instructions: instructionsText,
      },
    };
  }

  // -------------------------------------------------------------------------
  // Submission
  // -------------------------------------------------------------------------

  async function handleGenerate(extraInstructions?: string) {
    if (step === "submitting") return;

    // Blocking validation on the essential fields
    if (!title.trim()) {
      toast({ title: "Missing book title", description: "Please enter a book title.", variant: "error" });
      scrollToSection(0);
      return;
    }
    if (!topic.trim() || topic.trim().length < 5) {
      toast({
        title: "Topic needs more detail",
        description: "Please describe your topic in more detail (at least a few words).",
        variant: "error",
      });
      scrollToSection(0);
      return;
    }
    if (!audience.trim()) {
      toast({ title: "Missing target audience", description: "Please describe your target audience.", variant: "error" });
      scrollToSection(0);
      return;
    }

    setServerError(null);
    setStep("submitting");

    // 1. Save the API key first if the user entered one
    if (apiKey.trim()) {
      try {
        await studioApi.saveKey(provider, apiKey.trim());
      } catch (err) {
        setStep("idle");
        toast(toastError(err));
        return;
      }
    }

    // 2. Kick off generation
    try {
      const res = await generationApi.setup(buildSetup(extraInstructions));

      if (res.clarification_questions && res.clarification_questions.length > 0) {
        setClarifyQuestions(res.clarification_questions);
        setClarifyAnswers({});
        setStep("idle");
        return;
      }

      if (res.job_id && res.project_id) {
        toast({ title: "Generation started", variant: "success" });
        router.push(`/workspace/${res.project_id}?generating=${res.job_id}`);
      } else {
        setServerError("No job was started. Please try again.");
        setStep("idle");
      }
    } catch (err) {
      setStep("idle");
      toast(toastError(err));
    }
  }

  // Merge clarification answers into special_instructions and re-submit
  async function handleClarifyContinue() {
    const answered = clarifyQuestions
      .map((q) => {
        const answer = (clarifyAnswers[q.id] ?? "").trim();
        return answer ? `${q.question}\n${answer}` : null;
      })
      .filter((x): x is string => Boolean(x));

    const extra = answered.length > 0 ? `Clarification answers:\n\n${answered.join("\n\n")}` : "";
    setClarifyQuestions([]);
    setClarifyAnswers({});
    await handleGenerate(extra);
  }

  function handleProviderChange(value: string) {
    setProvider(value);
    setModel(MODEL_MAP[value] || MODELS[value]?.[0] || MODEL_MAP.openrouter);
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Create a new book</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tell us about your book, and AI will write the first draft. Everything can be edited later.
        </p>
      </div>

      {/* Section nav — sticky numbered pills; horizontal scroll row on mobile */}
      <nav
        aria-label="Wizard sections"
        className="sticky top-0 z-30 -mx-1 rounded-lg border border-border bg-background/95 px-1 py-2.5 shadow-sm backdrop-blur"
      >
        <div className="flex items-center gap-2 overflow-x-auto pb-0.5 sm:justify-center sm:overflow-visible">
          {SECTIONS.map((s, i) => {
            const Icon = s.icon;
            const active = i === activeSection;
            return (
              <button
                key={s.label}
                type="button"
                onClick={() => scrollToSection(i)}
                aria-current={active ? "step" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <span
                  className={cn(
                    "flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold",
                    active ? "bg-primary-foreground/20 text-primary-foreground" : "bg-muted text-muted-foreground",
                  )}
                >
                  {i + 1}
                </span>
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{s.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void handleGenerate();
        }}
        className="space-y-8"
      >
        {/* ================================================================
            1. Book details
            ================================================================ */}
        <div
          ref={(el) => {
            sectionRefs.current[0] = el;
          }}
          className="scroll-mt-28"
        >
          <Card>
            <CardContent className="space-y-5 p-6">
              <div className="flex items-center gap-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                  1
                </span>
                <div>
                  <h2 className="text-base font-semibold">Book details</h2>
                  <p className="text-xs text-muted-foreground">What is your book about, and who is it for?</p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Book title" htmlFor="nb-title" required>
                  <Input id="nb-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="The Art of Calm Productivity" />
                </Field>
                <Field label="Subtitle (optional)" htmlFor="nb-subtitle">
                  <Input
                    id="nb-subtitle"
                    value={subtitle}
                    onChange={(e) => setSubtitle(e.target.value)}
                    placeholder="A simple framework for doing less and achieving more"
                  />
                </Field>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Author (optional)" htmlFor="nb-author">
                  <Input id="nb-author" value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="Your name or pen name" />
                </Field>
                <Field label="Language" htmlFor="nb-lang">
                  <Select id="nb-lang" value={language} onChange={(e) => setLanguage(e.target.value)}>
                    {LANGUAGES.map((l) => (
                      <option key={l.value} value={l.value}>
                        {l.label}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>

              <Field label="Topic" htmlFor="nb-topic" required hint="What is this book about? Be specific.">
                <Textarea
                  id="nb-topic"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  rows={3}
                  placeholder="e.g. Morning routines for sustainable productivity — habits, mindset shifts and practical schedules for busy professionals"
                />
              </Field>

              <Field label="Target audience" htmlFor="nb-audience" required hint="Who are you writing this for?">
                <Input id="nb-audience" value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="e.g. Busy professionals who feel overwhelmed" />
              </Field>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Writing tone" htmlFor="nb-tone">
                  <Select id="nb-tone" value={tone} onChange={(e) => setTone(e.target.value)}>
                    {TONES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Writing style" htmlFor="nb-style">
                  <Select id="nb-style" value={style} onChange={(e) => setStyle(e.target.value)}>
                    {STYLES.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>

              <Field
                label="Book purpose"
                htmlFor="nb-purpose"
                hint="Why are you writing this book, and what should it achieve for the reader? The AI uses this to focus every chapter."
              >
                <Textarea
                  id="nb-purpose"
                  value={bookPurpose}
                  onChange={(e) => setBookPurpose(e.target.value)}
                  rows={2}
                  placeholder="e.g. Help busy professionals build calm, sustainable morning routines that boost focus without burnout"
                />
              </Field>
            </CardContent>
          </Card>
        </div>

        {/* ================================================================
            2. Size
            ================================================================ */}
        <div
          ref={(el) => {
            sectionRefs.current[1] = el;
          }}
          className="scroll-mt-28"
        >
          <Card>
            <CardContent className="space-y-5 p-6">
              <div className="flex items-center gap-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                  2
                </span>
                <div>
                  <h2 className="text-base font-semibold">How long should your book be?</h2>
                  <p className="text-xs text-muted-foreground">Pick a target length or enter a custom word count.</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                {WORD_PRESETS.map((w) => (
                  <button
                    key={w}
                    type="button"
                    onClick={() => {
                      setWordCount(w);
                      setUseCustomWords(false);
                    }}
                    className={cn(
                      "rounded-full px-4 py-2 text-sm font-medium transition-colors",
                      !useCustomWords && wordCount === w
                        ? "bg-primary text-primary-foreground"
                        : "bg-secondary text-secondary-foreground hover:bg-secondary/80",
                    )}
                  >
                    {w.toLocaleString()} words
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setUseCustomWords(true)}
                  className={cn(
                    "rounded-full px-4 py-2 text-sm font-medium transition-colors",
                    useCustomWords ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground hover:bg-secondary/80",
                  )}
                >
                  Custom
                </button>
              </div>

              {useCustomWords && (
                <Field label="Custom word count" htmlFor="nb-words" hint="Between 1,000 and 200,000 words.">
                  <Input id="nb-words" type="number" min={1000} max={200000} value={customWords} onChange={(e) => setCustomWords(e.target.value)} placeholder="20000" />
                </Field>
              )}

              <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/40 px-4 py-3">
                <Badge variant="secondary">Estimated chapters: {effectiveChapters}</Badge>
                <span className="text-sm text-muted-foreground">
                  for a <strong className="font-semibold text-foreground">{actualWords.toLocaleString()} word</strong> book
                  (about {Math.round(actualWords / 250)} pages)
                </span>
              </div>

              <Field
                label="Chapter count (optional override)"
                htmlFor="nb-chapters"
                hint="Leave empty to auto-estimate from the word count."
              >
                <Input
                  id="nb-chapters"
                  type="number"
                  min={1}
                  max={200}
                  value={chaptersOverride}
                  onChange={(e) => setChaptersOverride(e.target.value)}
                  placeholder={`Auto: ${estimateChapters(actualWords)}`}
                />
              </Field>
            </CardContent>
          </Card>
        </div>

        {/* ================================================================
            3. Formatting
            ================================================================ */}
        <div
          ref={(el) => {
            sectionRefs.current[2] = el;
          }}
          className="scroll-mt-28"
        >
          <Card>
            <CardContent className="space-y-5 p-6">
              <div className="flex items-center gap-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                  3
                </span>
                <div>
                  <h2 className="text-base font-semibold">Formatting</h2>
                  <p className="text-xs text-muted-foreground">Page, typography and image settings. These can be changed at any time from the editor.</p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Page size" htmlFor="nb-page-size">
                  <Select id="nb-page-size" value={pageSize} onChange={(e) => setPageSize(e.target.value)}>
                    {PAGE_SIZES.map((p) => (
                      <option key={p} value={p}>
                        {PAGE_SIZE_LABELS[p]}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>

              {pageSize === "custom" && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Custom width (inches)" htmlFor="nb-cw">
                    <Input id="nb-cw" type="number" min={3} max={12} step={0.25} value={customPageWidth} onChange={(e) => setCustomPageWidth(e.target.value)} placeholder="6" />
                  </Field>
                  <Field label="Custom height (inches)" htmlFor="nb-ch">
                    <Input id="nb-ch" type="number" min={3} max={12} step={0.25} value={customPageHeight} onChange={(e) => setCustomPageHeight(e.target.value)} placeholder="9" />
                  </Field>
                </div>
              )}

              <h3 className="pt-1 text-sm font-medium">Margins (inches)</h3>
              <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
                <Field label="Top" htmlFor="nb-mt">
                  <Input id="nb-mt" type="number" min={0} max={3} step={0.1} value={String(marginTop)} onChange={(e) => setMarginTop(Number(e.target.value) || 1)} />
                </Field>
                <Field label="Bottom" htmlFor="nb-mb">
                  <Input id="nb-mb" type="number" min={0} max={3} step={0.1} value={String(marginBottom)} onChange={(e) => setMarginBottom(Number(e.target.value) || 1)} />
                </Field>
                <Field label="Left" htmlFor="nb-ml">
                  <Input id="nb-ml" type="number" min={0} max={3} step={0.1} value={String(marginLeft)} onChange={(e) => setMarginLeft(Number(e.target.value) || 1)} />
                </Field>
                <Field label="Right" htmlFor="nb-mr">
                  <Input id="nb-mr" type="number" min={0} max={3} step={0.1} value={String(marginRight)} onChange={(e) => setMarginRight(Number(e.target.value) || 1)} />
                </Field>
              </div>

              <h3 className="pt-1 text-sm font-medium">Typography</h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Header font" htmlFor="nb-header-font">
                  <Select id="nb-header-font" value={headerFont} onChange={(e) => setHeaderFont(e.target.value)}>
                    {FONTS.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Header size (pt)" htmlFor="nb-header-size">
                  <Input id="nb-header-size" type="number" min={8} max={32} value={String(headerSize)} onChange={(e) => setHeaderSize(Number(e.target.value) || 14)} />
                </Field>
                <Field label="Body font" htmlFor="nb-font">
                  <Select id="nb-font" value={bodyFont} onChange={(e) => setBodyFont(e.target.value)}>
                    {FONTS.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Body size (pt)" htmlFor="nb-size">
                  <Input id="nb-size" type="number" min={8} max={24} value={String(bodySize)} onChange={(e) => setBodySize(Number(e.target.value) || 12)} />
                </Field>
                <Field label="Line spacing" htmlFor="nb-line">
                  <Input id="nb-line" type="number" min={1} max={3} step={0.1} value={String(lineSpacing)} onChange={(e) => setLineSpacing(Number(e.target.value) || 1.5)} />
                </Field>
                <Field label="Paragraph spacing" htmlFor="nb-paragraph">
                  <Input id="nb-paragraph" type="number" min={0} max={3} step={0.1} value={String(paragraphSpacing)} onChange={(e) => setParagraphSpacing(Number(e.target.value) || 1)} />
                </Field>
              </div>

              <Field label="Chapter heading style" htmlFor="nb-heading-style">
                <Select id="nb-heading-style" value={chapterHeadingStyle} onChange={(e) => setChapterHeadingStyle(e.target.value)}>
                  {CHAPTER_HEADING_STYLES.map((h) => (
                    <option key={h.value} value={h.value}>
                      {h.label}
                    </option>
                  ))}
                </Select>
              </Field>

              <h3 className="pt-1 text-sm font-medium">Images</h3>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Image width (inches)" htmlFor="nb-img-width">
                  <Input id="nb-img-width" type="number" min={1} max={10} step={0.5} value={String(imageWidth)} onChange={(e) => setImageWidth(Number(e.target.value) || 6)} />
                </Field>
                <Field label="Image ratio" htmlFor="nb-img-ratio">
                  <Select id="nb-img-ratio" value={imageRatio} onChange={(e) => setImageRatio(e.target.value)}>
                    {IMAGE_RATIOS.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Default image style" htmlFor="nb-img-style">
                  <Select id="nb-img-style" value={imageStyle} onChange={(e) => setImageStyle(e.target.value)}>
                    {IMAGE_STYLES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ================================================================
            4. AI settings
            ================================================================ */}
        <div
          ref={(el) => {
            sectionRefs.current[3] = el;
          }}
          className="scroll-mt-28"
        >
          <Card>
            <CardContent className="space-y-5 p-6">
              <div className="flex items-center gap-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                  4
                </span>
                <div>
                  <h2 className="text-base font-semibold">AI settings</h2>
                  <p className="text-xs text-muted-foreground">Choose the model and how the AI should write.</p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Model provider" htmlFor="nb-provider">
                  <Select id="nb-provider" value={provider} onChange={(e) => handleProviderChange(e.target.value)}>
                    {PROVIDERS.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Model" htmlFor="nb-model">
                  <Select id="nb-model" value={model} onChange={(e) => setModel(e.target.value)}>
                    {(MODELS[provider] || [MODEL_MAP[provider]]).map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>

              <Field
                label="API key"
                htmlFor="nb-api-key"
                hint="Stored encrypted on the server. Leave empty to use the key saved in Settings."
              >
                <Input
                  id="nb-api-key"
                  type="password"
                  autoComplete="off"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-…"
                />
              </Field>

              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Creativity" htmlFor="nb-creativity">
                  <Select id="nb-creativity" value={creativity} onChange={(e) => setCreativity(e.target.value)}>
                    {CREATIVITIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Writing quality" htmlFor="nb-quality">
                  <Select id="nb-quality" value={writingQuality} onChange={(e) => setWritingQuality(e.target.value)}>
                    {WRITING_QUALITIES.map((q) => (
                      <option key={q.value} value={q.value}>
                        {q.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Reading level" htmlFor="nb-reading-level">
                  <Select id="nb-reading-level" value={readingLevel} onChange={(e) => setReadingLevel(e.target.value)}>
                    {READING_LEVELS.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>

              <div className="flex flex-wrap gap-x-6 gap-y-2 pt-1">
                <label htmlFor="nb-citations" className="flex cursor-pointer items-center gap-2 text-sm">
                  <Checkbox id="nb-citations" checked={useCitations} onChange={(e) => setUseCitations(e.target.checked)} />
                  Use citations
                </label>
                <label htmlFor="nb-exercises" className="flex cursor-pointer items-center gap-2 text-sm">
                  <Checkbox id="nb-exercises" checked={generateExercises} onChange={(e) => setGenerateExercises(e.target.checked)} />
                  Generate exercises
                </label>
                <label htmlFor="nb-summaries" className="flex cursor-pointer items-center gap-2 text-sm">
                  <Checkbox id="nb-summaries" checked={generateSummaries} onChange={(e) => setGenerateSummaries(e.target.checked)} />
                  Generate summaries
                </label>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ================================================================
            5. Special instructions
            ================================================================ */}
        <div
          ref={(el) => {
            sectionRefs.current[4] = el;
          }}
          className="scroll-mt-28"
        >
          <Card>
            <CardContent className="space-y-5 p-6">
              <div className="flex items-center gap-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                  5
                </span>
                <div>
                  <h2 className="text-base font-semibold">Special instructions</h2>
                  <p className="text-xs text-muted-foreground">
                    The AI follows these throughout the book — tone, structure, content rules, topics to cover or avoid.
                  </p>
                </div>
              </div>

              <Field label="Instructions" htmlFor="nb-instructions" hint="Optional but very helpful for the AI.">
                <Textarea
                  id="nb-instructions"
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  rows={6}
                  placeholder="e.g. Avoid jargon, use UK English, write for beginners, include real-world examples, use humour, mention Bible verses, include practical exercises at the end of each chapter…"
                />
              </Field>
            </CardContent>
          </Card>
        </div>

        {/* Smart checks — non-blocking warnings */}
        {warnings.length > 0 && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-50/60 p-4 dark:bg-amber-950/30">
            <div className="flex items-center gap-2">
              <IconAlert className="h-4 w-4 shrink-0 text-amber-600" />
              <p className="text-sm font-medium text-amber-800 dark:text-amber-300">A few things to review before generating</p>
            </div>
            <ul className="mt-2 space-y-1.5">
              {warnings.map((w) => (
                <li key={w} className="flex items-start gap-2 text-sm text-amber-800/90 dark:text-amber-200/90">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                  {w}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-amber-700/70 dark:text-amber-300/70">
              These won't block generation — you can proceed or adjust the settings above.
            </p>
          </div>
        )}

        {/* Clarification Q&A panel (inline) */}
        {clarifyQuestions.length > 0 && (
          <Card className="border-primary/40">
            <CardContent className="space-y-4 p-6">
              <div className="flex items-center gap-2">
                <IconSparkles className="h-5 w-5 text-primary" />
                <h3 className="text-base font-semibold">A few more questions</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                We need a bit more detail before the AI can write your book. Your answers are added to the special
                instructions and generation restarts.
              </p>
              {clarifyQuestions.map((q) => (
                <Field key={q.id} label={q.question} htmlFor={`clarify-${q.id}`}>
                  <Input
                    id={`clarify-${q.id}`}
                    value={clarifyAnswers[q.id] ?? ""}
                    onChange={(e) => setClarifyAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                    placeholder={q.placeholder}
                  />
                </Field>
              ))}
              <div className="flex items-center justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setClarifyQuestions([]);
                    setClarifyAnswers({});
                  }}
                >
                  Skip
                </Button>
                <Button type="button" onClick={() => void handleClarifyContinue()} disabled={step === "submitting"}>
                  {step === "submitting" ? <Spinner label="Submitting…" /> : "Continue"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {serverError && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
            <p className="whitespace-pre-wrap text-sm text-destructive">{serverError}</p>
          </div>
        )}

        {/* Prev / Next section navigation */}
        <div className="flex items-center justify-between gap-3">
          <Button type="button" variant="outline" onClick={() => scrollToSection(Math.max(0, activeSection - 1))} disabled={activeSection === 0}>
            <IconChevronLeft className="h-4 w-4" />
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => scrollToSection(Math.min(SECTIONS.length - 1, activeSection + 1))}
            disabled={activeSection === SECTIONS.length - 1}
          >
            Next
            <IconChevronRight className="h-4 w-4" />
          </Button>
        </div>

        {/* Generate */}
        <div className="flex flex-col items-center gap-4 pt-2">
          <Button type="submit" size="lg" className="w-full" disabled={step === "submitting"}>
            {step === "submitting" ? (
              <span className="flex items-center gap-2">
                <Spinner label="" />
                Creating your book…
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <IconSparkles className="h-4 w-4" />
                Generate Book
              </span>
            )}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            This will create your book and start AI generation in the background. You&apos;ll be taken to a progress
            dashboard where you can watch your book come together.
          </p>
        </div>
      </form>
    </div>
  );
}
