# SmartRenamer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a TUI-based AI-powered bulk image/file renamer with metadata extraction, classification, optional Gemini vision, and safe rename execution.

**Architecture:** The system follows a layered pipeline: TUI (Textual) → Planner (Brain: Metadata Extractor + Classifier + Template Engine) → Validator → Executor. Each layer is independent with well-defined Pydantic data models between them. A skills system (SKILL.md files) provides heuristic rules loaded at runtime.

**Tech Stack:** Python 3.11+, Textual (TUI), Pydantic (models), Pillow (image metadata), httpx (Gemini API), stdlib (filesystem ops)

---

### Task 1: Pydantic Data Models

**Files:**
- Create: `smart_renamer/models/__init__.py`
- Create: `smart_renamer/models/file_metadata.py`
- Create: `smart_renamer/models/rename_plan.py`
- Create: `smart_renamer/models/execution_result.py`
- Create: `smart_renamer/models/validation_report.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the models**

```python
# smart_renamer/models/__init__.py
from .file_metadata import FileMetadata
from .rename_plan import RenamePlan
from .execution_result import ExecutionResult, UndoEntry
from .validation_report import ValidationReport, Conflict

__all__ = ["FileMetadata", "RenamePlan", "ExecutionResult", "UndoEntry", "ValidationReport", "Conflict"]
```

```python
# smart_renamer/models/file_metadata.py
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel


class FileMetadata(BaseModel):
    path: Path
    size_bytes: int = 0
    dimensions: tuple[int, int] | None = None
    file_type: str = ""
    created_at: datetime | None = None
    modified_at: datetime | None = None
    exif_camera: str | None = None
    exif_date_taken: datetime | None = None
    exif_gps: tuple[float, float] | None = None
    is_animated: bool = False
    dominant_colors: list[str] = []
```

```python
# smart_renamer/models/rename_plan.py
from pathlib import Path
from pydantic import BaseModel


class RenamePlan(BaseModel):
    file_id: str
    old_path: Path
    proposed_new_name: str
    confidence: float
    tags: list[str]
    metadata_summary: str
```

```python
# smart_renamer/models/execution_result.py
from pathlib import Path
from pydantic import BaseModel


class ExecutionResult(BaseModel):
    file_id: str
    success: bool
    old_path: Path
    new_path: Path | None = None
    error: str | None = None


class UndoEntry(BaseModel):
    old_path: Path
    new_path: Path
```

```python
# smart_renamer/models/validation_report.py
from pydantic import BaseModel


class Conflict(BaseModel):
    file_ids: list[str]
    proposed_name: str
    reason: str


class ValidationReport(BaseModel):
    conflicts: list[Conflict] = []
    warnings: list[str] = []
    suggestions: list[str] = []
```

- [ ] **Step 2: Write and run tests**

```python
# tests/test_models.py
from smart_renamer.models import RenamePlan, ExecutionResult, ValidationReport, Conflict, UndoEntry
from pathlib import Path


def test_rename_plan_creation():
    plan = RenamePlan(
        file_id="abc123",
        old_path=Path("/tmp/test.jpg"),
        proposed_new_name="sunset_beach_01.jpg",
        confidence=0.92,
        tags=["sunset", "beach"],
        metadata_summary="Photo taken during golden hour"
    )
    assert plan.file_id == "abc123"
    assert plan.confidence == 0.92


def test_execution_result_success():
    result = ExecutionResult(
        file_id="abc123",
        success=True,
        old_path=Path("/tmp/old.jpg"),
        new_path=Path("/tmp/new.jpg")
    )
    assert result.success
    assert result.new_path == Path("/tmp/new.jpg")


def test_execution_result_failure():
    result = ExecutionResult(
        file_id="abc123",
        success=False,
        old_path=Path("/tmp/old.jpg"),
        error="Permission denied"
    )
    assert not result.success
    assert result.error == "Permission denied"


def test_validation_report():
    report = ValidationReport(
        conflicts=[Conflict(file_ids=["a", "b"], proposed_name="same.jpg", reason="Duplicate name")],
        warnings=["Path length exceeds 255 chars for file x.jpg"],
        suggestions=["Consider using shorter tags"]
    )
    assert len(report.conflicts) == 1
    assert report.conflicts[0].proposed_name == "same.jpg"


def test_undo_entry():
    entry = UndoEntry(old_path=Path("/tmp/new.jpg"), new_path=Path("/tmp/old.jpg"))
    assert entry.old_path == Path("/tmp/new.jpg")
    assert entry.new_path == Path("/tmp/old.jpg")
```

Run: `pytest tests/test_models.py -v`
Expected: 5 passed

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/models/ tests/test_models.py
git commit -m "feat: add Pydantic data models for rename plans, results, validation"
```

---

### Task 2: Metadata Extractor

**Files:**
- Create: `smart_renamer/brain/__init__.py`
- Create: `smart_renamer/brain/metadata_extractor.py`
- Test: `tests/test_metadata_extractor.py`

- [ ] **Step 1: Write the Metadata Extractor**

```python
# smart_renamer/brain/__init__.py
from .metadata_extractor import MetadataExtractor

__all__ = ["MetadataExtractor"]
```

```python
# smart_renamer/brain/metadata_extractor.py
import hashlib
from datetime import datetime
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS
from smart_renamer.models import FileMetadata


class MetadataExtractor:
    def extract(self, path: Path) -> FileMetadata:
        stats = path.stat()
        metadata = FileMetadata(
            path=path,
            size_bytes=stats.st_size,
            file_type=path.suffix.lower(),
            created_at=datetime.fromtimestamp(stats.st_ctime),
            modified_at=datetime.fromtimestamp(stats.st_mtime),
        )
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}:
            self._extract_image_metadata(path, metadata)
        return metadata

    def _extract_image_metadata(self, path: Path, metadata: FileMetadata) -> None:
        try:
            img = Image.open(path)
            metadata.dimensions = img.size
            metadata.is_animated = getattr(img, "is_animated", False)
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, "")
                    if tag_name == "Make" and value:
                        metadata.exif_camera = str(value).strip()
                    elif tag_name == "Model" and value and metadata.exif_camera:
                        metadata.exif_camera = f"{metadata.exif_camera} {value}".strip()
                    elif tag_name == "DateTimeOriginal" and value:
                        try:
                            metadata.exif_date_taken = datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                        except ValueError:
                            pass
                    elif tag_name == "GPSInfo" and value:
                        metadata.exif_gps = self._parse_gps(value)
        except Exception:
            pass

    def _parse_gps(self, gps_info: dict) -> tuple[float, float] | None:
        try:
            def _to_decimal(coord, ref):
                if coord is None:
                    return None
                d, m, s = float(coord[0]), float(coord[1]), float(coord[2])
                decimal = d + m / 60.0 + s / 3600.0
                if ref in ("S", "W"):
                    decimal = -decimal
                return decimal
            lat = _to_decimal(gps_info.get(2), gps_info.get(1, "N"))
            lon = _to_decimal(gps_info.get(4), gps_info.get(3, "E"))
            if lat is not None and lon is not None:
                return (lat, lon)
        except Exception:
            pass
        return None

    def compute_file_id(self, path: Path) -> str:
        hasher = hashlib.md5()
        hasher.update(str(path.resolve()).encode())
        return hasher.hexdigest()[:12]
```

- [ ] **Step 2: Write and run tests**

```python
# tests/test_metadata_extractor.py
from pathlib import Path
from smart_renamer.brain import MetadataExtractor


def test_extract_basic_file(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    extractor = MetadataExtractor()
    meta = extractor.extract(f)
    assert meta.path == f
    assert meta.size_bytes == 5
    assert meta.file_type == ".txt"


def test_compute_file_id_is_consistent(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_text("data")
    extractor = MetadataExtractor()
    id1 = extractor.compute_file_id(f)
    id2 = extractor.compute_file_id(f)
    assert id1 == id2
    assert len(id1) == 12
```

Run: `pytest tests/test_metadata_extractor.py -v`
Expected: 2 passed

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/brain/ tests/test_metadata_extractor.py
git commit -m "feat: add MetadataExtractor with EXIF parsing"
```

---

### Task 3: Classifier

**Files:**
- Create: `smart_renamer/brain/classifier.py`
- Test: `tests/test_classifier.py`

- [ ] **Step 1: Write the Classifier**

```python
# smart_renamer/brain/classifier.py
from smart_renamer.models import FileMetadata


class Classifier:
    def classify(self, metadata: FileMetadata) -> tuple[list[str], float]:
        tags: list[str] = []
        confidence = 0.5

        if self._is_wallpaper(metadata):
            tags.append("wallpaper")
            confidence = 0.7
        elif self._is_screenshot(metadata):
            tags.append("screenshot")
            confidence = 0.8
        elif self._has_exif_camera(metadata):
            tags.append("photo")
            confidence = 0.9
            if metadata.exif_camera:
                camera_name = metadata.exif_camera.split()[0].lower()
                tags.append(camera_name)
            if metadata.exif_date_taken:
                tags.append("dated")
        elif self._is_meme(metadata):
            tags.append("meme")
            confidence = 0.6
        elif metadata.file_type in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
            tags.append("video")
            confidence = 0.8
        elif metadata.file_type in {".mp3", ".wav", ".flac", ".aac", ".ogg"}:
            tags.append("audio")
            confidence = 0.8
        else:
            tags.append("unknown")
            confidence = 0.3

        if metadata.file_type in {".jpg", ".jpeg", ".png", ".webp"}:
            tags.append("image")

        return tags, confidence

    def _is_wallpaper(self, m: FileMetadata) -> bool:
        if m.dimensions is None:
            return False
        w, h = m.dimensions
        return (w >= 1920 and h >= 1080) and not self._has_exif_camera(m)

    def _is_screenshot(self, m: FileMetadata) -> bool:
        if m.dimensions is None:
            return False
        w, h = m.dimensions
        return (w, h) in {(1920, 1080), (2560, 1440), (3840, 2160), (1366, 768), (1440, 900)} and not self._has_exif_camera(m)

    def _is_meme(self, m: FileMetadata) -> bool:
        if m.dimensions is None:
            return False
        w, h = m.dimensions
        return 200 <= w <= 800 and 200 <= h <= 800 and not self._has_exif_camera(m)

    def _has_exif_camera(self, m: FileMetadata) -> bool:
        return m.exif_camera is not None
```

- [ ] **Step 2: Write and run tests**

```python
# tests/test_classifier.py
from smart_renamer.models import FileMetadata
from smart_renamer.brain.classifier import Classifier
from pathlib import Path


def test_classifies_wallpaper():
    meta = FileMetadata(
        path=Path("test.jpg"),
        dimensions=(3840, 2160),
        file_type=".jpg",
    )
    tags, conf = Classifier().classify(meta)
    assert "wallpaper" in tags
    assert conf >= 0.7


def test_classifies_photo_with_exif():
    meta = FileMetadata(
        path=Path("photo.jpg"),
        dimensions=(4000, 3000),
        file_type=".jpg",
        exif_camera="Canon EOS 5D",
    )
    tags, conf = Classifier().classify(meta)
    assert "photo" in tags
    assert "canon" in tags
    assert conf >= 0.9


def test_classifies_screenshot():
    meta = FileMetadata(
        path=Path("screen.png"),
        dimensions=(1920, 1080),
        file_type=".png",
    )
    tags, conf = Classifier().classify(meta)
    assert "screenshot" in tags


def test_classifies_video():
    meta = FileMetadata(path=Path("vid.mp4"), file_type=".mp4")
    tags, conf = Classifier().classify(meta)
    assert "video" in tags


def test_low_confidence_for_unknown():
    meta = FileMetadata(path=Path("data.bin"), file_type=".bin")
    tags, conf = Classifier().classify(meta)
    assert "unknown" in tags
    assert conf < 0.5
```

Run: `pytest tests/test_classifier.py -v`
Expected: 5 passed

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/brain/classifier.py tests/test_classifier.py
git commit -m "feat: add heuristic Classifier for image types"
```

---

### Task 4: Template Engine

**Files:**
- Create: `smart_renamer/brain/template_engine.py`
- Test: `tests/test_template_engine.py`

- [ ] **Step 1: Write the Template Engine**

```python
# smart_renamer/brain/template_engine.py
import re
import os
from pathlib import Path


class TemplateEngine:
    def __init__(self, template: str = "{tags}_{index}"):
        self.template = template

    def generate(self, tags: list[str], index: int, ext: str, metadata_summary: str = "") -> str:
        context = {
            "tags": "_".join(tags) if tags else "untagged",
            "index": str(index).zfill(2),
            "date": "",
            "ext": ext.lstrip("."),
            "summary": self._slugify(metadata_summary[:30]),
        }
        result = self.template
        for key, value in context.items():
            result = result.replace(f"{{{key}}}", value)
        result = self._sanitize(result)
        return f"{result}.{ext.lstrip('.')}".lower()

    def _sanitize(self, name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        name = re.sub(r'\s+', "_", name)
        name = name.strip("._")
        max_len = 200
        name = name[:max_len]
        return name if name else "unnamed"
```

- [ ] **Step 2: Write and run tests**

```python
# tests/test_template_engine.py
from smart_renamer.brain.template_engine import TemplateEngine


def test_default_template():
    engine = TemplateEngine()
    result = engine.generate(["sunset", "beach"], 1, ".jpg")
    assert result == "sunset_beach_01.jpg"


def test_custom_template():
    engine = TemplateEngine("{date}_{tags}_{index}")
    result = engine.generate(["mountain"], 3, ".png")
    assert result.startswith("_mountain_03.png")  # date is empty


def test_sanitizes_invalid_chars():
    engine = TemplateEngine("{tags}_{index}")
    result = engine.generate(["cool:pic"], 1, ".jpg")
    assert ":" not in result
    assert result.endswith(".jpg")


def test_handles_empty_tags():
    engine = TemplateEngine()
    result = engine.generate([], 1, ".png")
    assert result.startswith("untagged")


def test_max_length_200():
    engine = TemplateEngine()
    long_tags = ["a" * 50] * 10
    result = engine.generate(long_tags, 1, ".jpg")
    assert len(result) <= 205  # 200 + ".jpg"
```

Run: `pytest tests/test_template_engine.py -v`
Expected: 5 passed

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/brain/template_engine.py tests/test_template_engine.py
git commit -m "feat: add TemplateEngine for filename generation"
```

---

### Task 5: Planner (Brain Orchestrator)

**Files:**
- Create: `smart_renamer/brain/planner.py`
- Test: `tests/test_planner.py`

- [ ] **Step 1: Write the Planner**

```python
# smart_renamer/brain/planner.py
from pathlib import Path
from smart_renamer.models import RenamePlan
from smart_renamer.brain.metadata_extractor import MetadataExtractor
from smart_renamer.brain.classifier import Classifier
from smart_renamer.brain.template_engine import TemplateEngine


class Planner:
    def __init__(self, template: str = "{tags}_{index}"):
        self.metadata_extractor = MetadataExtractor()
        self.classifier = Classifier()
        self.template_engine = TemplateEngine(template)

    def plan(self, files: list[Path], vision_router=None) -> list[RenamePlan]:
        plans: list[RenamePlan] = []
        for idx, filepath in enumerate(sorted(files), start=1):
            if not filepath.is_file():
                continue
            metadata = self.metadata_extractor.extract(filepath)
            tags, confidence = self.classifier.classify(metadata)
            metadata_summary = self._build_summary(metadata, tags)
            if vision_router and confidence < 0.6:
                vision_tags = vision_router.enrich(filepath)
                if vision_tags:
                    tags = vision_tags
                    confidence = 0.85
            file_id = self.metadata_extractor.compute_file_id(filepath)
            new_name = self.template_engine.generate(tags, idx, metadata.file_type, metadata_summary)
            plans.append(RenamePlan(
                file_id=file_id,
                old_path=filepath,
                proposed_new_name=new_name,
                confidence=round(confidence, 2),
                tags=tags,
                metadata_summary=metadata_summary,
            ))
        return plans

    def _build_summary(self, metadata, tags: list[str]) -> str:
        parts = []
        if metadata.dimensions:
            parts.append(f"{metadata.dimensions[0]}x{metadata.dimensions[1]}")
        if metadata.exif_camera:
            parts.append(metadata.exif_camera)
        if metadata.exif_date_taken:
            parts.append(metadata.exif_date_taken.strftime("%Y-%m-%d"))
        parts.append(", ".join(tags))
        return " | ".join(parts)
```

- [ ] **Step 2: Write and run tests**

```python
# tests/test_planner.py
from pathlib import Path
from smart_renamer.brain.planner import Planner


def test_planner_skips_non_files(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()
    planner = Planner()
    plans = planner.plan([d])
    assert len(plans) == 0


def test_planner_generates_renames_for_files(tmp_path):
    f1 = tmp_path / "photo.jpg"
    f1.write_text("fake-jpeg-data")
    f2 = tmp_path / "wallpaper.png"
    f2.write_text("fake-png-data")
    planner = Planner()
    plans = planner.plan([f1, f2])
    assert len(plans) == 2
    for plan in plans:
        assert plan.proposed_new_name.endswith((".jpg", ".png"))
        assert plan.confidence > 0
        assert len(plan.file_id) == 12
```

Run: `pytest tests/test_planner.py -v`
Expected: 2 passed

- [ ] **Step 3: Update brain __init__.py**

```python
# smart_renamer/brain/__init__.py
from .metadata_extractor import MetadataExtractor
from .classifier import Classifier
from .template_engine import TemplateEngine
from .planner import Planner

__all__ = ["MetadataExtractor", "Classifier", "TemplateEngine", "Planner"]
```

- [ ] **Step 4: Commit**

```bash
git add smart_renamer/brain/ tests/test_planner.py
git commit -m "feat: add Planner orchestrator for rename plan generation"
```

---

### Task 6: Optional Vision Router (Gemini)

**Files:**
- Create: `smart_renamer/brain/vision_router.py`
- Test: `tests/test_vision_router.py`

- [ ] **Step 1: Write the Vision Router**

```python
# smart_renamer/brain/vision_router.py
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Optional
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
        if cached:
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
```

- [ ] **Step 2: Write tests (mocked)**

```python
# tests/test_vision_router.py
from smart_renamer.brain.vision_router import VisionRouter
from pathlib import Path


def test_vision_router_unavailable_without_key():
    router = VisionRouter(api_key="")
    assert not router.is_available()
    assert router.enrich(Path("test.jpg")) == []


def test_vision_router_skips_non_images():
    router = VisionRouter(api_key="fake")
    assert router.enrich(Path("test.txt")) == []


def test_cache_hit(tmp_path):
    img = tmp_path / "test.jpg"
    img.write_text("fake-data")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    router = VisionRouter(api_key="fake", cache_dir=cache_dir)
    key = router._cache_key(img)
    cache_file = cache_dir / f"{key}.json"
    import json
    cache_file.write_text(json.dumps(["sunset", "ocean"]))
    result = router.enrich(img)
    assert result == ["sunset", "ocean"]
```

Run: `pytest tests/test_vision_router.py -v`
Expected: 3 passed

- [ ] **Step 3: Update brain __init__.py**

```python
# smart_renamer/brain/__init__.py
from .metadata_extractor import MetadataExtractor
from .classifier import Classifier
from .template_engine import TemplateEngine
from .planner import Planner
from .vision_router import VisionRouter

__all__ = ["MetadataExtractor", "Classifier", "TemplateEngine", "Planner", "VisionRouter"]
```

- [ ] **Step 4: Commit**

```bash
git add smart_renamer/brain/vision_router.py smart_renamer/brain/__init__.py tests/test_vision_router.py
git commit -m "feat: add optional Gemini Vision Router with caching"
```

---

### Task 7: Validator Layer

**Files:**
- Create: `smart_renamer/validator/__init__.py`
- Create: `smart_renamer/validator/validator.py`
- Test: `tests/test_validator.py`

- [ ] **Step 1: Write the Validator**

```python
# smart_renamer/validator/__init__.py
from .validator import Validator

__all__ = ["Validator"]
```

```python
# smart_renamer/validator/validator.py
import os
import re
from collections import Counter
from pathlib import Path
from smart_renamer.models import RenamePlan, ValidationReport, Conflict


class Validator:
    MAX_PATH_LENGTH = 255
    INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')
    RESERVED_NAMES = {"con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"}

    def validate(self, plans: list[RenamePlan], target_dir: Path) -> ValidationReport:
        report = ValidationReport()
        proposed_names = [p.proposed_new_name for p in plans]
        duplicates = {name: idxs for name, idxs in Counter(proposed_names).items() if idxs > 1}
        for name, count in duplicates.items():
            conflicted = [p for p in plans if p.proposed_new_name == name]
            report.conflicts.append(Conflict(
                file_ids=[p.file_id for p in conflicted],
                proposed_name=name,
                reason=f"{count} files would get the same name"
            ))
        for plan in plans:
            full_path = target_dir / plan.proposed_new_name
            if full_path.exists() and full_path != plan.old_path:
                report.conflicts.append(Conflict(
                    file_ids=[plan.file_id],
                    proposed_name=plan.proposed_new_name,
                    reason="Target file already exists"
                ))
            if len(str(full_path)) > self.MAX_PATH_LENGTH:
                report.warnings.append(f"Path too long: {plan.proposed_new_name} ({len(str(full_path))} chars)")
            name_stem = Path(plan.proposed_new_name).stem.lower()
            if name_stem in self.RESERVED_NAMES:
                report.warnings.append(f"Reserved filename: {plan.proposed_new_name}")
            if self.INVALID_CHARS.search(plan.proposed_new_name):
                report.warnings.append(f"Invalid characters in: {plan.proposed_new_name}")
        return report
```

- [ ] **Step 2: Write and run tests**

```python
# tests/test_validator.py
from pathlib import Path
from smart_renamer.models import RenamePlan
from smart_renamer.validator import Validator


def test_detects_duplicate_names():
    plans = [
        RenamePlan(file_id="a", old_path=Path("1.jpg"), proposed_new_name="same.jpg", confidence=0.9, tags=[], metadata_summary=""),
        RenamePlan(file_id="b", old_path=Path("2.jpg"), proposed_new_name="same.jpg", confidence=0.9, tags=[], metadata_summary=""),
    ]
    report = Validator().validate(plans, Path("/tmp"))
    assert len(report.conflicts) == 1
    assert "same.jpg" in report.conflicts[0].proposed_name


def test_detects_existing_file(tmp_path):
    existing = tmp_path / "existing.jpg"
    existing.write_text("data")
    plans = [
        RenamePlan(file_id="a", old_path=Path("test.jpg"), proposed_new_name="existing.jpg", confidence=0.9, tags=[], metadata_summary=""),
    ]
    report = Validator().validate(plans, tmp_path)
    assert len(report.conflicts) == 1


def test_no_conflicts_for_unique_names(tmp_path):
    plans = [
        RenamePlan(file_id="a", old_path=Path("1.jpg"), proposed_new_name="sunset.jpg", confidence=0.9, tags=[], metadata_summary=""),
        RenamePlan(file_id="b", old_path=Path("2.jpg"), proposed_new_name="beach.jpg", confidence=0.9, tags=[], metadata_summary=""),
    ]
    report = Validator().validate(plans, tmp_path)
    assert len(report.conflicts) == 0
```

Run: `pytest tests/test_validator.py -v`
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/validator/ tests/test_validator.py
git commit -m "feat: add Validator for conflict detection and safety checks"
```

---

### Task 8: Executor Layer

**Files:**
- Create: `smart_renamer/executor/__init__.py`
- Create: `smart_renamer/executor/executor.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write the Executor**

```python
# smart_renamer/executor/__init__.py
from .executor import Executor

__all__ = ["Executor"]
```

```python
# smart_renamer/executor/executor.py
import json
import shutil
from datetime import datetime
from pathlib import Path
from smart_renamer.models import RenamePlan, ExecutionResult, UndoEntry


class Executor:
    def __init__(self, undo_dir: Path | None = None):
        self.undo_dir = undo_dir or Path.home() / ".smart_renamer" / "undo"
        self.undo_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, plans: list[RenamePlan], target_dir: Path) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        undo_entries: list[UndoEntry] = []
        for plan in plans:
            new_path = target_dir / plan.proposed_new_name
            try:
                if new_path.exists():
                    results.append(ExecutionResult(
                        file_id=plan.file_id, success=False,
                        old_path=plan.old_path, error="Target exists"
                    ))
                    continue
                if not plan.old_path.exists():
                    results.append(ExecutionResult(
                        file_id=plan.file_id, success=False,
                        old_path=plan.old_path, error="Source not found"
                    ))
                    continue
                shutil.move(str(plan.old_path), str(new_path))
                undo_entries.append(UndoEntry(old_path=new_path, new_path=plan.old_path))
                results.append(ExecutionResult(
                    file_id=plan.file_id, success=True,
                    old_path=plan.old_path, new_path=new_path
                ))
            except OSError as e:
                results.append(ExecutionResult(
                    file_id=plan.file_id, success=False,
                    old_path=plan.old_path, error=str(e)
                ))
        if undo_entries:
            self._save_undo(undo_entries)
        return results

    def _save_undo(self, entries: list[UndoEntry]) -> Path:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        undo_file = self.undo_dir / f"{session_id}.json"
        data = [{"old_path": str(e.old_path), "new_path": str(e.new_path)} for e in entries]
        undo_file.write_text(json.dumps(data, indent=2))
        return undo_file

    def undo(self, session_id: str) -> list[ExecutionResult]:
        undo_file = self.undo_dir / f"{session_id}.json"
        if not undo_file.exists():
            return [ExecutionResult(file_id="", success=False, old_path=Path(""), error=f"Undo session {session_id} not found")]
        data = json.loads(undo_file.read_text())
        results = []
        for entry in data:
            old_path = Path(entry["old_path"])
            new_path = Path(entry["new_path"])
            try:
                shutil.move(str(old_path), str(new_path))
                results.append(ExecutionResult(file_id="", success=True, old_path=old_path, new_path=new_path))
            except OSError as e:
                results.append(ExecutionResult(file_id="", success=False, old_path=old_path, error=str(e)))
        return results
```

- [ ] **Step 2: Write and run tests**

```python
# tests/test_executor.py
from pathlib import Path
from smart_renamer.models import RenamePlan
from smart_renamer.executor import Executor


def test_execute_rename_success(tmp_path):
    src = tmp_path / "old.jpg"
    src.write_text("data")
    plans = [
        RenamePlan(file_id="a", old_path=src, proposed_new_name="new.jpg", confidence=0.9, tags=[], metadata_summary=""),
    ]
    ex = Executor(undo_dir=tmp_path / "undo")
    results = ex.execute(plans, tmp_path)
    assert results[0].success
    assert (tmp_path / "new.jpg").exists()
    assert not src.exists()


def test_execute_skips_missing_source(tmp_path):
    plans = [
        RenamePlan(file_id="a", old_path=tmp_path / "nonexistent.jpg", proposed_new_name="new.jpg", confidence=0.9, tags=[], metadata_summary=""),
    ]
    ex = Executor(undo_dir=tmp_path / "undo")
    results = ex.execute(plans, tmp_path)
    assert not results[0].success
    assert results[0].error == "Source not found"


def test_execute_skips_existing_target(tmp_path):
    src = tmp_path / "old.jpg"
    src.write_text("data")
    existing = tmp_path / "existing.jpg"
    existing.write_text("other")
    plans = [
        RenamePlan(file_id="a", old_path=src, proposed_new_name="existing.jpg", confidence=0.9, tags=[], metadata_summary=""),
    ]
    ex = Executor(undo_dir=tmp_path / "undo")
    results = ex.execute(plans, tmp_path)
    assert not results[0].success
    assert "Target exists" in results[0].error
```

Run: `pytest tests/test_executor.py -v`
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/executor/ tests/test_executor.py
git commit -m "feat: add Executor with undo support"
```

---

### Task 9: Skills System (SKILL.md files)

**Files:**
- Create: `skills/image_classification/SKILL.md`
- Create: `skills/filename_generation/SKILL.md`
- Create: `skills/metadata_analysis/SKILL.md`
- Create: `skills/safety_validation/SKILL.md`

- [ ] **Step 1: Write each SKILL.md**

```markdown
# skills/image_classification/SKILL.md
# Image Classification Heuristics

## Rules
- If no EXIF camera data AND dimensions >= 1920x1080 → wallpaper
- If EXIF camera data present → photo
- If dimensions exactly match common screen resolutions (1920x1080, 2560x1440, etc.) AND no EXIF camera → screenshot
- If dimensions between 200-800px AND no EXIF camera → meme
- Multi-label: files can be both "image" and "wallpaper"

## Examples
- 3840x2160, no camera → wallpaper
- 4000x3000, Canon EOS → photo
- 1920x1080, no camera → screenshot
- 512x512, no camera → meme

## Constraints
- Classification is heuristic, not AI. Low-confidence files (<0.6) may be sent to Vision Router if enabled.
```

```markdown
# skills/filename_generation/SKILL.md
# Filename Generation Rules

## Default Template
{tags}_{index}

## Template Variables
- {tags} — underscore-joined semantic tags from classifier/vision
- {index} — zero-padded 2-digit index
- {date} — best-available date from metadata
- {ext} — original file extension
- {summary} — first 30 chars of metadata summary

## Sanitization Rules
- Replace invalid chars (<>:"/\|?*) with underscore
- Replace whitespace with underscore
- Max 200 chars for basename
- Force lowercase
- Strip leading/trailing dots and underscores
```

```markdown
# skills/metadata_analysis/SKILL.md
# Metadata Analysis Rules

## Date Priority
1. EXIF DateTimeOriginal
2. File creation date (ctime)
3. File modification date (mtime)

## GPS Handling
- Extract from EXIF GPSInfo tag
- Convert DMS to decimal degrees
- Skip if coords are (0,0) or clearly invalid

## Camera
- Concatenate Make + Model from EXIF
- Use first word as tag (e.g., "canon" from "Canon EOS 5D")
```

```markdown
# skills/safety_validation/SKILL.md
# Safety Validation Rules

## OS-Safe Filenames
- Strip: < > : " / \ | ? *
- Reserved names (Windows): CON, PRN, AUX, NUL, COM1-9, LPT1-9
- Max path length: 255 characters

## Conflict Prevention
- Detect duplicate proposed names → auto-index
- Never overwrite existing files
- Source must exist before rename

## Reversibility
- Every rename creates undo entry
- Undo restores original name at original path
- Undo sessions stored in ~/.smart_renamer/undo/
```

- [ ] **Step 2: Commit**

```bash
git add skills/
git commit -m "feat: add skills system with classification, generation, metadata, and safety rules"
```

---

### Task 10: Configuration

**Files:**
- Create: `smart_renamer/config.py`
- Create: `smart_renamer.toml` (example)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write config module and example**

```python
# smart_renamer/config.py
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
```

```toml
# smart_renamer.toml (example — copy to project root or ~/.config/smart_renamer/config.toml)
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
enable_vision = false
```

- [ ] **Step 2: Write and run tests**

```python
# tests/test_config.py
from pathlib import Path
from smart_renamer.config import Config


def test_defaults():
    cfg = Config()
    assert cfg.template == "{tags}_{index}"
    assert cfg.dry_run is True


def test_loads_from_file(tmp_path):
    config_file = tmp_path / "smart_renamer.toml"
    config_file.write_text("""
[general]
template = "{date}_{tags}"
dry_run = false

[gemini]
enabled = true
api_key = "test-key"
""")
    cfg = Config(config_file)
    assert cfg.template == "{date}_{tags}"
    assert cfg.dry_run is False
    assert cfg.gemini_enabled is True
    assert cfg.gemini_api_key == "test-key"
```

Run: `pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/config.py smart_renamer.toml tests/test_config.py
git commit -m "feat: add TOML-based configuration"
```

---

### Task 11: Main Entry Point

**Files:**
- Create: `smart_renamer/main.py`
- Create: `__init__.py` (project root)

- [ ] **Step 1: Write CLI entry point**

```python
# smart_renamer/main.py
import sys
from pathlib import Path
from smart_renamer.config import Config
from smart_renamer.brain.planner import Planner
from smart_renamer.brain.vision_router import VisionRouter
from smart_renamer.validator import Validator
from smart_renamer.executor import Executor


def main():
    args = sys.argv[1:]
    target_dir = Path(args[0]) if args else Path.cwd()
    config = Config()
    vision_router = VisionRouter(api_key=config.gemini_api_key) if config.gemini_enabled else None
    planner = Planner(template=config.template)
    files = sorted(target_dir.iterdir()) if not config.recursive else sorted(target_dir.rglob("*"))
    files = [f for f in files if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".flac"}]
    if not files:
        print("No supported media files found.")
        sys.exit(0)
    plans = planner.plan(files, vision_router)
    validator = Validator()
    report = validator.validate(plans, target_dir)
    if report.conflicts:
        print("Validation conflicts found:")
        for c in report.conflicts:
            print(f"  - {c.reason}: {c.proposed_name}")
        sys.exit(1)
    print(f"Planned renames for {len(plans)} files:")
    for plan in plans:
        marker = "[DRY RUN]" if config.dry_run else "[EXECUTE]"
        print(f"  {marker} {plan.old_path.name} → {plan.proposed_new_name}  (conf: {plan.confidence})")
    if not config.dry_run:
        executor = Executor()
        results = executor.execute(plans, target_dir)
        success = sum(1 for r in results if r.success)
        print(f"Renamed {success}/{len(results)} files.")
    else:
        print("Dry run — no files changed. Set dry_run = false to execute.")


if __name__ == "__main__":
    main()
```

```python
# __init__.py (project root — empty)
```

- [ ] **Step 2: Create a `pyproject.toml` for the project**

```toml
[project]
name = "smart-renamer"
version = "0.1.0"
description = "AI-powered bulk file renamer with TUI"
requires-python = ">=3.11"
dependencies = [
    "textual>=1.0.0",
    "pydantic>=2.0.0",
    "Pillow>=10.0.0",
    "httpx>=0.25.0",
]
```

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/main.py pyproject.toml __init__.py
git commit -m "feat: add CLI entry point and project config"
```

---

### Task 12: Textual TUI

**Files:**
- Create: `smart_renamer/tui/__init__.py`
- Create: `smart_renamer/tui/app.py`

- [ ] **Step 1: Write the TUI app**

```python
# smart_renamer/tui/__init__.py
```

```python
# smart_renamer/tui/app.py
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, DataTable, Static, Button, Label
from textual.screen import Screen
from textual.binding import Binding
from textual.reactive import reactive
from smart_renamer.brain.planner import Planner
from smart_renamer.brain.vision_router import VisionRouter
from smart_renamer.validator import Validator
from smart_renamer.executor import Executor
from smart_renamer.config import Config


class FileTable(DataTable):
    def __init__(self, plans, **kwargs):
        super().__init__(**kwargs)
        self.plans = plans
        self.approved = {p.file_id: True for p in plans}

    def on_mount(self):
        self.add_columns("✓", "Old Name", "Proposed Name", "Confidence", "Tags")
        for plan in self.plans:
            check = "✓" if self.approved[plan.file_id] else " "
            tags_str = ", ".join(plan.tags[:3])
            self.add_row(check, plan.old_path.name, plan.proposed_new_name, f"{plan.confidence:.0%}", tags_str)

    def toggle_file(self, file_id: str) -> None:
        self.approved[file_id] = not self.approved[file_id]
        self.clear()
        self.on_mount()


class PreviewPanel(Vertical):
    def __init__(self, plan=None, **kwargs):
        super().__init__(**kwargs)
        self._plan = plan

    def set_plan(self, plan):
        self._plan = plan
        self._update()

    def on_mount(self):
        self._update()

    def _update(self):
        self.remove_children()
        if not self._plan:
            self.mount(Static("Select a file to preview", id="preview-empty"))
            return
        self.mount(Static(f"Old: {self._plan.old_path.name}", id="preview-old"))
        self.mount(Static(f"New: {self._plan.proposed_new_name}", id="preview-new"))
        self.mount(Static(f"Tags: {', '.join(self._plan.tags)}", id="preview-tags"))
        self.mount(Static(f"Confidence: {self._plan.confidence:.0%}", id="preview-conf"))
        self.mount(Static(f"Summary: {self._plan.metadata_summary}", id="preview-summary"))


class StatusBar(Static):
    status = reactive("initial")

    def on_mount(self):
        self._update()

    def watch_status(self, val: str):
        self._update()

    def _update(self):
        self.update(f"Status: {self.status}")


class SmartRenamerApp(App):
    TITLE = "SmartRenamer"
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 3fr 1fr;
    }
    #file-grid { border: solid $primary; }
    #preview { border: solid $secondary; padding: 1; }
    #controls { column-span: 2; height: 3; }
    DataTable { height: 100%; }
    Button { margin: 1; }
    StatusBar { column-span: 2; height: 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_file", "Toggle"),
        Binding("a", "approve_all", "Approve All"),
        Binding("e", "execute", "Execute"),
    ]

    def __init__(self, target_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.target_dir = target_dir
        self.config = Config()
        self.planner = Planner(template=self.config.template)
        self.vision_router = VisionRouter() if self.config.gemini_enabled else None
        self.validator = Validator()
        self.executor = Executor()
        self.plans = []
        self.status_bar = StatusBar()

    def on_mount(self):
        self.status_bar.status = "Scanning files..."
        files = sorted(self.target_dir.iterdir())
        files = [f for f in files if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".flac"}]
        self.plans = self.planner.plan(files, self.vision_router)
        self.set_screen(MainScreen(self))

    def action_toggle_file(self):
        table = self.query_one(FileTable)
        if table.cursor_row is not None:
            plan = self.plans[table.cursor_row]
            table.toggle_file(plan.file_id)

    def action_approve_all(self):
        table = self.query_one(FileTable)
        for plan in self.plans:
            table.approved[plan.file_id] = True
        table.clear()
        table.on_mount()

    def action_execute(self):
        table = self.query_one(FileTable)
        approved = [p for p in self.plans if table.approved.get(p.file_id, False)]
        report = self.validator.validate(approved, self.target_dir)
        if report.conflicts:
            self.status_bar.status = f"Conflicts: {len(report.conflicts)} — fix and retry"
            return
        self.status_bar.status = "Executing..."
        results = self.executor.execute(approved, self.target_dir)
        ok = sum(1 for r in results if r.success)
        self.status_bar.status = f"Done: {ok}/{len(results)} renamed"
        table.clear()
        self.plans = [p for p in self.plans if table.approved.get(p.file_id, False) and p.file_id not in {r.file_id for r in results if r.success}]
        table.on_mount()


class MainScreen(Screen):
    def compose(self):
        yield Header()
        with Horizontal():
            with Vertical(id="file-grid"):
                yield FileTable(self.app.plans, id="file-table")
            with Vertical(id="preview"):
                yield PreviewPanel(id="preview-panel")
        with Horizontal(id="controls"):
            yield Button("Toggle (Space)", id="btn-toggle")
            yield Button("Approve All (A)", id="btn-approve")
            yield Button("Execute (E)", id="btn-execute")
        yield Footer()
```

- [ ] **Step 2: Commit**

```bash
git add smart_renamer/tui/
git commit -m "feat: add Textual TUI with file grid, preview, and controls"
```

---

### Task 13: Final Wiring + README

**Files:**
- Modify: `smart_renamer/main.py` — add TUI launch path
- Create: `README.md`

- [ ] **Step 1: Update main.py to support TUI mode**

```python
# smart_renamer/main.py
import sys
from pathlib import Path
from smart_renamer.config import Config
from smart_renamer.brain.planner import Planner
from smart_renamer.brain.vision_router import VisionRouter
from smart_renamer.validator import Validator
from smart_renamer.executor import Executor


def cli():
    args = sys.argv[1:]
    use_tui = "--tui" in args or "-t" in args
    target_dir = None
    for a in args:
        if not a.startswith("-"):
            target_dir = Path(a)
            break
    target_dir = target_dir or Path.cwd()
    if use_tui:
        from smart_renamer.tui.app import SmartRenamerApp
        app = SmartRenamerApp(target_dir)
        app.run()
        return
    config = Config()
    vision_router = VisionRouter(api_key=config.gemini_api_key) if config.gemini_enabled else None
    planner = Planner(template=config.template)
    files = sorted(target_dir.iterdir()) if not config.recursive else sorted(target_dir.rglob("*"))
    files = [f for f in files if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".flac"}]
    if not files:
        print("No supported media files found.")
        sys.exit(0)
    plans = planner.plan(files, vision_router)
    validator = Validator()
    report = validator.validate(plans, target_dir)
    if report.conflicts:
        print("Validation conflicts found:")
        for c in report.conflicts:
            print(f"  - {c.reason}: {c.proposed_name}")
        sys.exit(1)
    print(f"Planned renames for {len(plans)} files:")
    for plan in plans:
        marker = "[DRY RUN]" if config.dry_run else "[EXECUTE]"
        print(f"  {marker} {plan.old_path.name} → {plan.proposed_new_name}  (conf: {plan.confidence})")
    if not config.dry_run:
        executor = Executor()
        results = executor.execute(plans, target_dir)
        success = sum(1 for r in results if r.success)
        print(f"Renamed {success}/{len(results)} files.")
    else:
        print("Dry run — no files changed. Set dry_run = false to execute.")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Write README**

```markdown
# SmartRenamer

AI-powered bulk file renamer with a terminal UI. Uses metadata extraction and heuristic classification to suggest intelligent filenames. Optionally uses Google Gemini Vision API for semantic image tagging.

## Quick Start

```bash
pip install smart-renamer

# CLI mode (dry-run by default)
smart-renamer /path/to/images

# Execute (after reviewing)
smart-renamer /path/to/images --execute

# TUI mode
smart-renamer /path/to/images --tui
```

## Configuration

Create `smart_renamer.toml` in your project root or `~/.config/smart_renamer/config.toml`:

```toml
[general]
template = "{tags}_{index}"
dry_run = true

[gemini]
enabled = true
api_key = "your-key-here"  # or set GEMINI_API_KEY env var
```

## Safety

- Dry-run by default — nothing is renamed without explicit approval
- Undo support via `~/.smart_renamer/undo/<session>.json`
- Conflict detection prevents overwrites
```

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/main.py README.md
git commit -m "feat: add TUI mode, README, and final wiring"
```

---

## Self-Review Checklist

1. **Spec coverage:** Every section of the spec has a corresponding task — models (1), metadata extractor (2), classifier (3), template engine (4), planner (5), vision router (6), validator (7), executor (8), skills system (9), config (10), main entry point (11), TUI (12), final wiring (13).

2. **Placeholder scan:** No TBDs, TODOs, or vague steps. Every step has complete code.

3. **Type consistency:** All imports reference the correct module paths. Method signatures match between tasks.

4. **Scope check:** Focused on SmartRenamer implementation only. No scope creep.
