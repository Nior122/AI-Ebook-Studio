// Book settings form test: loads the default settings, edits a value, and
// saves via the update mutation.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor, act } from "@testing-library/react";
import FormattingPage from "@/app/(dashboard)/projects/[projectId]/formatting/page";
import * as booksHooks from "@/hooks/use-books";
import { renderWithProviders } from "./test-utils";

const defaultSettings = {
  id: "s1",
  book_id: "b1",
  kdp_trim_size: "6x9",
  custom_format_enabled: false,
  page_width: 6,
  page_height: 9,
  margin_top: 0.75,
  margin_bottom: 0.75,
  margin_left: 0.75,
  margin_right: 0.75,
  body_font: "Georgia",
  body_font_size: 11,
  heading_font: "Georgia",
  line_spacing: 1.15,
  paragraph_spacing: 6,
  image_width: 5,
  image_alignment: "center",
  image_aspect_ratio: "16:9",
  image_style: "realistic",
  caption_enabled: true,
  caption_font_size: 9,
  chapter_page_breaks: true,
  toc_enabled: true,
};

describe("FormattingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(booksHooks, "useProjectBook").mockReturnValue({
      data: { id: "b1", title: "Book" },
      isLoading: false,
    } as never);
    vi.spyOn(booksHooks, "useBookSettings").mockReturnValue({
      data: defaultSettings,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as never);
    const mutate = vi.fn().mockResolvedValue(defaultSettings);
    vi.spyOn(booksHooks, "useUpdateBookSettings").mockReturnValue({
      mutateAsync: mutate,
      isPending: false,
    } as never);
  });

  it("loads and displays the default trim size", async () => {
    await act(async () => {
      renderWithProviders(<FormattingPage params={Promise.resolve({ projectId: "p1" })} />);
    });
    const select = (await screen.findByLabelText(/kdp trim size/i)) as HTMLSelectElement;
    expect(select.value).toBe("6x9");
  });

  it("saves edited settings", async () => {
    const mutate = vi.fn().mockResolvedValue(defaultSettings);
    vi.spyOn(booksHooks, "useUpdateBookSettings").mockReturnValue({
      mutateAsync: mutate,
      isPending: false,
    } as never);

    await act(async () => {
      renderWithProviders(<FormattingPage params={Promise.resolve({ projectId: "p1" })} />);
    });
    const select = (await screen.findByLabelText(/kdp trim size/i)) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "8x10" } });
    fireEvent.click(screen.getByRole("button", { name: /save settings/i }));

    await waitFor(() =>
      expect(mutate).toHaveBeenCalledWith(
        expect.objectContaining({ bookId: "b1", payload: expect.objectContaining({ kdp_trim_size: "8x10" }) }),
      ),
    );
  });
});
