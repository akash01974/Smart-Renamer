# SmartRenamer — AI-Powered Bulk File Renamer

**Date:** 2026-06-04
**Status:** Approved Design

## Overview

SmartRenamer is a terminal-based (TUI) tool that intelligently renames image/media files using metadata extraction, heuristic classification, and optionally Google Gemini Vision API for semantic analysis. It provides a safe, reversible, user-approved rename workflow.

## Architecture

The system is composed of 9 components that work together in a pipeline:

| Component | Role |
|-----------|------|
| TUI (Textual) | File grid, previews, approval controls |
| Planner (Brain) | Generates structured RenamePlan from files |
| Validator | Conflict detection, OS-safety checks |
| Executor | Applies renames, logs undo operations |
| Metadata Extractor | EXIF, timestamps, dimensions, file size |
| Classifier | Heuristic tagging: photo/screenshot/wallpaper/anime/etc. |
| Vision Router (optional) | Gemini API for low-confidence or semantic tagging |
| Template Engine | Converts tags + metadata into filenames |
| Skills System | SKILL.md files loaded dynamically by the Planner |

### Layer Responsibilities

| Layer | Input | Output | Side Effects |
|-------|-------|--------|-------------|
| TUI | user commands | approval signals | rendering only |
| Planner | file list | `list[RenamePlan]` | none |
| Validator | `list[RenamePlan]` | `ValidationReport` | none |
| Executor | approved plans | `list[ExecutionResult]` | filesystem renames + undo log |
| Metadata Extractor | file path | `FileMetadata` | reads file (no writes) |
| Classifier | `FileMetadata` | `list[Tag]` | none |
| Vision Router | file path | `list[Tag]` | HTTP call to Gemini |
| Template Engine | tags + config | filename string | none |

## Data Models

All models use Pydantic for validation.

### RenamePlan
- `file_id: str` — unique hash of original path
- `old_path: Path`
- `proposed_new_name: str` — filename only (not full path)
- `confidence: float` — 0.0 to 1.0
- `tags: list[str]` — semantic tags from classifier/vision
- `metadata_summary: str` — human-readable summary of why this name was chosen

### ExecutionResult
- `file_id: str`
- `success: bool`
- `old_path: Path`
- `new_path: Path | None`
- `error: str | None`

### ValidationReport
- `conflicts: list[Conflict]` — duplicate proposed names, overwrite risks
- `warnings: list[str]` — OS-path-length, invalid chars, etc.
- `suggestions: list[str]` — alternative names for conflicted files

### FileMetadata
- `path: Path`
- `size_bytes: int`
- `dimensions: tuple[int, int] | None`
- `file_type: str` — extension
- `created_at: datetime | None`
- `modified_at: datetime | None`
- `exif_camera: str | None`
- `exif_date_taken: datetime | None`
- `exif_gps: tuple[float, float] | None`
- `is_animated: bool` — for GIF/WebP

## Workflow

1. User launches `smart-renamer <directory>` from terminal
2. TUI scans directory, shows file grid
3. User triggers "Analyze" — Planner runs:
   a. Metadata Extractor reads each file
   b. Classifier assigns heuristic tags
   c. If Gemini enabled + confidence < threshold, Vision Router enriches tags
   d. Template Engine generates proposed names
   e. Validator checks for conflicts
4. TUI shows dry-run preview: old name → proposed name, confidence, tags
5. User toggles approval per-file or batch
6. User switches from "Dry Run" to "Execute" mode
7. Executor applies approved renames
8. Undo log written to `~/.smart_renamer/undo/<session>.json`

## Safety

- **Never rename without approval** — rename is a two-step: preview → confirm
- **Dry run is default** — execute mode must be explicitly enabled
- **No overwrites** — Validator detects same proposed name for different files, appends index
- **OS-safe filenames** — strip/replace invalid chars, enforce max length
- **Undo log** — JSON file per session with old→new path mapping; dedicated `undo` command restores
- **AI output is untrusted** — Vision Router output is treated as suggestions; Validator strips anything that produces invalid filenames

## Skills System

Each skill is a `SKILL.md` file under `skills/<name>/` with structured rules.

### image_classification/SKILL.md
- Heuristics to classify image type: dimensions suggestive of wallpaper? EXIF present → photo? Uniform histogram → screenshot?
- Multi-label: `wallpaper`, `photo`, `screenshot`, `meme`, `anime`, `document`

### filename_generation/SKILL.md
- Templates like `{tags}_{date}_{index}`, configurable via `smart_renamer.toml`
- Default pattern: `{tags}_{index}`

### metadata_analysis/SKILL.md
- Rules for extracting best date (EXIF > filesystem creation > modified)
- Rules for determining if GPS coordinates are valid

### safety_validation/SKILL.md
- Invalid character rules per OS
- Path length limits
- Reserved names

## UI Design (Textual)

### Layout

```
┌────────────────────────────────────────────────┐
│ SmartRenamer — /home/user/wallpapers     [ESC] │
├─────────────────────────┬──────────────────────┤
│  File Grid              │  Preview Panel       │
│                         │                      │
│  [✓] 1.jpg → sunset_01 │  Old: IMG_001.jpg    │
│  [✓] 2.jpg → naruto_02 │  New: sunset_01.jpg  │
│  [✗] 3.jpg → city_03   │  Tags: sunset,       │
│  [✓] 4.jpg → beach_04  │        warm, beach    │
│  [ ] 5.jpg → dragon_05 │  Confidence: 0.92     │
│                         │  Camera: Canon EOS    │
│                         │  Date: 2024-06-01     │
│                         │                      │
│                         │  [Approve] [Reject]  │
├─────────────────────────┴──────────────────────┤
│ [Analyze] [Select All] [Dry Run] [Execute]     │
│ Status: 4/10 approved · Dry Run mode           │
└────────────────────────────────────────────────┘
```

### Key Bindings
- `j/k` — navigate files
- `Space` — toggle approval for selected file
- `a` — approve all
- `r` — reject all
- `e` — edit proposed name inline
- `Enter` — show preview detail
- `Tab` — switch between file grid and preview panel
- `Esc` — quit

### States
- **Loading** — scanning directory, analyzing files
- **Review** — showing dry-run preview, awaiting user input
- **Executing** — applying renames, progress bar
- **Done** — summary of results
- **Error** — recoverable error with message

## Gemini Integration

- Optional, disabled by default
- Enabled by setting `GEMINI_API_KEY` env var or in config
- Model: `gemini-2.5-flash` (free tier)
- Prompt: "Describe this image in 3-5 comma-separated keywords focusing on the subject, setting, and theme. Return only keywords."
- Only called when classifier confidence < 0.6
- Rate-limited to 10 RPM (free tier respect)
- Results cached per image hash to avoid re-calling on re-analysis

## Configuration

File: `~/.config/smart_renamer/config.toml` or `./smart_renamer.toml`

```toml
[general]
template = "{tags}_{index}"
dry_run = true
recursive = false

[gemini]
enabled = false
api_key = ""  # or set GEMINI_API_KEY env var
confidence_threshold = 0.6

[classifier]
enable_heuristics = true
enable_vision = false  # requires gemini enabled
```

## Testing Strategy

- **Unit tests** per layer: MetadataExtractor, Classifier, TemplateEngine, Validator
- **Integration tests**: Planner → Validator → Executor pipeline with temp files
- **Snapshot tests**: TUI widget rendering with Textual's testing utilities
- **Safety tests**: edge cases like 500 files with same proposed name, unicode chars, max path length

## Future Considerations (not in scope)

- Batch rename with regex patterns
- Watch mode (auto-rename on file drop)
- More AI backends (Ollama, Claude)
- Image duplicate detection via perceptual hashing
