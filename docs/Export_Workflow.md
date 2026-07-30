# Export Workflow

## Planned Formats

- DOCX
- PDF
- EPUB

## Planned Flow

```text
Project content -> export service -> renderer -> validation -> downloadable artifact
```

## Design Rules

- Exports should run as background jobs.
- Export artifacts should be versioned.
- Formatting settings should be explicit and reproducible.

## Stage 1 Boundary

No export engine is implemented in this stage.
