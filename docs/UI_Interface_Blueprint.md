# UI Interface Blueprint

## Purpose

This document defines the complete product interface direction for AI Ebook Studio using ASCII wireframes and UX notes.

It is a design document only. It does not implement application screens, components, routes, or frontend code.

## Product Feel

AI Ebook Studio should feel like:

- Notion for structured project organization.
- Figma for panels, inspectors, assets, and precision.
- ChatGPT for conversational AI assistance and iterative generation.
- Apple software for calm spacing, restraint, typography, and focus.

The interface should be modern, minimal, responsive, and work-focused. It should avoid heavy decoration and keep the user close to the content.

## Global Layout System

### Desktop Shell

```text
+--------------------------------------------------------------------------------+
| Top Bar: Workspace / Search / Command / Notifications / Account                 |
+----------------------+---------------------------------------------------------+
| Primary Sidebar      | Page Header: Title / Status / Actions                   |
|                      +---------------------------------------------------------+
| Dashboard            |                                                         |
| Projects             | Main Canvas                                             |
| Templates            |                                                         |
| History              |                                                         |
| Settings             |                                                         |
|                      |                                                         |
| Recent Projects      |                                                         |
| - Project A          |                                                         |
| - Project B          |                                                         |
+----------------------+---------------------------------------------------------+
```

### Workspace Shell

```text
+--------------------------------------------------------------------------------+
| Project Top Bar: Project Name / Workflow Stepper / Share / Export               |
+----------------------+--------------------------------------+-------------------+
| Project Sidebar      | Main Editor Canvas                   | Inspector Panel   |
|                      |                                      |                   |
| Overview             | Content, tools, previews, or chat    | Contextual tools  |
| Writing              |                                      | Settings          |
| Editing              |                                      | Suggestions       |
| Images               |                                      | Metadata          |
| Formatting           |                                      | Status            |
| Validation           |                                      |                   |
| Cover                |                                      |                   |
| Marketing            |                                      |                   |
| Translation          |                                      |                   |
| Export               |                                      |                   |
+----------------------+--------------------------------------+-------------------+
```

### Mobile Shell

```text
+----------------------------------+
| Top Bar: Menu / Title / Account  |
+----------------------------------+
| Workflow Stepper                 |
+----------------------------------+
| Main Content                     |
|                                  |
| Panels become sheets or tabs     |
|                                  |
+----------------------------------+
| Bottom Nav: Home Projects Tools  |
+----------------------------------+
```

## Global Navigation

### Top Bar

Purpose:
Provides global orientation and fast access to search, commands, notifications, and account controls.

Elements:
- Workspace switcher: future team workspace selection.
- Global search: opens command search for projects, chapters, assets, exports, and settings.
- Command button: opens the command palette.
- Notifications button: opens notifications popover.
- Account button: opens profile menu.

Buttons:
- Search: opens search overlay.
- Command: opens command palette with quick actions.
- Notifications: opens notification list.
- Account: opens account menu with settings, help, logout.

### Primary Sidebar

Purpose:
Acts as the persistent product map for app-level navigation.

Items:
- Dashboard
- Projects
- Templates
- History
- Settings
- Help

Behavior:
- Collapsible on desktop.
- Hidden behind a menu button on tablet/mobile.
- Recent projects appear below primary items.
- Active item uses quiet highlight, not heavy color.

### Project Sidebar

Purpose:
Guides the user through the ebook production workflow.

Items:
- Overview
- Writing
- Editing
- Images
- Formatting
- Validation
- Cover
- Marketing
- Translation
- Export
- History
- Settings

Behavior:
- Shows completion status per workflow step.
- Supports quick navigation between chapters.
- On mobile, becomes a workflow drawer.

### Inspector Panel

Purpose:
Provides contextual controls without cluttering the main canvas.

Common content:
- Metadata
- AI provider selection
- Prompt template selection
- Status
- Warnings
- Suggestions
- Related assets
- Version notes

Behavior:
- Right side on desktop.
- Slide-over sheet on tablet.
- Bottom sheet on mobile.

## Global Popups And Overlays

### Command Palette

```text
+------------------------------------------------+
| Search commands, projects, chapters, assets... |
+------------------------------------------------+
| Create project                                 |
| Generate chapter outline                       |
| Run validation                                 |
| Export EPUB                                    |
| Open settings                                  |
+------------------------------------------------+
```

Purpose:
Fast keyboard-first navigation and action execution.

Buttons/actions:
- Enter: run selected action.
- Escape: close.
- Filters: narrow to projects, commands, chapters, assets.

### Confirmation Dialog

```text
+------------------------------------------+
| Archive Project?                         |
| This project will move out of active work|
| and can be restored later.               |
|                                          |
| [Cancel]                    [Archive]    |
+------------------------------------------+
```

Purpose:
Confirms destructive or state-changing actions.

Buttons:
- Cancel: closes without changes.
- Primary action: performs the confirmed action.

### AI Generation Sheet

```text
+--------------------------------------------------+
| Generate with AI                                 |
| Provider: [OpenAI v] Model: [Default v]          |
| Prompt Template: [Chapter Draft v]               |
|                                                  |
| Instruction                                      |
| +----------------------------------------------+ |
| | Write a practical introduction...            | |
| +----------------------------------------------+ |
|                                                  |
| [Cancel] [Save as Template] [Generate]           |
+--------------------------------------------------+
```

Purpose:
Shared interface for writing, editing, image prompt, marketing, and translation generation.

Buttons:
- Cancel: closes sheet.
- Save as Template: stores reusable prompt template.
- Generate: starts async job.

### Job Progress Popover

```text
+------------------------------------+
| Generating EPUB                    |
| [==========------] 64%             |
| Formatting chapters                |
|                                    |
| [View Logs]              [Cancel]  |
+------------------------------------+
```

Purpose:
Shows long-running task status.

Buttons:
- View Logs: opens job detail drawer.
- Cancel: requests job cancellation when allowed.

## Page Designs

## 1. Login

### Wireframe

```text
+----------------------------------------------------------------------------+
|                                                                            |
|                              AI Ebook Studio                               |
|                                                                            |
|                       +--------------------------------+                   |
|                       | Sign in                        |                   |
|                       |                                |                   |
|                       | Email                          |                   |
|                       | +----------------------------+ |                   |
|                       | Password                       |                   |
|                       | +----------------------------+ |                   |
|                       |                                |                   |
|                       | [ Sign In ]                    |                   |
|                       |                                |                   |
|                       | Forgot password?               |                   |
|                       | New here? Create account       |                   |
|                       +--------------------------------+                   |
|                                                                            |
+----------------------------------------------------------------------------+
```

### Page Explanation

The login page is intentionally quiet and centered. It should feel secure, polished, and fast. The product name is the main brand signal; no marketing clutter appears here.

### Buttons

- Sign In: validates credentials and starts a session.
- Forgot password: opens password reset flow.
- Create account: switches to registration page.

### Popups

- Error toast: appears for invalid credentials or unavailable service.
- Password reset dialog: collects email and confirms request submission.

### Responsive Behavior

- Desktop: centered login card.
- Mobile: full-width form with comfortable spacing and large tap targets.

## 2. Dashboard

### Wireframe

```text
+--------------------------------------------------------------------------------+
| AI Ebook Studio        Search...                         Bell  Account          |
+----------------------+---------------------------------------------------------+
| Dashboard            | Good morning, Author                         [New Book] |
| Projects             |---------------------------------------------------------|
| Templates            | Active Projects                                         |
| History              | +----------------+ +----------------+ +---------------+ |
| Settings             | | Meal Prep      | | Kids Story    | | AI Workbook   | |
|                      | | Draft          | | Editing       | | Validation    | |
| Recent               | | 42% complete   | | 66% complete  | | 81% complete  | |
| - Meal Prep          | +----------------+ +----------------+ +---------------+ |
| - Kids Story         |                                                         |
|                      | Next Actions                                            |
|                      | +-----------------------------------------------------+ |
|                      | | Run validation on AI Workbook                       | |
|                      | | Review generated cover concepts                     | |
|                      | | Export latest EPUB                                  | |
|                      | +-----------------------------------------------------+ |
+----------------------+---------------------------------------------------------+
```

### Page Explanation

The dashboard gives the user a calm overview of all active work. It emphasizes progress, next actions, and recent projects rather than analytics overload.

### Buttons

- New Book: opens create project modal.
- Project card: opens project detail.
- Next action row: deep-links to the relevant workspace.
- Search: opens global search.
- Bell: opens notifications popover.
- Account: opens profile menu.

### Popups

- Create Project modal.
- Notifications popover.
- Account menu.
- Command palette.

### Workflow

The user lands here after login, sees where work is blocked, and continues the most urgent project action.

## 3. Project List

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Projects                                      [Import] [New Project]            |
+--------------------------------------------------------------------------------+
| Filters: [All] [Draft] [Editing] [Ready] [Archived]       Sort: Updated v      |
+--------------------------------------------------------------------------------+
| + Project Name          Status       Books   Updated        Actions             |
| | Meal Prep Guide       Draft        1       Today          Open  ...           |
| | Kids Bedtime Story    Editing      1       Yesterday      Open  ...           |
| | Business Workbook     Ready        2       Jul 4          Open  ...           |
+--------------------------------------------------------------------------------+
```

### Page Explanation

The project list is a clean management table. It should feel more like a professional file browser than a marketing grid.

### Buttons

- Import: future option for importing existing manuscripts.
- New Project: opens create project modal.
- Filter pills: filter the table by project status.
- Sort dropdown: changes table order.
- Open: opens project detail.
- More menu: archive, duplicate, rename, delete.

### Popups

- Create Project modal.
- Import modal.
- Row action menu.
- Archive/delete confirmation dialog.

### Workflow

Users find, filter, create, import, or manage project workspaces.

## 4. Project Detail

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Meal Prep Guide                 Draft        [Share] [Run Validation] [Export] |
+----------------------+--------------------------------------+-------------------+
| Overview             | Project Overview                     | Project Inspector |
| Writing              |                                      | Title             |
| Editing              | Progress                             | Meal Prep Guide   |
| Images               | [Writing 60%] [Editing 20%]          |                   |
| Formatting           | [Images 10%]  [Validation 0%]        | Status: Draft     |
| Validation           |                                      | Language: English |
| Cover                | Books                                |                   |
| Marketing            | +----------------------------------+ | Next Best Action  |
| Translation          | | Healthy Meal Prep                | | Continue Writing |
| Export               | | 12 chapters, 18k words           | | [Open Writing]   |
| History              | +----------------------------------+ |                   |
+----------------------+--------------------------------------+-------------------+
```

### Page Explanation

Project detail is the command center for one ebook project. It summarizes status and routes the user into the right workspace.

### Buttons

- Share: future collaboration sharing.
- Run Validation: starts validation job.
- Export: opens export workflow.
- Open Writing: moves to writing workspace.
- Sidebar items: navigate within project workflow.

### Popups

- Share dialog.
- Validation job sheet.
- Export settings dialog.
- Project settings drawer.

### Workflow

Users review project health, then choose the next production step.

## 5. Writing Workspace

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Meal Prep Guide / Writing                         [AI Draft] [Save] [Preview] |
+----------------------+--------------------------------------+-------------------+
| Chapters             | Chapter 1: Getting Started           | AI Writing Panel  |
| + Intro              |--------------------------------------| Provider          |
| + Getting Started *  | Start with simple meals that...      | [OpenAI v]        |
| + Weekly Planning    |                                      | Template          |
| + Shopping List      |                                      | [Chapter Draft v] |
|                      |                                      |                   |
| Outline              |                                      | Instruction       |
| - Goal               |                                      | +---------------+ |
| - Key points         |                                      | | Continue this | |
| - Notes              |                                      | +---------------+ |
|                      |                                      | [Generate]        |
+----------------------+--------------------------------------+-------------------+
```

### Page Explanation

Writing is a focused document workspace. The center is the manuscript, the left is structure, and the right is AI assistance.

### Buttons

- AI Draft: opens generation sheet.
- Save: saves chapter changes.
- Preview: opens reader-style preview.
- Chapter item: opens chapter.
- Add Chapter: creates a new chapter.
- Generate: starts AI writing job.
- Template dropdown: selects prompt template.
- Provider dropdown: selects AI provider.

### Popups

- AI generation sheet.
- Unsaved changes dialog.
- Prompt template picker.
- Chapter creation modal.
- Job progress popover.

### Sidebar

The chapter sidebar shows structure, status, and quick notes. Draft chapters use subtle status markers.

### Workflow

User selects a chapter, writes manually or with AI, reviews output, saves, and moves to editing.

## 6. Editing Workspace

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Meal Prep Guide / Editing             [Analyze] [Revise] [Accept Changes]      |
+----------------------+--------------------------------------+-------------------+
| Review Queue         | Original / Revised                   | Suggestions       |
| - Chapter 1          | +----------------+ +---------------+ | Clarity: 8 issues |
| - Chapter 2          | | Original       | | Revised       | | Tone: 2 issues    |
| - Chapter 3          | | text...        | | text...       | | Structure: good   |
|                      | +----------------+ +---------------+ |                   |
| Filters              |                                      | [Apply Selected]  |
| [Clarity]            | Inline comments and changes          | [Reject]          |
| [Grammar]            |                                      | [Regenerate]      |
| [Tone]               |                                      |                   |
+----------------------+--------------------------------------+-------------------+
```

### Page Explanation

Editing combines document comparison, review queue, and AI suggestions. It should feel like a calm editorial cockpit.

### Buttons

- Analyze: starts analysis job.
- Revise: starts revision job.
- Accept Changes: applies approved revision to chapter.
- Apply Selected: applies selected suggestion.
- Reject: rejects suggestion or revision.
- Regenerate: reruns edit with adjusted instruction.
- Filters: show selected issue types.

### Popups

- Analysis settings sheet.
- Revision instruction sheet.
- Accept changes confirmation.
- Suggestion detail popover.

### Workflow

User runs analysis, reviews suggestions, applies or rejects edits, then marks chapter as approved.

## 7. Image Workspace

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Meal Prep Guide / Images                    [New Plan] [Generate] [Upload]     |
+----------------------+--------------------------------------+-------------------+
| Image Plans          | Asset Grid                            | Image Inspector   |
| - Cover concept      | +----------+ +----------+ +---------+ | Plan              |
| - Chapter 1 image    | | Image    | | Image    | | Image   | | Chapter 1 image  |
| - Diagram            | | Approved | | Draft    | | Reject  | | Prompt           |
|                      | +----------+ +----------+ +---------+ | Provider          |
| Filters              |                                      | [Approve]         |
| [Cover] [Chapter]    |                                      | [Place]           |
| [Approved] [Draft]   |                                      | [Regenerate]      |
+----------------------+--------------------------------------+-------------------+
```

### Page Explanation

Images are managed like a design asset board. Plans live on the left, generated assets in the center, and metadata/actions on the right.

### Buttons

- New Plan: opens image plan modal.
- Generate: starts image generation for selected plan.
- Upload: uploads user-provided image.
- Approve: marks asset approved.
- Place: assigns image to chapter, cover, or marketing asset.
- Regenerate: creates another variation.
- Filters: filter by type/status.

### Popups

- Image plan modal.
- Generation settings sheet.
- Asset preview modal.
- Placement picker.
- Upload dialog.

### Workflow

User creates image plans, generates assets, approves the best options, and places them into the book.

## 8. Formatting Workspace

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Meal Prep Guide / Formatting                  [Preview] [Apply Preset] [Save]  |
+----------------------+--------------------------------------+-------------------+
| Sections             | Book Preview                         | Format Inspector |
| Front Matter         | +----------------------------------+ | Trim Size        |
| Chapters             | | Title Page                       | | [6x9 v]          |
| Back Matter          | | Chapter 1                        | | Headings         |
| Images               | | Body text and image placement    | | [Classic v]      |
|                      | +----------------------------------+ | Image Rules      |
| Checks               |                                      | [Update Preview] |
| - Missing TOC        |                                      |                  |
+----------------------+--------------------------------------+-------------------+
```

### Page Explanation

Formatting gives users a controlled preview of the book structure, style, and export readiness.

### Buttons

- Preview: generates formatting preview.
- Apply Preset: opens style preset picker.
- Save: saves formatting settings.
- Update Preview: refreshes preview using current settings.

### Popups

- Preset picker.
- Preview generation progress.
- Missing section warning.
- Formatting issue detail popover.

### Workflow

User selects format settings, previews layout, resolves issues, and proceeds to validation.

## 9. Validation Workspace

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Meal Prep Guide / Validation                       [Run Checks] [Export Report] |
+----------------------+--------------------------------------+-------------------+
| Check Groups         | Validation Report                    | Issue Inspector  |
| [Metadata]           | Score: 82 / 100                      | Selected Issue   |
| [Manuscript]         |                                      | Missing subtitle |
| [Formatting]         | Warnings                             | Severity: Medium |
| [Images]             | +----------------------------------+ |                  |
| [Cover]              | | Missing subtitle metadata        | | [Fix Now]        |
| [Export]             | | Cover image below target size    | | [Ignore]         |
|                      | +----------------------------------+ | [Add Note]       |
+----------------------+--------------------------------------+-------------------+
```

### Page Explanation

Validation is a checklist and report interface. It should feel objective and actionable, not scary.

### Buttons

- Run Checks: starts validation job.
- Export Report: downloads validation report.
- Fix Now: deep-links to relevant workspace.
- Ignore: marks issue as intentionally ignored.
- Add Note: attaches reviewer note.

### Popups

- Validation settings sheet.
- Issue detail drawer.
- Ignore confirmation.
- Report export dialog.

### Workflow

User runs checks, reviews issues, fixes or acknowledges them, then moves to cover/export.

## 10. Cover Generator

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Meal Prep Guide / Cover                       [Generate Concepts] [Save Cover] |
+----------------------+--------------------------------------+-------------------+
| Cover Brief          | Concept Board                        | Cover Inspector  |
| Genre                | +----------+ +----------+ +---------+ | Title            |
| Audience             | | Concept  | | Concept  | | Concept | | Typography      |
| Mood                 | | 1        | | 2        | | 3       | | Image Prompt    |
| References           | +----------+ +----------+ +---------+ |                  |
|                      |                                      | [Select]         |
|                      | Large Preview                        | [Regenerate]     |
|                      | +----------------------------------+ | [Check KDP]      |
+----------------------+--------------------------------------+-------------------+
```

### Page Explanation

The cover generator blends creative direction and asset selection. The user manages brief, concepts, and final readiness.

### Buttons

- Generate Concepts: creates concept directions or images.
- Save Cover: saves current selected cover state.
- Select: marks concept as selected.
- Regenerate: creates variations.
- Check KDP: runs cover-specific validation.

### Popups

- Cover brief editor.
- Concept generation sheet.
- Large image preview.
- KDP cover check report.

### Workflow

User defines cover brief, generates concepts, selects a direction, validates cover requirements, and saves.

## 11. Translation

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Meal Prep Guide / Translation                  [New Translation] [Review]       |
+----------------------+--------------------------------------+-------------------+
| Languages            | Translation Editor                   | Translation Tools|
| English source       | +----------------+ +---------------+ | Target: Spanish  |
| Spanish draft *      | | Source         | | Translation   | | Glossary         |
| French planned       | | text...        | | text...       | | Tone Guide       |
|                      | +----------------+ +---------------+ |                  |
| Scope                |                                      | [Translate]      |
| [Book] [Chapter]     |                                      | [Approve]        |
+----------------------+--------------------------------------+-------------------+
```

### Page Explanation

Translation uses a side-by-side editor so users can review meaning and tone. It supports book, chapter, metadata, and marketing localization.

### Buttons

- New Translation: opens language and scope setup.
- Review: opens review checklist.
- Translate: starts translation job.
- Approve: marks translation approved.
- Scope tabs: switch between book/chapter/metadata/marketing.

### Popups

- Language picker.
- Glossary editor.
- Translation job progress.
- Approval confirmation.

### Workflow

User selects target language, defines scope, generates translation, reviews side by side, edits, and approves.

## 12. Marketing

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Meal Prep Guide / Marketing                   [Generate Pack] [Copy] [Export]  |
+----------------------+--------------------------------------+-------------------+
| Pack Types           | Marketing Content                    | Pack Inspector   |
| KDP Listing          | Book Description                     | Audience         |
| Social Posts         | +----------------------------------+ | Keywords         |
| Email Launch         | | A practical guide for...         | | Tone            |
| Sales Page           | +----------------------------------+ |                  |
|                      | Keywords                             | [Regenerate]     |
|                      | [meal prep] [healthy eating]        | [Approve]        |
+----------------------+--------------------------------------+-------------------+
```

### Page Explanation

Marketing organizes launch copy into reusable packs. It should feel like a content studio with copyable blocks.

### Buttons

- Generate Pack: starts marketing generation job.
- Copy: copies selected content.
- Export: exports marketing pack.
- Regenerate: regenerates selected copy block.
- Approve: marks pack approved.

### Popups

- Marketing generation sheet.
- Copy success toast.
- Export marketing pack dialog.
- Keyword editor.

### Workflow

User chooses a pack type, generates content, edits/copies assets, approves final pack, and optionally exports.

## 13. Export

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Meal Prep Guide / Export                         [Create Export] [Download]    |
+----------------------+--------------------------------------+-------------------+
| Formats              | Export Checklist                     | Export Settings  |
| [DOCX]               | + Manuscript approved                | Format: EPUB     |
| [PDF]                | + Images placed                      | Validation: Pass |
| [EPUB]               | ! Cover warning                      | Include Images   |
|                      |                                      | [Run Validation] |
| Export History       | Latest Exports                       | [Create Export]  |
| - EPUB today         | +----------------------------------+ |                  |
| - PDF yesterday      | | EPUB completed                   | |                  |
+----------------------+--------------------------------------+-------------------+
```

### Page Explanation

Export is the final production checkpoint. It should make readiness clear before files are generated.

### Buttons

- Create Export: starts export job.
- Download: downloads completed export.
- Format buttons: select output format.
- Run Validation: starts validation before export.
- Export history item: opens export details.

### Popups

- Export settings dialog.
- Validation warning dialog.
- Job progress popover.
- Download link dialog.

### Workflow

User selects format, reviews checklist, resolves blocking issues, starts export, then downloads file.

## 14. Settings

### Wireframe

```text
+--------------------------------------------------------------------------------+
| Settings                                                                        |
+----------------------+---------------------------------------------------------+
| Profile              | Profile                                                 |
| Security             | Name                                                     |
| Providers            | +-----------------------------------------------------+ |
| Writing Defaults     | Email                                                    |
| Export Defaults      | +-----------------------------------------------------+ |
| Notifications        |                                                         |
| API Keys             | [Save Changes]                                          |
| Billing future       |                                                         |
+----------------------+---------------------------------------------------------+
```

### Page Explanation

Settings are organized by scope. The layout is simple, predictable, and administrative.

### Buttons

- Save Changes: saves the active settings section.
- Add Provider Key: future secret configuration action.
- Create API Key: opens API key dialog.
- Revoke API Key: confirms key revocation.
- Test Provider: future provider health check.

### Popups

- API key creation dialog.
- API key created one-time secret dialog.
- Revoke confirmation.
- Unsaved changes dialog.

### Workflow

User configures profile, security, provider preferences, writing defaults, export defaults, notifications, and future billing.

## Responsive Design Rules

### Desktop

- Three-column workspace layout is preferred.
- Sidebar can collapse to icons.
- Inspector remains visible when screen width allows.
- Keyboard shortcuts and command palette are primary accelerators.

### Tablet

- Primary sidebar becomes collapsible drawer.
- Inspector becomes slide-over panel.
- Main editor remains central.
- Toolbars wrap into grouped controls.

### Mobile

- One primary content column.
- Sidebars become drawers.
- Inspector becomes bottom sheet.
- Long toolbars become overflow menus.
- Editing comparisons stack vertically.
- Asset grids become two-column or single-column lists.

## Interaction Model

### Save Behavior

- Manual save button for major content changes.
- Autosave may be introduced for drafts and settings after conflict handling is designed.
- Unsaved changes warning appears when navigating away from dirty editor state.

### AI Job Behavior

- Generation buttons start jobs instead of blocking the page.
- Job progress appears in popovers, side panels, or notifications.
- Completed jobs create history events.
- Failed jobs show clear retry actions.

### Review Behavior

- User must approve AI-generated edits before applying them to final manuscript content.
- User can reject or regenerate suggestions.
- Validation issues can be fixed, ignored, or annotated.

### Navigation Behavior

- Users should always know:
  - Current project
  - Current workflow step
  - Current chapter or asset
  - Current status
  - Next recommended action

## Button System

### Primary Buttons

Used for the main action on the page:
- New Project
- Generate
- Save
- Run Validation
- Create Export
- Approve

### Secondary Buttons

Used for supportive actions:
- Preview
- Copy
- Import
- Upload
- Export Report
- Apply Preset

### Ghost Buttons

Used for low-emphasis actions:
- Cancel
- Close
- More
- Ignore

### Destructive Buttons

Used for irreversible or risky actions:
- Delete
- Revoke
- Discard
- Cancel Job

Destructive actions should require confirmation unless they are easily reversible.

## Popup System

### Modal

Used when the user must complete or cancel a focused task:
- Create Project
- Delete confirmation
- API key creation

### Sheet

Used for contextual creation or generation:
- AI generation
- Export settings
- Validation settings
- Translation setup

### Popover

Used for small contextual menus:
- Notifications
- Account menu
- Sort menu
- More actions

### Drawer

Used for detail views:
- Job logs
- Issue details
- Asset metadata
- History event details

### Toast

Used for lightweight feedback:
- Saved
- Copied
- Job queued
- Export ready

## End-To-End Workflow

```text
Login
  -> Dashboard
  -> Project List
  -> Create Project
  -> Project Detail
  -> Writing Workspace
  -> Editing Workspace
  -> Image Workspace
  -> Formatting Workspace
  -> Validation Workspace
  -> Cover Generator
  -> Marketing
  -> Translation
  -> Export
```

Workflow principles:
- Each workspace has a clear next action.
- Each AI action returns reviewable output, not automatic final content.
- Each production step creates traceable history.
- Export is gated by visible readiness checks.

## Visual Design Principles

- Use quiet neutral backgrounds.
- Use cards only for contained objects like projects, assets, and summaries.
- Keep page sections unframed and spacious.
- Use 8px border radius.
- Use soft shadows sparingly.
- Use high-contrast typography.
- Avoid decorative gradients and visual noise.
- Let content, structure, and workflow status carry the interface.

## Accessibility Principles

- All controls must be keyboard reachable.
- All icon-only buttons must have accessible labels and tooltips.
- Focus states must be visible.
- Color cannot be the only status indicator.
- Modals and sheets must trap focus.
- Forms must have labels, helper text, and field-level errors.

## Design Risks To Avoid

- Making the app feel like a marketing landing page instead of a production workspace.
- Hiding core actions inside too many menus.
- Allowing AI output to overwrite user content without approval.
- Making validation feel punitive instead of helpful.
- Overloading the dashboard with analytics before workflow clarity is solved.
- Treating mobile as an afterthought.
