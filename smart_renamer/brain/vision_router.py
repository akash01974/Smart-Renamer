import base64
import hashlib
import json
import os
from pathlib import Path
import httpx


class VisionRouter:
    def __init__(self, api_key: str | None = None, cache_dir: Path | None = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.cache_dir = cache_dir or Path.home() / ".smart_renamer" / "vision_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def enrich(self, filepath: Path) -> list[str]:
        if not self.is_available():
            return []
        if filepath.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            return []
        cache_key = self._cache_key(filepath)
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        tags = self._call_gemini(filepath, cache_key)
        return tags

    def _cache_key(self, filepath: Path) -> str:
        hasher = hashlib.md5()
        with open(filepath, "rb") as f:
            hasher.update(f.read(8192))
        return hasher.hexdigest()

    def _load_cache(self, key: str) -> list[str] | None:
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def _save_cache(self, key: str, tags: list[str]) -> None:
        cache_file = self.cache_dir / f"{key}.json"
        try:
            cache_file.write_text(json.dumps(tags))
        except OSError:
            pass

    def _call_gemini(self, filepath: Path, cache_key: str) -> list[str]:
        try:
            with open(filepath, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()
            mime = self._mime_type(filepath)
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Describe this image in 3-5 comma-separated keywords focusing on the subject, setting, and theme. Return only keywords."},
                        {"inline_data": {"mime_type": mime, "data": img_data}}
                    ]
                }]
            }
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
            resp = httpx.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            tags = [t.strip().lower().replace(" ", "_") for t in text.split(",") if t.strip()]
            if tags:
                self._save_cache(cache_key, tags)
            return tags
        except Exception:
            return []

    def _mime_type(self, path: Path) -> str:
        mapping = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
        return mapping.get(path.suffix.lower(), "image/jpeg")
