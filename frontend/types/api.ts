// Frontend API contract types.
// These mirror the backend Pydantic schemas (auth, projects, books, settings)
// so the typed API client and React Query hooks stay in sync with the server.
// Keep field names identical to the backend JSON keys.

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface UserProfile {
  id: string;
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
  timezone: string | null;
}

export interface User {
  id: string;
  email: string;
  status: string;
  stage: string;
  is_email_verified: boolean;
  created_at: string;
  profile: UserProfile;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at: string;
}

export interface AuthResponse {
  user: User;
  tokens: TokenPair;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  display_name: string;
}

// ---------------------------------------------------------------------------
// Workspaces
// ---------------------------------------------------------------------------

export interface Workspace {
  id: string;
  name: string;
  status: string;
  stage: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export type ProjectStatus = "active" | "archived" | "completed" | "draft";

export interface Project {
  id: string;
  workspace_id: string;
  owner_user_id: string;
  name: string;
  title: string;
  description: string | null;
  status: string;
  stage: string;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreatePayload {
  workspace_id: string;
  name: string;
  title?: string | null;
  description?: string | null;
}

export interface ProjectUpdatePayload {
  name?: string | null;
  title?: string | null;
  description?: string | null;
  status?: string | null;
  is_favorite?: boolean | null;
}

// ---------------------------------------------------------------------------
// Books
// ---------------------------------------------------------------------------

export type BookStatus = "draft" | "in_progress" | "completed" | "published";

export interface Book {
  id: string;
  project_id: string;
  title: string;
  subtitle: string | null;
  author_name: string | null;
  description: string | null;
  language: string;
  target_audience: string | null;
  writing_style: string | null;
  status: string;
  stage: string;
  metadata_json?: { writing_book_id?: string } | null;
  created_at: string;
  updated_at: string;
}

export interface BookCreatePayload {
  title: string;
  subtitle?: string | null;
  author_name?: string | null;
  description?: string | null;
  language?: string;
  target_audience?: string | null;
  writing_style?: string | null;
}

export interface BookUpdatePayload {
  title?: string | null;
  subtitle?: string | null;
  author_name?: string | null;
  description?: string | null;
  language?: string | null;
  target_audience?: string | null;
  writing_style?: string | null;
  status?: string | null;
}

// ---------------------------------------------------------------------------
// Chapters
// ---------------------------------------------------------------------------

export interface Chapter {
  id: string;
  book_id: string;
  chapter_number: number;
  title: string;
  content: string;
  word_count: number;
  status: string;
  stage: string;
  created_at: string;
  updated_at: string;
}

export interface ChapterCreatePayload {
  title: string;
  content?: string;
  chapter_number?: number;
}

export interface ChapterUpdatePayload {
  title?: string | null;
  content?: string | null;
  chapter_number?: number;
  status?: string | null;
}

// ---------------------------------------------------------------------------
// Book settings (formatting)
// ---------------------------------------------------------------------------

export type TrimSize = "6x9" | "8x10" | "A4" | "Letter" | "custom";
export type ImageAlignment = "left" | "center" | "right";

export interface BookSettings {
  id: string;
  book_id: string;
  kdp_trim_size: TrimSize;
  custom_format_enabled: boolean;
  page_width: number;
  page_height: number;
  margin_top: number;
  margin_bottom: number;
  margin_left: number;
  margin_right: number;
  body_font: string;
  body_font_size: number;
  heading_font: string;
  line_spacing: number;
  paragraph_spacing: number;
  image_width: number;
  image_alignment: ImageAlignment;
  image_aspect_ratio: string;
  image_style: string;
  caption_enabled: boolean;
  caption_font_size: number;
  chapter_page_breaks: boolean;
  toc_enabled: boolean;
}

export type BookSettingsUpdatePayload = Partial<BookSettings>;

// ---------------------------------------------------------------------------
// Phase 6: Book Writing Engine (user-owned book workflow)
// ---------------------------------------------------------------------------

export type WritingBookStatus =
  | "draft" | "planning" | "outlining" | "writing"
  | "editing" | "ready_for_formatting" | "completed";

export type WritingBookStep =
  | "idea" | "brief" | "blueprint" | "outline"
  | "writing" | "editing" | "formatting" | "export";

export interface WritingBook {
  id: string;
  user_id: string;
  title: string;
  subtitle: string | null;
  description: string | null;
  author_name: string | null;
  target_audience: string | null;
  book_type: string | null;
  language: string;
  tone: string | null;
  approximate_length: string | null;
  status: WritingBookStatus;
  current_step: WritingBookStep;
  created_at: string;
  updated_at: string;
}

export interface WritingBookCreatePayload {
  title: string;
  subtitle?: string | null;
  description?: string | null;
  author_name?: string | null;
  target_audience?: string | null;
  book_type?: string | null;
  language?: string;
  tone?: string | null;
  approximate_length?: string | null;
}

export interface WritingBookUpdatePayload {
  title?: string | null;
  subtitle?: string | null;
  description?: string | null;
  author_name?: string | null;
  target_audience?: string | null;
  book_type?: string | null;
  language?: string | null;
  tone?: string | null;
  approximate_length?: string | null;
  status?: string | null;
  current_step?: string | null;
}

export interface BookBrief {
  id: string;
  book_id: string;
  working_title: string | null;
  subtitle: string | null;
  book_purpose: string | null;
  target_reader: string | null;
  reader_problems: string[];
  promised_transformation: string | null;
  tone: string | null;
  writing_style: string | null;
  key_themes: string[];
  major_concepts: string[];
  topics_to_avoid: string[];
  suggested_structure: string | null;
  estimated_chapter_count: number | null;
  estimated_word_count: number | null;
  raw_content: string | null;
  created_at: string;
  updated_at: string;
}

export interface BookBriefUpdatePayload {
  working_title?: string | null;
  subtitle?: string | null;
  book_purpose?: string | null;
  target_reader?: string | null;
  reader_problems?: string[] | null;
  promised_transformation?: string | null;
  tone?: string | null;
  writing_style?: string | null;
  key_themes?: string[] | null;
  major_concepts?: string[] | null;
  topics_to_avoid?: string[] | null;
  suggested_structure?: string | null;
  estimated_chapter_count?: number | null;
  estimated_word_count?: number | null;
  raw_content?: string | null;
}

export interface BlueprintChapterPlan {
  title: string;
  objective?: string | null;
  summary?: string | null;
  key_lessons?: string[];
  important_examples?: string[];
  practical_exercises?: string[];
  estimated_word_count?: number | null;
  connects_to_previous?: string | null;
  connects_to_future?: string | null;
}

export interface BookBlueprint {
  id: string;
  book_id: string;
  introduction_purpose: string | null;
  chapters: BlueprintChapterPlan[];
  estimated_total_word_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface BookBlueprintUpdatePayload {
  introduction_purpose?: string | null;
  chapters?: BlueprintChapterPlan[] | null;
  estimated_total_word_count?: number | null;
}

export interface WritingChapterOutlineSection {
  title: string;
  purpose?: string | null;
  key_points?: string[];
}

export type ChapterStatus =
  | "planned" | "outlining" | "generating" | "draft"
  | "editing" | "approved" | "needs_revision";

export interface WritingChapter {
  id: string;
  book_id: string;
  chapter_number: number;
  title: string;
  purpose: string | null;
  objective: string | null;
  summary: string | null;
  outline: string | null;
  outline_sections: WritingChapterOutlineSection[];
  content: string;
  status: ChapterStatus;
  target_word_count: number | null;
  actual_word_count: number;
  is_approved: boolean;
  created_at: string;
  updated_at: string;
}

export interface WritingChapterCreatePayload {
  title: string;
  chapter_number?: number | null;
  purpose?: string | null;
  objective?: string | null;
  summary?: string | null;
  target_word_count?: number | null;
}

export interface WritingChapterUpdatePayload {
  title?: string | null;
  chapter_number?: number | null;
  purpose?: string | null;
  objective?: string | null;
  summary?: string | null;
  outline?: string | null;
  outline_sections?: WritingChapterOutlineSection[] | null;
  content?: string | null;
  status?: string | null;
  target_word_count?: number | null;
  is_approved?: boolean | null;
}

export interface ChapterVersion {
  id: string;
  chapter_id: string;
  version_number: number;
  content: string;
  word_count: number;
  version_type: string;
  generation_metadata: Record<string, unknown>;
  created_at: string;
  created_by: string | null;
}

export type VersionType = "ai_generated" | "user_edited" | "ai_edited" | "approved";

export interface Manuscript {
  id: string;
  book_id: string;
  full_text: string;
  word_count: number;
  chapter_order: string[];
  is_stale: boolean;
  created_at: string;
  updated_at: string;
}

export interface WritingBookSettings {
  id: string;
  book_id: string;
  tone: string | null;
  formality: string | null;
  sentence_complexity: string | null;
  paragraph_length: string | null;
  use_examples: string | null;
  use_stories: string | null;
  use_analogies: string | null;
  use_humor: string | null;
  use_practical_exercises: string | null;
  point_of_view: string | null;
  reading_level: string | null;
  preferred_provider: string | null;
  preferred_model: string | null;
  temperature: number;
  stream_responses: boolean;
  style_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface WritingBookSettingsUpdatePayload {
  tone?: string | null;
  formality?: string | null;
  sentence_complexity?: string | null;
  paragraph_length?: string | null;
  use_examples?: string | null;
  use_stories?: string | null;
  use_analogies?: string | null;
  use_humor?: string | null;
  use_practical_exercises?: string | null;
  point_of_view?: string | null;
  reading_level?: string | null;
  preferred_provider?: string | null;
  preferred_model?: string | null;
  temperature?: number | null;
  stream_responses?: boolean | null;
  style_notes?: string | null;
}

export interface GenerateRequest {
  provider?: string | null;
  model?: string | null;
  temperature?: number | null;
  instruction?: string | null;
  selected_text?: string | null;
}

export interface BookWorkflow {
  book_id: string;
  current_step: string;
  status: string;
  stage: string;
  has_brief: boolean;
  has_blueprint: boolean;
  chapter_count: number;
  approved_chapter_count: number;
  version_count: number;
}

// ---------------------------------------------------------------------------
// Generic API envelope
// ---------------------------------------------------------------------------

export interface MessageResponse {
  message: string;
}

// ---------------------------------------------------------------------------
// Phase 7 — AI Editing & Proofreading
// ---------------------------------------------------------------------------

export type SuggestionCategory =
  | "grammar" | "spelling" | "punctuation" | "clarity" | "style"
  | "tone" | "structure" | "consistency" | "repetition" | "fact_check";

export type SuggestionSeverity = "low" | "medium" | "high";
export type SuggestionStatus = "pending" | "accepted" | "rejected" | "ignored";

export type EditingMode =
  | "proofreading" | "clarity_editing" | "style_editing"
  | "structural_editing" | "consistency_check" | "repetition_check"
  | "full_review" | "fact_check";

export type ReviewJobStatus =
  | "queued" | "processing" | "saving_suggestions"
  | "completed" | "failed" | "cancelled";

export type SelectionAction =
  | "rewrite" | "improve_clarity" | "make_more_professional"
  | "make_more_conversational" | "simplify" | "improve_flow"
  | "reduce_repetition" | "expand_explanation" | "shorten" | "proofread";

export interface EditingSuggestion {
  id: string;
  chapter_id: string;
  session_id: string;
  batch_id: string | null;
  category: SuggestionCategory;
  severity: SuggestionSeverity;
  confidence: number;
  original_text: string;
  suggested_text: string | null;
  explanation: string | null;
  location_data: Record<string, unknown>;
  status: SuggestionStatus;
  created_at: string;
  updated_at: string;
  accepted_at: string | null;
  rejected_at: string | null;
  ignored_at: string | null;
}

export interface EditingSession {
  id: string;
  book_id: string;
  chapter_id: string;
  user_id: string;
  mode: EditingMode;
  status: string;
  stage: string;
  created_at: string;
  completed_at: string | null;
  suggestions: EditingSuggestion[];
}

export interface ChapterReviewResponse {
  session: EditingSession;
  suggestions: EditingSuggestion[];
}

export interface ReviewRequest {
  mode: EditingMode;
  selected_text?: string | null;
  instruction?: string | null;
  provider?: string | null;
  model?: string | null;
}

export interface SelectionActionRequest {
  selected_text: string;
  action: SelectionAction;
  instruction?: string | null;
  provider?: string | null;
  model?: string | null;
}

export interface StartFullReviewRequest {
  mode: EditingMode;
  chapter_ids?: string[] | null;
  provider?: string | null;
  model?: string | null;
}

export interface ReviewJob {
  id: string;
  book_id: string;
  chapter_id: string | null;
  mode: EditingMode;
  status: ReviewJobStatus;
  total_items: number;
  processed_items: number;
  progress: number;
  progress_data: Array<{ chapter_id: string; chapter_title: string; status: string; suggestion_count?: number }>;
  error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  failed_at: string | null;
}

export interface ReviewSummary {
  total: number;
  by_category: Record<string, number>;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
  high_severity: number;
  accepted: number;
  rejected: number;
  pending: number;
  ignored: number;
}

export interface BulkActionResponse {
  updated: number;
  chapter_version_created: boolean;
  chapter_id: string;
}

export interface DiffResponse {
  original: string;
  suggested: string;
  segments: Array<{ type: string; text: string }>;
}
