# SmartRenamer Redesign: OpenTUI + Persistent Python Backend

## Architecture

```
┌──────────────────────────────┐
│  OpenTUI (Bun / TypeScript)  │  ← UI state, rendering, user input
│                              │
│  components/                 │
│   App.tsx                    │
│   FileGrid.tsx               │
│   PreviewPanel.tsx           │
│   ImagePreview.tsx           │
│   Controls.tsx               │
│   StatusBar.tsx              │
│                              │
│  rpc/                        │
│   client.ts                  │  ← JSON-RPC 2.0 over stdio
│   types.ts                   │
│                              │
│  state/                      │
│   store.ts                   │  ← user selections, UI toggles
└──────────────┬───────────────┘
               │ JSON-RPC over stdin/stdout
               ▼
┌──────────────────────────────┐
│  Python Backend (Persistent) │  ← all AI, logic, data
│                              │
│  backend/                    │
│   __main__.py                │
│   server.py                  │  ← RPC dispatcher
│   session.py                 │  ← session state machine
│   models.py                  │  ← RenamePlan, Session, states
│   planner.py                 │
│   validator.py               │
│   executor.py                │
│   brain/                     │
│    metadata_extractor.py     │
│    classifier.py             │
│    vision_router.py          │
│    vision_decision.py        │
│    template_engine.py        │
│   cache/                     │
│    metadata_cache.py         │
│    classification_cache.py   │
│    vision_cache.py           │
└──────────────────────────────┘
```

## State Ownership

| Backend owns | TUI owns |
|---|---|
| AI decisions | User selection state |
| Rename plans | UI toggles |
| Validation results | Editing overrides |
| Execution logs | Cursor position |
| File metadata | Approval state |

## Folder Structure

```
smart_renamer/
├── backend/                        # Python package
│   ├── __init__.py
│   ├── __main__.py                 # Entry: python -m smart_renamer.backend
│   ├── server.py                   # JSON-RPC stdin/stdout loop
│   ├── session.py                  # SessionManager + Session
│   ├── models.py                   # RenamePlan, SessionState, etc.
│   ├── planner.py                  # Orchestrate plan creation
│   ├── validator.py                # Validation logic
│   ├── executor.py                 # Rename execution + undo
│   ├── brain/
│   │   ├── __init__.py
│   │   ├── metadata_extractor.py   # Pillow-based EXIF/dimensions
│   │   ├── classifier.py           # Heuristic type detection
│   │   ├── vision_router.py        # Gemini API calls + caching
│   │   ├── vision_decision.py      # NEW: decides WHEN to call vision
│   │   └── template_engine.py      # Name template rendering
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── metadata_cache.py       # NEW: file hash → metadata
│   │   ├── classification_cache.py # NEW: file hash → classifier result
│   │   └── vision_cache.py         # existing: file hash → Gemini tags
├── tui/                            # Bun/TypeScript project
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── index.ts
│   │   ├── components/
│   │   │   ├── App.tsx
│   │   │   ├── FileGrid.tsx
│   │   │   ├── PreviewPanel.tsx
│   │   │   ├── ImagePreview.tsx
│   │   │   ├── Controls.tsx
│   │   │   └── StatusBar.tsx
│   │   ├── rpc/
│   │   │   ├── client.ts
│   │   │   └── types.ts
│   │   └── state/
│   │       └── store.ts
├── smart_renamer.toml
└── pyproject.toml
```

## JSON-RPC Protocol

JSON-RPC 2.0 over stdin/stdout. Line-delimited JSON. One request → one response.

### Request

```json
{"id": "1", "method": "method.name", "params": {...}}
```

### Response (ok)

```json
{"id": "1", "status": "ok", "data": {...}}
```

### Response (error)

```json
{"id": "1", "status": "error", "data": {"code": "ERROR_CODE", "message": "human message"}}
```

### Methods

#### Session

| Method | Params | Returns |
|---|---|---|
| `session.create` | `{directory, config_path?}` | `{session_id, state, file_count}` |
| `session.destroy` | `{session_id}` | `{}` |
| `session.status` | `{session_id}` | `{state, file_count, enriched_count}` |

#### Planning

| Method | Params | Returns |
|---|---|---|
| `plan` | `{session_id}` | `{plans: [RenamePlan]}` |
| `enrich` | `{session_id, file_ids?}` | `{plans: [RenamePlan], enriched_count}` |

#### Validation & Execution

| Method | Params | Returns |
|---|---|---|
| `validate` | `{session_id, approvals}` | `{valid, conflicts, report}` |
| `execute` | `{session_id}` | `{results}` |

#### Preview

| Method | Params | Returns |
|---|---|---|
| `preview` | `{session_id, file_id, format?, width?, height?}` | `{ascii, dimensions, file_size}` |

#### Undo

| Method | Params | Returns |
|---|---|---|
| `undo` | `{session_id}` | `{undone_count}` |

### RenamePlan Schema

```json
{
  "file_id": "abc123def456",
  "original_path": "/dir/screenshot_01.jpg",
  "proposed_name": "roronoa_zoro_screenshot_01.jpg",
  "tags": ["roronoa_zoro", "anime", "screenshot"],
  "confidence": 0.85,
  "state": "PLANNED",
  "reasoning": "Vision: identified character roronoa zoro from One Piece. Classifier: screenshot based on 1920x1080 resolution."
}
```

### Error Codes

| Code | Meaning |
|---|---|
| `SESSION_NOT_FOUND` | Invalid session_id |
| `INVALID_STATE` | Operation not allowed in current state |
| `VALIDATION_FAILED` | Plans failed validation |
| `EXECUTION_FAILED` | Rename failed |
| `INVALID_PARAMS` | Missing or invalid parameters |

## Session State Machine

```
CREATED ──load──► LOADED ──plan──► PLANNED ──enrich──► ENRICHED
                  ▲                  │   ▲                │
                  │                  │   │                │
                  └──────────────────┘   └────────────────┘
                                      │
                                      ▼
                                 VALIDATED ──approve──► APPROVED ──execute──► EXECUTED
                                      ▲                                         │
                                      │                                         │
                                      └────────────── undo ────────────────────┘
```

- `plan` transitions LOADED → PLANNED
- `enrich` transitions PLANNED → ENRICHED (can be called multiple times)
- `validate` transitions PLANNED/ENRICHED → VALIDATED
- `approve` transitions VALIDATED → APPROVED
- `execute` transitions APPROVED → EXECUTED
- `undo` transitions EXECUTED → APPROVED (restores files)

## Vision Decision Engine

Logic in `brain/vision_decision.py`:

```
should_enrich(metadata, classification) -> bool

1. If confidence >= 0.7 AND type in {wallpaper, photo, screenshot, meme} → skip
2. If confidence < 0.7 → enrich
3. If type == "unknown" → enrich
4. If metadata has no EXIF AND type != "wallpaper" → enrich
5. Otherwise → skip
```

## Caching System

### Metadata Cache (`cache/metadata_cache.py`)

- Key: SHA256 hash of file's first 8KB
- Value: serialized `FileMetadata`
- TTL: session lifetime (invalidated on new session for same dir)

### Classification Cache (`cache/classification_cache.py`)

- Key: file hash
- Value: `(tags, confidence)` tuple
- TTL: session lifetime

### Vision Cache (`cache/vision_cache.py`)

- Key: file hash
- Value: `[tags]`
- Persistent: written to `~/.smart_renamer/vision_cache/` as JSON files
- Survives across sessions

### Directory Fingerprinting

- On `session.create`, compute a fingerprint: `(mtime_sum, file_count, total_size)` of the directory
- On subsequent calls, if fingerprint matches, reuse cached plan
- If fingerprint changed, invalidate caches

## OpenTUI Component Tree

```
App
├── Header                       — title, session state, file count, [AI] badge
├── Main (flex row)
│   ├── FileGrid (flex: 2)       — scrollable list of files
│   │   ├── ColumnHeaders
│   │   └── FileRow[]            — ✓, original name, proposed name, conf, tags
│   └── PreviewPanel (width: 35) — selected file details
│       ├── ImagePreview         — ASCII art from backend
│       └── FileDetails          — metadata, tags, reasoning
├── Controls                     — action buttons
│   ├── Toggle
│   ├── Approve All
│   └── Execute
├── StatusBar                    — status message text
└── Footer                       — keyboard shortcuts
```

### Image Preview Options

Primary: **ASCII art** generated by Python backend (Pillow → grayscale → 10-level ASCII ramp). TUI renders via `<text>`.

Secondary: **Metadata card** — dimensions, camera, date, file size, type. Always shown regardless of preview format.

Fallback: If image is unreadable, show "No preview available" + metadata.

## Data Flow

### Startup
1. Bun spawns `python -m smart_renamer.backend` as subprocess with stdio pipes
2. TUI sends `session.create` with target directory
3. Backend scans directory, computes fingerprint, caches metadata, returns file count
4. TUI sends `plan` — backend runs heuristic classification, returns plans
5. Backend runs VisionDecisionEngine, enriches qualifying files
6. TUI renders file grid with proposed names

### User Interaction
1. User navigates file grid (up/down) — TUI updates cursor
2. Space toggles approval — TUI sends `validate` with updated approvals
3. User edits a name inline — TUI updates local store, sends on next `validate`
4. User presses Execute — TUI sends `execute`

### Execute Flow
1. TUI sends `execute` with session_id
2. Backend validates plans are in APPROVED state
3. Backend executes renames, writes undo log
4. Backend transitions session to EXECUTED
5. TUI refreshes to show results

### Undo
1. TUI sends `undo` with session_id
2. Backend reads undo log, reverses each rename
3. Backend transitions session back to APPROVED
4. TUI refreshes

## Keyboard Bindings

| Key | Action |
|---|---|
| `j` / `↓` | Move cursor down |
| `k` / `↑` | Move cursor up |
| `Space` | Toggle approval on selected file |
| `a` | Approve all |
| `r` | Reject all |
| `e` | Execute approved renames |
| `u` | Undo last execution |
| `q` / `Esc` | Quit |
| `Enter` | Show full preview / toggle panel focus |

## State Ownership Rules

### Backend owns:
- All AI decisions (classification, vision, confidence scores)
- Rename plans and proposed names
- Validation results and conflict detection
- Execution and undo logs
- File metadata and caching

### TUI owns:
- User selection state (cursor position)
- Approval toggles per file
- Name editing overrides (user-customized names)
- UI rendering decisions

## Error Handling

- Backend writes errors to stderr as plain text (not JSON)
- Backend responds to RPC with `status: "error"` and structured error data
- TUI catches subprocess stderr and displays in status bar
- On backend crash, TUI detects process exit, shows "Backend crashed" error, offers restart
- Backend traps SIGTERM/SIGINT for graceful shutdown
