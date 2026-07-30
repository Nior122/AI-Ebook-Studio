"""Structured Document Model — the canonical in-memory representation of a book.

Every book is represented internally as a tree of typed, uniquely-identified
nodes rather than a blob of plain text::

    Project
      └── Book
            └── Part (optional)
                  └── Chapter
                        └── Section
                              └── Paragraph
                                    └── Sentence

Each :class:`DocumentNode` carries a stable UUID and a ``node_type``. Future
modules (Editing, Images, Translation, DOCX export, KDP Validator) consume and
mutate this tree instead of reparsing raw text, so that:

* Editing one paragraph only touches that paragraph node.
* Attaching an image to a section only mutates that section node.
* Translating one chapter operates on the chapter subtree.
* Exporting walks the tree once without re-parsing.

The Writing Engine produces :class:`DocumentNode` trees; persistence layer
(:mod:`models.document`) mirrors the same hierarchy into relational tables.
This module is deliberately framework-free (no SQLAlchemy, no Pydantic) so it
can be imported anywhere without pulling persistence concerns.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class DocumentNodeType(StrEnum):
    """Every level of the book hierarchy plus a synthetic root."""

    PROJECT = "project"
    BOOK = "book"
    PART = "part"
    CHAPTER = "chapter"
    SECTION = "section"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"


# Parent type each node type is allowed to live under. The Writing Engine and
# validators consult this map to guarantee structural integrity of the tree.
_ALLOWED_PARENT: dict[DocumentNodeType, tuple[DocumentNodeType, ...]] = {
    DocumentNodeType.BOOK: (DocumentNodeType.PROJECT,),
    DocumentNodeType.PART: (DocumentNodeType.BOOK,),
    DocumentNodeType.CHAPTER: (DocumentNodeType.BOOK, DocumentNodeType.PART),
    DocumentNodeType.SECTION: (DocumentNodeType.CHAPTER,),
    DocumentNodeType.PARAGRAPH: (DocumentNodeType.SECTION,),
    DocumentNodeType.SENTENCE: (DocumentNodeType.PARAGRAPH,),
}

# Leaves hold the actual prose; branches only structure the document.
_LEAF_TYPES: frozenset[DocumentNodeType] = frozenset({DocumentNodeType.SENTENCE})

# Sentence-delimiter join when flattening a paragraph back to prose.
_SENTENCE_JOIN = " "

# Paragraph separator when flattening a section/book to plain text.
_PARAGRAPH_JOIN = "\n\n"


class DocumentModelError(ValueError):
    """Raised when a DocumentNode tree violates the structural contract."""


@dataclass
class DocumentNode:
    """A single addressable element of a book.

    ``id`` is stable for the lifetime of the node: downstream modules reference
    nodes by id (e.g. "translate chapter <id>", "attach image to section <id>")
    rather than by text position, so structural edits never invalidate them.
    """

    node_type: DocumentNodeType
    id: UUID = field(default_factory=uuid4)
    title: str | None = None
    text: str | None = None
    position: int = 0
    status: str = "draft"
    kind: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # attachments are how non-prose modules pin data to a node without changing
    # the prose: image placements, translation refs, export anchors, KDP flags.
    attachments: dict[str, Any] = field(default_factory=dict)
    children: list[DocumentNode] = field(default_factory=list)
    parent_id: UUID | None = None

    # ------------------------------------------------------------------
    # construction / parenting
    # ------------------------------------------------------------------
    def add_child(self, child: DocumentNode) -> DocumentNode:
        """Append ``child`` after validating hierarchy + assigning parentage."""
        if child.node_type not in _ALLOWED_PARENT or self.node_type not in _ALLOWED_PARENT.get(
            child.node_type, ()
        ):
            raise DocumentModelError(
                f"A {child.node_type.value!r} node cannot be parented under a "
                f"{self.node_type.value!r} node."
            )
        child.parent_id = self.id
        if not child.children and child.node_type not in _LEAF_TYPES:
            # branches are addressable even when empty
            pass
        child.position = len(self.children)
        self.children.append(child)
        return child

    def insert_child(self, index: int, child: DocumentNode) -> DocumentNode:
        """Insert ``child`` at ``index`` and renumber sibling positions."""
        self._validate_parentable(child)
        child.parent_id = self.id
        self.children.insert(index, child)
        self._renumber()
        return child

    def remove_child(self, child: DocumentNode | UUID) -> DocumentNode | None:
        """Detach a child node (and subtree) by node or id. Returns removed node."""
        target_id = child.id if isinstance(child, DocumentNode) else child
        for i, node in enumerate(self.children):
            if node.id == target_id:
                removed = self.children.pop(i)
                removed.parent_id = None
                self._renumber()
                return removed
        return None

    def replace_child(self, target: DocumentNode | UUID, replacement: DocumentNode) -> DocumentNode:
        """Replace a child in-place, preserving position. Returns the old child."""
        target_id = target.id if isinstance(target, DocumentNode) else target
        self._validate_parentable(replacement)
        for i, node in enumerate(self.children):
            if node.id == target_id:
                old = self.children[i]
                old.parent_id = None
                replacement.parent_id = self.id
                replacement.position = i
                self.children[i] = replacement
                return old
        raise DocumentModelError(f"Child {target_id} not found under {self.id}.")

    # ------------------------------------------------------------------
    # traversal
    # ------------------------------------------------------------------
    def find(self, node_id: UUID) -> DocumentNode | None:
        """Depth-first lookup of a node by id across the whole subtree."""
        if self.id == node_id:
            return self
        for child in self.children:
            found = child.find(node_id)
            if found is not None:
                return found
        return None

    def find_by_type(self, node_type: DocumentNodeType) -> list[DocumentNode]:
        """Return every descendant of a given type, in document order."""
        out: list[DocumentNode] = []
        for child in self.children:
            if child.node_type == node_type:
                out.append(child)
            out.extend(child.find_by_type(node_type))
        return out

    def walk(self) -> Iterator[DocumentNode]:
        """Pre-order traversal yielding self then every descendant."""
        yield self
        for child in self.children:
            yield from child.walk()

    def ancestors(self, root: DocumentNode) -> list[DocumentNode]:
        """Return the chain of ancestors from this node up to ``root``."""
        chain: list[DocumentNode] = []
        if self.parent_id is None or self.parent_id == root.id:
            return chain
        parent = root.find(self.parent_id)
        while parent is not None and parent.id != root.id:
            chain.append(parent)
            parent = root.find(parent.parent_id) if parent.parent_id else None
        return list(reversed(chain))

    # ------------------------------------------------------------------
    # text helpers — used by DOCX/KDP/export consumers
    # ------------------------------------------------------------------
    def plain_text(self) -> str:
        """Flatten the subtree into readable prose.

        Branch nodes contribute an optional title heading; leaves contribute
        their ``text``. This is a *projection* of the tree, never the source of
        truth — downstream modules read the tree, not this string.
        """
        parts: list[str] = []
        if self.title:
            parts.append(self.title)
        if self.text:
            parts.append(self.text)
        if self.node_type == DocumentNodeType.PARAGRAPH:
            return _SENTENCE_JOIN.join(s.text for s in self.children if s.text) or (self.text or "")
        for child in self.children:
            child_text = child.plain_text()
            if child_text:
                parts.append(child_text)
        if self.node_type == DocumentNodeType.SECTION:
            return _PARAGRAPH_JOIN.join(p for p in parts if p)
        return _PARAGRAPH_JOIN.join(p for p in parts if p) if parts else ""

    def word_count(self) -> int:
        """Cached-friendly word count derived from leaf text."""
        return sum(len((n.text or "").split()) for n in self.walk() if n.node_type in _LEAF_TYPES)

    # ------------------------------------------------------------------
    # mutation helpers used by the Editing module
    # ------------------------------------------------------------------
    def set_text(self, text: str) -> None:
        """Set prose on a leaf node; branches must not carry text."""
        if self.node_type not in _LEAF_TYPES and self.children:
            raise DocumentModelError(
                f"Cannot set text on a {self.node_type.value!r} branch with children."
            )
        self.text = text

    def attach(self, key: str, value: Any) -> None:
        """Pin a non-prose payload (image, translation ref, export anchor) here."""
        self.attachments[key] = value

    def detach(self, key: str) -> Any | None:
        """Remove and return a previously-attached payload."""
        return self.attachments.pop(key, None)

    # ------------------------------------------------------------------
    # serialization — round-trips through dicts for JSONB snapshots / API
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """Serialize the subtree to a plain dict (JSON-safe)."""
        return {
            "id": str(self.id),
            "node_type": self.node_type.value,
            "title": self.title,
            "text": self.text,
            "position": self.position,
            "status": self.status,
            "kind": self.kind,
            "metadata": self.metadata,
            "attachments": self.attachments,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentNode:
        """Reconstruct a subtree from a serialized dict."""
        node_obj = cls(
            node_type=DocumentNodeType(data["node_type"]),
            id=UUID(data["id"]),
            title=data.get("title"),
            text=data.get("text"),
            position=data.get("position", 0),
            status=data.get("status", "draft"),
            kind=data.get("kind"),
            metadata=dict(data.get("metadata") or {}),
            attachments=dict(data.get("attachments") or {}),
            parent_id=UUID(data["parent_id"]) if data.get("parent_id") else None,
        )
        for child_data in data.get("children") or []:
            child = cls.from_dict(child_data)
            child.parent_id = node_obj.id
            node_obj.children.append(child)
        return node_obj

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _validate_parentable(self, child: DocumentNode) -> None:
        if self.node_type not in _ALLOWED_PARENT.get(child.node_type, ()):
            raise DocumentModelError(
                f"A {child.node_type.value!r} node cannot be parented under a "
                f"{self.node_type.value!r} node."
            )

    def _renumber(self) -> None:
        for i, node in enumerate(self.children):
            node.position = i


@dataclass
class StructuredDocument:
    """Rooted wrapper around a Book's :class:`DocumentNode` tree.

    Holds the project- and book-level bookends and exposes the operations every
    downstream module needs. Modules never hold a raw :class:`DocumentNode`
    root; they receive a :class:`StructuredDocument` so that traversal,
    versioning, and snapshotting stay centralized.
    """

    project_id: UUID
    book_id: UUID
    root: DocumentNode  # a BOOK node

    # ------------------------------------------------------------------
    # lookups
    # ------------------------------------------------------------------
    def find(self, node_id: UUID) -> DocumentNode | None:
        """Locate any node in the book by its stable id."""
        return self.root.find(node_id)

    def require(self, node_id: UUID) -> DocumentNode:
        """Like :meth:`find` but raises if missing — use for module entrypoints."""
        node = self.find(node_id)
        if node is None:
            raise DocumentModelError(f"Node {node_id} not found in book {self.book_id}.")
        return node

    def chapters(self) -> list[DocumentNode]:
        """All chapters in document order, regardless of part grouping."""
        return self.root.find_by_type(DocumentNodeType.CHAPTER)

    def sections(self, chapter_id: UUID) -> list[DocumentNode]:
        """Sections directly under a chapter."""
        chapter = self.require(chapter_id)
        return [c for c in chapter.children if c.node_type == DocumentNodeType.SECTION]

    def paragraphs(self, section_id: UUID) -> list[DocumentNode]:
        """Paragraphs directly under a section."""
        section = self.require(section_id)
        return [c for c in section.children if c.node_type == DocumentNodeType.PARAGRAPH]

    def sentences(self, paragraph_id: UUID) -> list[DocumentNode]:
        """Sentences directly under a paragraph."""
        paragraph = self.require(paragraph_id)
        return [c for c in paragraph.children if c.node_type == DocumentNodeType.SENTENCE]

    # ------------------------------------------------------------------
    # whole-document operations
    # ------------------------------------------------------------------
    def walk(self) -> Iterator[DocumentNode]:
        """Yield every node in the book (book node first)."""
        yield from self.root.walk()

    def plain_text(self) -> str:
        """Flatten the entire book to prose (export / KDP projection only)."""
        return self.root.plain_text()

    def word_count(self) -> int:
        """Total word count across the book."""
        return self.root.word_count()

    def map_leaves(self, fn: Callable[[DocumentNode], None]) -> None:
        """Apply ``fn`` to every leaf (sentence) node in place.

        Used by the Translation module to rewrite prose node-by-node while
        preserving structure and ids.
        """
        for node in self.walk():
            if node.node_type in _LEAF_TYPES:
                fn(node)

    # ------------------------------------------------------------------
    # versioning / persistence bridges
    # ------------------------------------------------------------------
    def to_snapshot(self) -> dict[str, Any]:
        """Serialize the whole book tree for a :class:`BookVersion` snapshot."""
        return {
            "project_id": str(self.project_id),
            "book_id": str(self.book_id),
            "root": self.root.to_dict(),
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> StructuredDocument:
        """Rehydrate a :class:`StructuredDocument` from a snapshot dict."""
        return cls(
            project_id=UUID(data["project_id"]),
            book_id=UUID(data["book_id"]),
            root=DocumentNode.from_dict(data["root"]),
        )

    # ------------------------------------------------------------------
    # factory used by the Writing Engine to start a new book tree
    # ------------------------------------------------------------------
    @classmethod
    def new_book(
        cls,
        project_id: UUID,
        book_id: UUID,
        title: str,
        *,
        status: str = "draft",
    ) -> StructuredDocument:
        """Create an empty structured document rooted at a Book node."""
        root = DocumentNode(
            node_type=DocumentNodeType.BOOK,
            title=title,
            status=status,
        )
        return cls(project_id=project_id, book_id=book_id, root=root)


def node(node_type: DocumentNodeType | str, **kwargs: Any) -> DocumentNode:
    """Concise constructor used by builders/tests: ``node("paragraph")``."""
    nt = DocumentNodeType(node_type) if isinstance(node_type, str) else node_type
    return DocumentNode(node_type=nt, **kwargs)
