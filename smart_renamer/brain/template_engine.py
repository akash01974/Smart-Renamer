import re
from pathlib import Path


class TemplateEngine:
    VALID_KEYS = {"tags", "index", "date", "ext", "summary"}

    def __init__(self, template: str = "{tags}_{index}"):
        self.template = template
        self._validate_template(template)

    def _validate_template(self, template: str) -> None:
        found = re.findall(r"\{(\w+)\}", template)
        for key in found:
            if key not in self.VALID_KEYS:
                raise ValueError(f"Unknown template key: {{{key}}}. Valid keys: {', '.join(sorted(self.VALID_KEYS))}")

    def generate(self, tags: list[str], index: int, ext: str, metadata_summary: str = "", date: str = "") -> str:
        ext_clean = ext.lstrip(".")
        context = {
            "tags": "_".join(tags) if tags else "untagged",
            "index": str(index).zfill(2),
            "date": date,
            "ext": ext_clean,
            "summary": self._slugify(metadata_summary[:30]),
        }
        result = self.template
        for key, value in context.items():
            result = result.replace(f"{{{key}}}", value)
        result = self._sanitize(result)
        return f"{result}.{ext_clean}".lower()

    def _sanitize(self, name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        name = re.sub(r'\s+', "_", name)
        name = name.strip("._")
        max_len = 200
        name = name[:max_len]
        return name if name else "unnamed"

    def _slugify(self, text: str) -> str:
        text = re.sub(r'[^a-zA-Z0-9\s_-]', "", text)
        text = re.sub(r'\s+', "_", text)
        return text.strip("_")
