// Structured Document Model — shared contract for frontend and backend.
//
// Mirrors services/document_model.py. Every book is represented internally
// as a tree of typed, uniquely-identified nodes rather than plain text.
//
// Future modules (Editing, Images, Translation, DOCX, KDP Validator) all
// operate on this tree by node id.

export type DocumentNodeType =
  | "project"
  | "book"
  | "part"
  | "chapter"
  | "section"
  | "paragraph"
  | "sentence";

export interface DocumentNode {
  id: string;
  node_type: DocumentNodeType;
  title?: string | null;
  text?: string | null;
  position: number;
  status: string;
  kind?: string | null;
  metadata: Record<string, unknown>;
  attachments: Record<string, unknown>;
  parent_id?: string | null;
  children: DocumentNode[];
}

export interface StructuredDocument {
  project_id: string;
  book_id: string;
  root: DocumentNode;
}

// ---------------------------------------------------------------------------
// Per-level CRUD shapes
// ---------------------------------------------------------------------------

export interface PartCreateRequest {
  title: string;
  slug: string;
  position?: number;
  summary?: string | null;
  status?: string;
}

export interface PartUpdateRequest {
  title?: string;
  slug?: string;
  position?: number;
  summary?: string | null;
  status?: string;
}

export interface PartResponse {
  id: string;
  project_id: string;
  book_id: string;
  title: string;
  slug: string;
  position: number;
  summary: string | null;
  status: string;
  word_count: number;
  created_at: string;
  updated_at: string;
  chapter_count: number;
}

export interface ChapterCreateRequest {
  title: string;
  slug: string;
  part_id?: string | null;
  position?: number;
  summary?: string | null;
  status?: string;
}

export interface ChapterUpdateRequest {
  title?: string;
  slug?: string;
  part_id?: string | null;
  position?: number;
  summary?: string | null;
  status?: string;
}

export interface ChapterResponse {
  id: string;
  project_id: string;
  book_id: string;
  part_id: string | null;
  title: string;
  slug: string;
  position: number;
  summary: string | null;
  status: string;
  word_count: number;
  created_at: string;
  updated_at: string;
  section_count: number;
}

export interface SectionCreateRequest {
  title?: string | null;
  position?: number;
  status?: string;
}

export interface SectionUpdateRequest {
  title?: string | null;
  position?: number;
  status?: string;
}

export interface SectionResponse {
  id: string;
  project_id: string;
  book_id: string;
  chapter_id: string;
  title: string | null;
  position: number;
  status: string;
  word_count: number;
  created_at: string;
  updated_at: string;
  paragraph_count: number;
}

export interface ParagraphCreateRequest {
  kind?: string;
  position?: number;
  status?: string;
}

export interface ParagraphUpdateRequest {
  kind?: string;
  position?: number;
  status?: string;
}

export interface ParagraphResponse {
  id: string;
  project_id: string;
  book_id: string;
  chapter_id: string;
  section_id: string;
  kind: string;
  position: number;
  status: string;
  word_count: number;
  created_at: string;
  updated_at: string;
  sentence_count: number;
}

export interface SentenceCreateRequest {
  text: string;
  kind?: string;
  position?: number;
  status?: string;
}

export interface SentenceUpdateRequest {
  text?: string;
  kind?: string;
  position?: number;
  status?: string;
}

export interface SentenceResponse {
  id: string;
  project_id: string;
  book_id: string;
  chapter_id: string;
  section_id: string;
  paragraph_id: string;
  text: string;
  kind: string;
  position: number;
  status: string;
  created_at: string;
  updated_at: string;
}
