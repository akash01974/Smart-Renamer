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
            Path.home() / ".config" / "smart_renamer" / "config.toml",
            Path.cwd() / "smart_renamer.toml",
        ]
        if path:
            paths_to_try.append(path)
        for p in paths_to_try:
            if p and p.exists():
                self._parse(p)

    def _parse(self, path: Path) -> None:
        data = tomllib.loads(path.read_text())
        general = data.get("general", {})
        self.template = general.get("template", self.template)
        self.dry_run = general.get("dry_run", self.dry_run)
        self.recursive = general.get("recursive", self.recursive)
        gemini = data.get("gemini", {})
        if gemini.get("enabled") is not None:
            self.gemini_enabled = gemini["enabled"]
        if gemini.get("confidence_threshold") is not None:
            self.confidence_threshold = gemini["confidence_threshold"]
        if gemini.get("api_key"):
            self.gemini_api_key = gemini["api_key"]
        if not self.gemini_api_key:
            self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
