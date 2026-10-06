import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { TranslationPanel } from "@/components/studio/panels/translation-panel";
import { bookWritingApi, type TranslationEdition, type TranslationSummary } from "@/lib/api/bookWriting";
import { jobsApi, type JobResponse } from "@/lib/api/jobs";
import type { WritingBook } from "@/types/api";
import { renderWithProviders } from "./test-utils";

const apiMocks = vi.hoisted(() => ({
  getBook: vi.fn(),
  listTranslations: vi.fn(),
  getTranslation: vi.fn(),
  getJob: vi.fn(),
  startTranslation: vi.fn(),
}));

vi.mock("@/lib/api/bookWriting", () => ({
  bookWritingApi: {
    getBook: apiMocks.getBook,
    listTranslations: apiMocks.listTranslations,
    getTranslation: apiMocks.getTranslation,
  },
}));

vi.mock("@/lib/api/jobs", () => ({
  jobsApi: {
    get: apiMocks.getJob,
    startTranslation: apiMocks.startTranslation,
  },
}));

const timestamp = "2026-10-05T12:00:00Z";

const book: WritingBook = {
  id: "book-1",
  user_id: "user-1",
  title: "A French Book",
  subtitle: null,
  description: null,
  author_name: null,
  target_audience: null,
  book_type: null,
  language: "fr-FR",
  tone: null,
  approximate_length: null,
  status: "writing",
  current_step: "writing",
  created_at: timestamp,
  updated_at: timestamp,
};

const edition: TranslationEdition = {
  id: "translation-1",
  book_id: "book-1",
  source_language: "fr",
  target_language: "es",
  status: "COMPLETED",
  source_chapter_count: 1,
  translated_chapter_count: 1,
  target_word_count: 3,
  error_message: null,
  completed_at: timestamp,
  created_at: timestamp,
  updated_at: timestamp,
  chapters: [
    {
      id: "translated-chapter-1",
      translation_id: "translation-1",
      source_chapter_id: "chapter-1",
      chapter_number: 1,
      title: "Introducción",
      content: "Contenido traducido.",
      word_count: 3,
      status: "COMPLETED",
      error_message: null,
      created_at: timestamp,
      updated_at: timestamp,
    },
  ],
};

const failedEdition: TranslationSummary = {
  ...edition,
  status: "FAILED",
  translated_chapter_count: 0,
  target_word_count: 0,
  completed_at: null,
};

function makeJob(
  status: JobResponse["status"],
  result: JobResponse["result"] = null,
): JobResponse {
  return {
    id: "job-1",
    job_type: "TRANSLATION",
    status,
    progress: status === "COMPLETED" ? 100 : 10,
    current_step: status === "COMPLETED" ? null : "Translating chapter 1",
    result,
    error_message: null,
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function renderPanel(onApplyEdit = vi.fn()) {
  return renderWithProviders(
    <TranslationPanel
      projectId="project-1"
      writingBookId="book-1"
      activeChapterId="chapter-1"
      onApplyEdit={onApplyEdit}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(bookWritingApi.getBook).mockResolvedValue(book);
  vi.mocked(bookWritingApi.listTranslations).mockResolvedValue({ items: [] });
  vi.mocked(bookWritingApi.getTranslation).mockResolvedValue(edition);
  vi.mocked(jobsApi.startTranslation).mockResolvedValue(makeJob("QUEUED"));
  vi.mocked(jobsApi.get).mockResolvedValue(makeJob("RUNNING"));
});

describe("TranslationPanel", () => {
  it("uses the book language, creates an independent edition, and opens it on completion", async () => {
    const onApplyEdit = vi.fn();
    vi.mocked(jobsApi.get).mockResolvedValue(
      makeJob("COMPLETED", { translation_id: edition.id }),
    );

    renderPanel(onApplyEdit);

    const sourceLanguage = screen.getByLabelText("From");
    await waitFor(() => expect(sourceLanguage).toHaveValue("fr"));
    expect(screen.getByText(/source chapters are never replaced/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /create translated edition/i }));

    await waitFor(() => {
      expect(jobsApi.startTranslation).toHaveBeenCalledWith("book-1", "fr", "es", undefined);
    });
    expect(await screen.findByRole("heading", { name: "Spanish edition" })).toBeInTheDocument();
    expect(bookWritingApi.getTranslation).toHaveBeenCalledWith("book-1", edition.id);

    fireEvent.click(screen.getByText(/Introducción/));
    expect(await screen.findByText("Contenido traducido.")).toBeInTheDocument();
    expect(onApplyEdit).not.toHaveBeenCalled();
  });

  it("disables translation when source and target languages match", async () => {
    renderPanel();

    const sourceLanguage = screen.getByLabelText("From");
    await waitFor(() => expect(sourceLanguage).toHaveValue("fr"));
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "fr" } });

    expect(screen.getByRole("button", { name: /create translated edition/i })).toBeDisabled();
    expect(screen.getByText(/choose two different languages/i)).toBeInTheDocument();
    expect(jobsApi.startTranslation).not.toHaveBeenCalled();
  });

  it("resumes a failed edition without creating a replacement", async () => {
    vi.mocked(bookWritingApi.listTranslations).mockResolvedValue({ items: [failedEdition] });

    renderPanel();
    const resumeButton = await screen.findByRole("button", { name: "Resume" });
    fireEvent.click(resumeButton);

    await waitFor(() => {
      expect(jobsApi.startTranslation).toHaveBeenCalledWith(
        "book-1",
        "fr",
        "es",
        "translation-1",
      );
    });
  });
});
