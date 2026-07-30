"""Phase 7 — Diff utility for suggestion visualization.

Produces stable segment-style diffs between original_text and suggested_text.
The output is a list of dict segments with type 'added', 'removed', or 'same'
that a frontend diff viewer can render without fragile text matching.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

TagType = str  # "same" | "added" | "removed"


def compute_diff(original: str, suggested: str) -> list[dict[str, Any]]:
    """Compare *original* vs *suggested* and return a list of labeled segments."""
    if not original and not suggested:
        return []
    matcher = SequenceMatcher(None, original, suggested)
    segments: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            segments.append({"type": "same", "text": original[i1:i2]})
        elif tag == "replace":
            segments.append({"type": "removed", "text": original[i1:i2]})
            segments.append({"type": "added", "text": suggested[j1:j2]})
        elif tag == "delete":
            segments.append({"type": "removed", "text": original[i1:i2]})
        elif tag == "insert":
            segments.append({"type": "added", "text": suggested[j1:j2]})
    return segments