"use client";

// Keyboard shortcuts for the workspace:
//   Ctrl+S        save now
//   Ctrl+F        focus the manuscript search box
//   Ctrl+Z        undo (native editor undo)
//   Ctrl+Shift+Z  redo
// Shortcuts only fire when the user isn't typing in a plain input/textarea.

import { useEffect } from "react";

interface ShortcutHandlers {
  onSave: () => void;
  onSearch: () => void;
}

export function useShortcuts(handlers: ShortcutHandlers): void {
  const handlersRef = { current: handlers };
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const modifier = event.ctrlKey || event.metaKey;
      if (!modifier) return;

      const target = event.target as HTMLElement | null;
      const tag = target?.tagName?.toLowerCase();
      const inPlainField =
        tag === "input" || tag === "textarea" || (tag === "select" ?? false);

      if (event.key.toLowerCase() === "s") {
        event.preventDefault();
        handlersRef.current.onSave();
        return;
      }
      if (event.key.toLowerCase() === "f") {
        // Ctrl+F inside the editor keeps native find when the editor is focused.
        if (!inPlainField) {
          event.preventDefault();
          handlersRef.current.onSearch();
        }
        return;
      }
      // Ctrl+Z / Ctrl+Shift+Z: let the contentEditable handle undo/redo natively;
      // just make sure we don't trigger browser dialogs elsewhere.
      if (event.key.toLowerCase() === "z") {
        if (inPlainField) {
          event.preventDefault();
          document.execCommand(event.shiftKey ? "redo" : "undo");
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}
