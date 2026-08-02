"use client";

// Rich text editor for chapter content. Backed by markdown (the storage
// format): renders contentEditable HTML, converts back on input, and supports
// a formatting toolbar plus markdown image insertion from the right panel.

import { useCallback, useEffect, useRef } from "react";
import { htmlToMd, mdToHtml } from "@/lib/markdown";

interface RichEditorProps {
  value: string;
  onChange: (markdown: string) => void;
  disabled?: boolean;
  placeholder?: string;
  /** Insert raw markdown (e.g. an image) at the current cursor position. */
  insertMarkdownRef?: React.MutableRefObject<((markdown: string) => void) | null>;
}

type Command = "bold" | "italic" | "formatBlock:h3" | "insertUnorderedList" | "formatBlock:blockquote" | "undo" | "redo";

const TOOLBAR: Array<{ command: Command; label: string; title: string }> = [
  { command: "bold", label: "B", title: "Bold (Ctrl+B)" },
  { command: "italic", label: "I", title: "Italic (Ctrl+I)" },
  { command: "formatBlock:h3", label: "H3", title: "Heading" },
  { command: "insertUnorderedList", label: "• List", title: "Bullet list" },
  { command: "formatBlock:blockquote", label: "❝", title: "Quote" },
];

export function RichEditor({ value, onChange, disabled, placeholder, insertMarkdownRef }: RichEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null);
  const lastEmittedRef = useRef<string>(value);
  const valueRef = useRef<string>(value);
  valueRef.current = value;

  // Sync external value -> DOM only when the user is not actively typing
  // (avoids clobbering the caret mid-edit).
  useEffect(() => {
    const editor = editorRef.current;
    if (!editor) return;
    if (document.activeElement === editor) return;
    const next = mdToHtml(value);
    if (editor.innerHTML !== next) editor.innerHTML = next;
  }, [value]);

  const emit = useCallback(() => {
    const editor = editorRef.current;
    if (!editor) return;
    const markdown = htmlToMd(editor.innerHTML);
    if (markdown !== lastEmittedRef.current) {
      lastEmittedRef.current = markdown;
      onChange(markdown);
    }
  }, [onChange]);

  const runCommand = useCallback((command: Command) => {
    const editor = editorRef.current;
    if (!editor) return;
    editor.focus();
    if (command === "formatBlock:h3") {
      document.execCommand("formatBlock", false, "h3");
    } else if (command === "formatBlock:blockquote") {
      document.execCommand("formatBlock", false, "blockquote");
    } else {
      document.execCommand(command, false);
    }
    emit();
  }, [emit]);

  // Expose markdown insertion (used by the Images panel).
  useEffect(() => {
    if (insertMarkdownRef) {
      insertMarkdownRef.current = (markdown: string) => {
        const editor = editorRef.current;
        if (!editor) return;
        editor.focus();
        const html = mdToHtml(markdown).trim();
        if (typeof window.getSelection === "function" && editor.contains(document.activeElement)) {
          document.execCommand("insertHTML", false, html);
        } else {
          editor.innerHTML += html;
        }
        emit();
      };
      return () => {
        insertMarkdownRef.current = null;
      };
    }
    return undefined;
  }, [insertMarkdownRef, emit]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center gap-1 border-b border-border bg-card/40 px-3 py-1.5">
        {TOOLBAR.map((item) => (
          <button
            key={item.command}
            type="button"
            title={item.title}
            disabled={disabled}
            onMouseDown={(event) => {
              // Prevent the editor from losing focus before the command runs.
              event.preventDefault();
              runCommand(item.command);
            }}
            className="rounded px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-40"
          >
            {item.label}
          </button>
        ))}
        <span className="ml-auto text-[10px] text-muted-foreground">
          Ctrl+S save · Ctrl+F search
        </span>
      </div>
      <div
        ref={editorRef}
        contentEditable={!disabled}
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        aria-label="Chapter editor"
        onInput={emit}
        onBlur={emit}
        className="rich-editor flex-1 overflow-y-auto px-6 py-5 text-sm leading-relaxed text-foreground outline-none"
        data-placeholder={placeholder}
      />
    </div>
  );
}
