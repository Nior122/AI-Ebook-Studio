"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { Dialog, DialogHeader, DialogFooter } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { generationApi, WORD_COUNT_PRESETS, type BookSetup } from "@/lib/api/generation";
import { ApiError } from "@/lib/api";

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

const PAGE_SIZES = ["6x9", "8x10", "A4"];

const FONTS = ["Georgia", "Merriweather", "Palatino", "Garamond", "Times New Roman", "Arial", "Helvetica"];

const IMAGE_STYLES = ["realistic", "illustration", "watercolor", "sketch", "comic"];

function estimateChapters(words: number): number {
  if (words <= 5000) return 5;
  if (words <= 10000) return 8;
  if (words <= 15000) return 10;
  if (words <= 25000) return 14;
  if (words <= 50000) return 20;
  return 25;
}

type Step = "idle" | "submitting" | "generating";

const MODEL_MAP: Record<string, string> = {
  openrouter: "openai/gpt-4o-mini",
  openai: "gpt-4o-mini",
  gemini: "gemini-2.0-flash",
  groq: "llama-3.3-70b",
};

export default function NewBookPage() {
  const router = useRouter();
  const toast = useToast();

  const [step, setStep] = useState<Step>("idle");
  const [serverError, setServerError] = useState<string | null>(null);
  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [clarifyQuestions, setClarifyQuestions] = useState<Array<{ id: string; question: string; placeholder: string }>>([]);
  const [clarifyAnswers, setClarifyAnswers] = useState<Record<string, string>>({});
  const [jobId, setJobId] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [tone, setTone] = useState("conversational");
  const [style, setStyle] = useState("practical_guide");
  const [language, setLanguage] = useState("en");

  const [wordCount, setWordCount] = useState(10000);
  const [customWords, setCustomWords] = useState("");
  const [useCustomWords, setUseCustomWords] = useState(false);

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
  const [imageWidth, setImageWidth] = useState(6.0);
  const [imageRatio, setImageRatio] = useState("16:9");
  const [imageStyle, setImageStyle] = useState("realistic");

  const [creativity, setCreativity] = useState("balanced");
  const [provider, setProvider] = useState("openrouter");

  const [instructions, setInstructions] = useState("");

  const actualWords = useCustomWords && customWords ? Number(customWords) || 10000 : wordCount;
  const chapCount = estimateChapters(actualWords);

  async function handleClarifySubmit() {
    // Re-submit the original setup with clarification answers appended
    const setup: BookSetup = {
      details: { title: title.trim(), subtitle: subtitle.trim() || null, topic: topic.trim(), target_audience: audience.trim(), tone, writing_style: style, language },
      size: { total_word_count: actualWords, custom: useCustomWords },
      layout: {
        page_size: pageSize,
        custom_page_size: pageSize === "custom" ? { width: Number(customPageWidth) || 6, height: Number(customPageHeight) || 9 } : null,
        margins: { top: marginTop, bottom: marginBottom, left: marginLeft, right: marginRight },
        header_font: headerFont, header_size: headerSize, body_font: bodyFont, body_size: bodySize,
        line_spacing: lineSpacing, paragraph_spacing: paragraphSpacing,
        image_width: imageWidth, image_ratio: imageRatio, default_image_style: imageStyle,
      },
      ai: { creativity, speed: "balanced", provider, model: MODEL_MAP[provider] || "openai/gpt-4o-mini" },
      special_instructions: { instructions: instructions.trim() },
    };
    setStep("submitting");
    try {
      const res = await generationApi.setup(setup);
      if (res.job_id) {
        setJobId(res.job_id);
        toast({ title: "Generation started", variant: "success" });
        router.push(`/generating/${res.job_id}?redirect=/workspace/${res.project_id}`);
      } else {
        setServerError("Unable to start generation. Please try again.");
        setStep("idle");
      }
    } catch (err) {
      setStep("idle");
      setServerError(err instanceof ApiError ? err.message || "Please try again." : "An unexpected error occurred.");
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setServerError(null);

    if (!title.trim()) {
      setServerError("Please enter a book title.");
      return;
    }
    if (!topic.trim() || topic.trim().length < 5) {
      setServerError("Please describe your topic in more detail (at least a few words).");
      return;
    }
    if (!audience.trim()) {
      setServerError("Please describe your target audience.");
      return;
    }

    const setup: BookSetup = {
      details: {
        title: title.trim(),
        subtitle: subtitle.trim() || null,
        topic: topic.trim(),
        target_audience: audience.trim(),
        tone,
        writing_style: style,
        language,
      },
      size: {
        total_word_count: actualWords,
        custom: useCustomWords,
      },
      layout: {
        page_size: pageSize,
        custom_page_size: pageSize === "custom" ? { width: Number(customPageWidth) || 6, height: Number(customPageHeight) || 9 } : null,
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
      },
            ai: {
        creativity,
        speed: "balanced",
        provider,
        model: MODEL_MAP[provider] || "openai/gpt-4o-mini",
      },
      special_instructions: {
        instructions: instructions.trim(),
      },
    };

    setStep("submitting");
    try {
      const res = await generationApi.setup(setup);

      if (res.clarification_questions && res.clarification_questions.length > 0) {
        setClarifyQuestions(res.clarification_questions);
        setClarifyAnswers({});
        setClarifyOpen(true);
        setStep("idle");
        return;
      }

      if (res.job_id) {
        setJobId(res.job_id);
        toast({ title: "Generation started", variant: "success" });
        router.push(`/generating/${res.job_id}?redirect=/workspace/${res.project_id}`);
      } else {
        setServerError("No job was started. Please try again.");
        setStep("idle");
      }
    } catch (err) {
      setStep("idle");
      let msg = "Something went wrong. Please try again.";
      if (err instanceof ApiError) {
        if (err.status === 0) msg = "Cannot reach the server. Check your connection and try again.";
        else if (err.status === 401) msg = "Your session has expired. Please refresh and sign in again.";
        else if (err.status === 429) msg = "Too many requests. Please wait a moment and try again.";
        else msg = err.message || msg;
      }
      setServerError(msg);
      toast({ title: "Generation failed", description: msg, variant: "error" });
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Create a new book</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tell us about your book, and AI will write the first draft. Everything can be edited later.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* 1. Book Details */}
        <Card>
          <CardContent className="space-y-4 p-6">
            <h2 className="text-lg font-semibold">What is your book about?</h2>
            <Field label="Book title" htmlFor="nb-title" required>
              <Input id="nb-title" value={title} onChange={e => setTitle(e.target.value)} placeholder="The Art of Calm Productivity" />
            </Field>
            <Field label="Subtitle (optional)" htmlFor="nb-subtitle">
              <Input id="nb-subtitle" value={subtitle} onChange={e => setSubtitle(e.target.value)} placeholder="A simple framework for doing less and achieving more" />
            </Field>
            <Field label="Topic" htmlFor="nb-topic" required hint="What is this book about? Be specific.">
              <Input id="nb-topic" value={topic} onChange={e => setTopic(e.target.value)} placeholder="e.g. Morning routines for sustainable productivity" />
            </Field>
            <Field label="Target audience" htmlFor="nb-audience" required hint="Who are you writing this for?">
              <Input id="nb-audience" value={audience} onChange={e => setAudience(e.target.value)} placeholder="e.g. Busy professionals who feel overwhelmed" />
            </Field>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Writing tone" htmlFor="nb-tone">
                <Select id="nb-tone" value={tone} onChange={e => setTone(e.target.value)}>
                  {TONES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </Select>
              </Field>
              <Field label="Writing style" htmlFor="nb-style">
                <Select id="nb-style" value={style} onChange={e => setStyle(e.target.value)}>
                  {STYLES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </Select>
              </Field>
              <Field label="Language" htmlFor="nb-lang">
                <Select id="nb-lang" value={language} onChange={e => setLanguage(e.target.value)}>
                  {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
                </Select>
              </Field>
            </div>
          </CardContent>
        </Card>

        {/* 2. Book Size */}
        <Card>
          <CardContent className="space-y-5 p-6">
            <h2 className="text-lg font-semibold">How long should your book be?</h2>
            <p className="text-sm text-muted-foreground">
              The AI will create approximately <strong>{chapCount} chapters</strong> for a <strong>{actualWords.toLocaleString()} word</strong> book
              (about {Math.round(actualWords / 250)} pages).
            </p>
            <div className="flex flex-wrap gap-2">
              {WORD_COUNT_PRESETS.map(w => (
                <button
                  key={w}
                  type="button"
                  onClick={() => { setWordCount(w); setUseCustomWords(false); }}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                    !useCustomWords && wordCount === w
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
                  }`}
                >
                  {w.toLocaleString()} words
                </button>
              ))}
              <button
                type="button"
                onClick={() => setUseCustomWords(true)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                  useCustomWords ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
                }`}
              >
                Custom
              </button>
            </div>
            {useCustomWords && (
              <Field label="Custom word count" htmlFor="nb-words">
                <Input id="nb-words" type="number" min={1000} max={200000} value={customWords} onChange={e => setCustomWords(e.target.value)} placeholder="20000" />
              </Field>
            )}
          </CardContent>
        </Card>

        {/* 3. Layout */}
        <Card>
          <CardContent className="space-y-5 p-6">
            <h2 className="text-lg font-semibold">Layout settings</h2>
            <p className="text-sm text-muted-foreground">These can be changed at any time from the editor.</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Page size" htmlFor="nb-page">
                <Select id="nb-page" value={pageSize} onChange={e => setPageSize(e.target.value)}>
                  {PAGE_SIZES.map(s => <option key={s} value={s}>{s}</option>)}
                  <option value="custom">Custom</option>
                </Select>
              </Field>
              {pageSize === "custom" && (
                <>
                  <Field label="Custom width (inches)" htmlFor="nb-w">
                    <Input id="nb-w" type="number" min={3} max={12} step={0.25} value={customPageWidth} onChange={e => setCustomPageWidth(e.target.value)} placeholder="6" />
                  </Field>
                  <Field label="Custom height (inches)" htmlFor="nb-h">
                    <Input id="nb-h" type="number" min={3} max={12} step={0.25} value={customPageHeight} onChange={e => setCustomPageHeight(e.target.value)} placeholder="9" />
                  </Field>
                </>
              )}
            </div>

            <h3 className="text-sm font-medium pt-2">Margins (inches)</h3>
            <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
              <Field label="Top" htmlFor="nb-mt">
                <Input id="nb-mt" type="number" min={0} max={3} step={0.1} value={String(marginTop)} onChange={e => setMarginTop(Number(e.target.value) || 1)} />
              </Field>
              <Field label="Bottom" htmlFor="nb-mb">
                <Input id="nb-mb" type="number" min={0} max={3} step={0.1} value={String(marginBottom)} onChange={e => setMarginBottom(Number(e.target.value) || 1)} />
              </Field>
              <Field label="Left" htmlFor="nb-ml">
                <Input id="nb-ml" type="number" min={0} max={3} step={0.1} value={String(marginLeft)} onChange={e => setMarginLeft(Number(e.target.value) || 1)} />
              </Field>
              <Field label="Right" htmlFor="nb-mr">
                <Input id="nb-mr" type="number" min={0} max={3} step={0.1} value={String(marginRight)} onChange={e => setMarginRight(Number(e.target.value) || 1)} />
              </Field>
            </div>

            <h3 className="text-sm font-medium pt-2">Typography</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Header font" htmlFor="nb-header-font">
                <Select id="nb-header-font" value={headerFont} onChange={e => setHeaderFont(e.target.value)}>
                  {FONTS.map(f => <option key={f} value={f}>{f}</option>)}
                </Select>
              </Field>
              <Field label="Header size (pt)" htmlFor="nb-header-size">
                <Input id="nb-header-size" type="number" min={8} max={32} value={String(headerSize)} onChange={e => setHeaderSize(Number(e.target.value) || 14)} />
              </Field>
              <Field label="Body font" htmlFor="nb-font">
                <Select id="nb-font" value={bodyFont} onChange={e => setBodyFont(e.target.value)}>
                  {FONTS.map(f => <option key={f} value={f}>{f}</option>)}
                </Select>
              </Field>
              <Field label="Body size (pt)" htmlFor="nb-size">
                <Input id="nb-size" type="number" min={8} max={24} value={String(bodySize)} onChange={e => setBodySize(Number(e.target.value) || 12)} />
              </Field>
              <Field label="Line spacing" htmlFor="nb-line">
                <Input id="nb-line" type="number" min={1} max={3} step={0.1} value={String(lineSpacing)} onChange={e => setLineSpacing(Number(e.target.value) || 1.5)} />
              </Field>
              <Field label="Paragraph spacing" htmlFor="nb-para">
                <Input id="nb-para" type="number" min={0} max={4} step={0.1} value={String(paragraphSpacing)} onChange={e => setParagraphSpacing(Number(e.target.value) || 1)} />
              </Field>
            </div>

            <h3 className="text-sm font-medium pt-2">Images</h3>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Image width (inches)" htmlFor="nb-img-width">
                <Input id="nb-img-width" type="number" min={1} max={8} step={0.25} value={String(imageWidth)} onChange={e => setImageWidth(Number(e.target.value) || 6)} />
              </Field>
              <Field label="Image ratio" htmlFor="nb-img-ratio">
                <Select id="nb-img-ratio" value={imageRatio} onChange={e => setImageRatio(e.target.value)}>
                  <option value="16:9">16:9 (Landscape)</option>
                  <option value="square">1:1 (Square)</option>
                  <option value="portrait">3:4 (Portrait)</option>
                  <option value="4:3">4:3</option>
                </Select>
              </Field>
              <Field label="Default image style" htmlFor="nb-img-style">
                <Select id="nb-img-style" value={imageStyle} onChange={e => setImageStyle(e.target.value)}>
                  {IMAGE_STYLES.map(s => <option key={s} value={s}>{s}</option>)}
                </Select>
              </Field>
            </div>
          </CardContent>
        </Card>

        {/* 4. AI Settings */}
        <Card>
          <CardContent className="space-y-5 p-6">
            <h2 className="text-lg font-semibold">AI settings</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Creativity" htmlFor="nb-creativity">
                <Select id="nb-creativity" value={creativity} onChange={e => setCreativity(e.target.value)}>
                  {CREATIVITIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </Select>
              </Field>
              <Field label="Model provider" htmlFor="nb-provider">
                <Select id="nb-provider" value={provider} onChange={e => setProvider(e.target.value)}>
                  {PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                </Select>
              </Field>
            </div>
          </CardContent>
        </Card>

        {/* 5. Special Instructions */}
        <Card>
          <CardContent className="space-y-5 p-6">
            <h2 className="text-lg font-semibold">Special instructions</h2>
            <p className="text-sm text-muted-foreground">
              Tell the AI anything specific about how you want this book written.
            </p>
            <Field label="Instructions" htmlFor="nb-instructions" hint="Optional but helpful for the AI">
              <Textarea
                id="nb-instructions"
                value={instructions}
                onChange={e => setInstructions(e.target.value)}
                rows={4}
                placeholder="e.g. Avoid jargon, use UK English, write for beginners, include real-world examples, use humour, mention Bible verses, include practical exercises at the end of each chapter…"
              />
            </Field>
          </CardContent>
        </Card>

        {serverError && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
            <p className="text-sm text-destructive whitespace-pre-wrap">{serverError}</p>
          </div>
        )}

        <div className="flex items-center gap-4 pt-4">
          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={step === "submitting"}
          >
            {step === "submitting" ? (
              <span className="flex items-center gap-2">
                <Spinner label="" />
                Creating your book…
              </span>
            ) : (
              "Generate Book"
            )}
          </Button>
        </div>
        <p className="text-center text-xs text-muted-foreground">
          This will create your book and start AI generation in the background.
          You&apos;ll be taken to a progress dashboard where you can watch your book come together.
        </p>
      </form>

      {/* Clarification dialog */}
      <Dialog open={clarifyOpen} onClose={() => setClarifyOpen(false)} labelledBy="clarify-title">
        <DialogHeader title="A few more questions" description="We need a bit more detail before the AI can write your book." />
        <form onSubmit={(e) => { e.preventDefault(); setClarifyOpen(false); handleClarifySubmit(); }} className="space-y-4">
          {clarifyQuestions.map(q => (
            <Field key={q.id} label={q.question} htmlFor={`clarify-${q.id}`}>
              <Input id={`clarify-${q.id}`} value={clarifyAnswers[q.id] ?? ""} onChange={e => setClarifyAnswers(prev => ({ ...prev, [q.id]: e.target.value }))} placeholder={q.placeholder} />
            </Field>
          ))}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setClarifyOpen(false)}>Skip</Button>
            <Button type="submit">Continue</Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}