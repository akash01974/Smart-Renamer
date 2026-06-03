import os
import tomllib
from pathlib import Path


class Config:
    def __init__(self, path: Path | None = None):
        self.template: str = "{tags}_{index}"
        self.dry_run: bool = True
        self.recursive: bool = False
        self.gemini_enabled: bool = False
        self.gemini_api_key: str = ""
        self.confidence_threshold: float = 0.6
        self._load(path)

    def _load(self, path: Path | None) -> None:
        paths_to_try = [
            path,
            Path.cwd() / "smart_renamer.toml",
            Path.home() / ".config" / "smart_renamer" / "config.toml",
        ]
        for p in paths_to_try:
            if p and p.exists():
                self._parse(p)
                return

    def _parse(self, path: Path) -> None:
        data = tomllib.loads(path.read_text())
        general = data.get("general", {})
        self.template = general.get("template", self.template)
        self.dry_run = general.get("dry_run", self.dry_run)
        self.recursive = general.get("recursive", self.recursive)
        gemini = data.get("gemini", {})
        self.gemini_enabled = gemini.get("enabled", False)
        self.gemini_api_key = gemini.get("api_key", "") or os.environ.get("GEMINI_API_KEY", "")
        self.confidence_threshold = gemini.get("confidence_threshold", self.confidence_threshold)
