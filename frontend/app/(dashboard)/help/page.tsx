"use client";

// Help page — comprehensive guides for every module.

import { Card, CardContent } from "@/components/ui/card";
import { IconBook, IconSparkles, IconHelp, IconPen, IconImage, IconLayout, IconCover, IconProof, IconTranslate, IconMarketing, IconExport } from "@/components/ui/icons";

const GUIDES = [
  {
    icon: <IconBook className="h-5 w-5" />,
    title: "Creating your first book",
    steps: [
      "Click \"New Book\" on the dashboard or projects page.",
      "Enter a project name, book title, author name, and description.",
      "Optionally add a subtitle, target audience, and writing style.",
      "Click \"Create project\" — your project and linked writing book are created instantly.",
      "Navigate to the Write module to start generating your book's content.",
    ],
  },
  {
    icon: <IconPen className="h-5 w-5" />,
    title: "Writing with AI",
    steps: [
      "Open your project and go to the Write module (redirects to the book editor).",
      "Generate a Book Brief — AI analyzes your idea and creates a structured plan.",
      "Generate a Blueprint — AI creates a chapter-by-chapter outline.",
      "For each chapter: generate an outline, then generate the full content.",
      "Use Continue, Rewrite, Expand, or Shorten to refine each chapter.",
      "Content autosaves every 1.5 seconds. Version history tracks every change.",
    ],
  },
  {
    icon: <IconProof className="h-5 w-5" />,
    title: "AI Proofreading",
    steps: [
      "Open the Review tab in the book editor.",
      "Choose a review mode: proofreading, clarity, style, consistency, or full review.",
      "Click \"Review chapter\" — AI analyzes the text and returns suggestions.",
      "Accept, reject, or ignore each suggestion individually or in bulk.",
      "Accepted changes automatically create a new chapter version.",
    ],
  },
  {
    icon: <IconImage className="h-5 w-5" />,
    title: "Image Generation",
    steps: [
      "Go to the Images module in your project.",
      "Enter a prompt describing the image you want (subject, style, mood).",
      "Choose how many variations to generate (1-8).",
      "Click Generate — images are created via the Pollinations AI provider.",
      "View, delete, or regenerate images in the gallery.",
    ],
  },
  {
    icon: <IconLayout className="h-5 w-5" />,
    title: "KDP Formatting",
    steps: [
      "Go to the Formatting module in your project.",
      "Choose a trim size (6x9, 8x10, A4, Letter, or custom).",
      "Set margins, body font, heading font, and font sizes.",
      "Configure line spacing, paragraph spacing, and image defaults.",
      "Toggle chapter page breaks and table of contents.",
      "These settings are applied automatically when you export.",
    ],
  },
  {
    icon: <IconLayout className="h-5 w-5" />,
    title: "KDP Validation",
    steps: [
      "Go to the Validator module in your project.",
      "Click \"Run KDP Check\" — the system inspects your book.",
      "Review the report: issues (red), warnings (amber), and passed checks (green).",
      "Each item includes a specific fix recommendation.",
      "Fix the issues in your formatting settings or chapters, then re-run.",
    ],
  },
  {
    icon: <IconCover className="h-5 w-5" />,
    title: "Cover Design",
    steps: [
      "Go to the Cover module in your project.",
      "Generate the front cover, back cover, or spine individually — or all at once.",
      "AI creates a detailed design brief: concept, color palette, typography, layout.",
      "Use the brief with a designer or AI image generator to produce the cover.",
      "Regenerate any component to get a new variation.",
    ],
  },
  {
    icon: <IconTranslate className="h-5 w-5" />,
    title: "Translation",
    steps: [
      "Go to the Translation module in your project.",
      "Select source and target languages (20+ supported).",
      "Click Translate — each chapter is translated sequentially.",
      "Markdown formatting (headings, bold, lists) and image placeholders are preserved.",
      "The translated text replaces your current chapter content.",
      "View translation history to track past translations.",
    ],
  },
  {
    icon: <IconMarketing className="h-5 w-5" />,
    title: "Marketing",
    steps: [
      "Go to the Marketing module in your project.",
      "Choose from 10 asset types: Amazon description, subtitle ideas, keywords, categories, Pinterest, Instagram, Facebook, X/Twitter, LinkedIn, and email launch campaign.",
      "Click Generate — AI creates optimized marketing copy.",
      "Regenerate to get a new variation, or delete to remove.",
      "Copy the content directly to your marketing channels.",
    ],
  },
  {
    icon: <IconExport className="h-5 w-5" />,
    title: "Exporting your book",
    steps: [
      "Go to the Export module in your project.",
      "Choose options: include front matter, table of contents, back matter.",
      "Click Generate for DOCX (Word), PDF, or EPUB.",
      "The export uses your latest chapters and formatting settings.",
      "Download the file or delete previous exports.",
      "Each new export of the same format replaces the old version.",
    ],
  },
];

const FAQ = [
  {
    q: "How do I configure AI providers?",
    a: "Go to Settings → AI Settings. Choose your preferred provider and model. API keys are configured server-side — contact your administrator to add or change API keys.",
  },
  {
    q: "Does my work autosave?",
    a: "Yes. The chapter editor autosaves every 1.5 seconds. Every save creates a version snapshot you can restore from the Versions tab.",
  },
  {
    q: "Can I reorder chapters?",
    a: "Yes. In the book editor, drag chapters to reorder them, or use the chapter list sidebar.",
  },
  {
    q: "What formats can I export?",
    a: "DOCX (Microsoft Word), PDF, and EPUB. Each format applies your formatting settings (trim size, margins, fonts, spacing).",
  },
  {
    q: "How does translation work?",
    a: "Translation processes each chapter sequentially via AI. Markdown formatting and image placeholders are preserved. The translated text replaces your current content — create a backup by exporting before translating.",
  },
  {
    q: "Is there a word count limit?",
    a: "No hard limit, but very long books (>200k words) may slow down during export and translation. Consider splitting very long books into volumes.",
  },
];

export default function HelpPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Help &amp; resources</h1>
        <p className="text-sm text-muted-foreground">
          Complete guides for every module in AI Ebook Studio.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="space-y-2 p-5">
            <IconBook className="h-6 w-6 text-foreground" />
            <h2 className="font-semibold">Guides</h2>
            <p className="text-sm text-muted-foreground">
              Step-by-step walkthroughs for every module below.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-2 p-5">
            <IconSparkles className="h-6 w-6 text-foreground" />
            <h2 className="font-semibold">Best practices</h2>
            <p className="text-sm text-muted-foreground">
              Generate a brief and blueprint before writing chapters for best results.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-2 p-5">
            <IconHelp className="h-6 w-6 text-foreground" />
            <h2 className="font-semibold">Support</h2>
            <p className="text-sm text-muted-foreground">
              Check the FAQ below or contact support if you need help.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">Module guides</h2>
        {GUIDES.map((guide) => (
          <Card key={guide.title}>
            <CardContent className="p-5">
              <div className="mb-3 flex items-center gap-2">
                {guide.icon}
                <h3 className="font-semibold">{guide.title}</h3>
              </div>
              <ol className="ml-5 list-decimal space-y-1 text-sm text-muted-foreground">
                {guide.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">FAQ</h2>
        {FAQ.map((item) => (
          <Card key={item.q}>
            <CardContent className="p-5">
              <h3 className="font-semibold">{item.q}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{item.a}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
