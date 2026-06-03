# SmartRenamer

AI-powered bulk file renamer with a terminal UI. Uses metadata extraction and heuristic classification to suggest intelligent filenames. Optionally uses Google Gemini Vision API for semantic image tagging.

## Quick Start

```bash
# Install
pip install smart-renamer

# CLI mode (dry-run by default)
python -m smart_renamer.main /path/to/images

# TUI mode
python -m smart_renamer.main /path/to/images --tui
```

## Features

- **Metadata extraction** — reads EXIF, dimensions, dates from images/media files
- **Heuristic classification** — automatically detects wallpapers, screenshots, photos, memes, videos, audio
- **Optional AI vision** — uses free Google Gemini API for semantic tagging (e.g., "sunset", "mountain", "anime character")
- **Safety-first** — dry-run by default, conflict detection, undo support, no overwrites
- **Terminal UI** — full-screen interactive TUI with file grid, preview panel, and approval controls

## Configuration

Create `smart_renamer.toml` in your project root or `~/.config/smart_renamer/config.toml`:

```toml
[general]
template = "{tags}_{index}"
dry_run = true
recursive = false

[gemini]
enabled = false
api_key = ""
confidence_threshold = 0.6
```

Set `GEMINI_API_KEY` environment variable or add it to the config to enable AI vision.

## Safety

- Dry-run by default — nothing is renamed without explicit approval
- Undo support via `~/.smart_renamer/undo/<session>.json`
- Conflict detection prevents overwrites
- Validator checks for invalid filenames, reserved names, and path length limits

## Project Structure

```
smart_renamer/
  main.py           — CLI entry point
  config.py         — TOML configuration
  models/           — Pydantic data models
  brain/            — MetadataExtractor, Classifier, TemplateEngine, Planner, VisionRouter
  validator/        — Conflict and safety validation
  executor/         — Rename execution with undo logging
  tui/              — Textual terminal UI
skills/             — Heuristic rules (SKILL.md files)
```

## License

MIT
