# SmartRenamer Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Textual TUI with OpenTUI (TypeScript) and refactor Python backend into a persistent JSON-RPC process with session management, caching, and a vision decision engine.

**Architecture:** Python backend runs as a long-lived process communicating via JSON-RPC 2.0 over stdin/stdout. OpenTUI (Bun/TypeScript) renders the TUI, manages user state, and calls backend methods via RPC. Existing brain modules (classifier, vision_router, metadata_extractor, template_engine) are reused with minor refactoring.

**Tech Stack:** Python 3.11+, Bun, OpenTUI (React reconciler), Pillow, httpx, pydantic

---

### Task 0: Install Bun

**Files:** None (system setup)

- [ ] **Step 1: Install Bun**

```bash
curl -fsSL https://bun.sh/install | bash
```

- [ ] **Step 2: Verify installation**

```bash
bun --version
```
Expected output: `1.x.x`

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: install Bun runtime"
```

---

### Task 1: Backend Package Skeleton + Enhanced Models

**Files:**
- Create: `smart_renamer/backend/__init__.py`
- Create: `smart_renamer/backend/models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_models.py`:

```python
from smart_renamer.backend.models import SessionState, RenamePlan, Session, RPCRequest, RPCResponse, SessionStatus, RenamePlanState


def test_session_state_enum():
    assert SessionState.CREATED.value == "CREATED"
    assert SessionState.LOADED.value == "LOADED"
    assert SessionState.PLANNED.value == "PLANNED"
    assert SessionState.ENRICHED.value == "ENRICHED"
    assert SessionState.VALIDATED.value == "VALIDATED"
    assert SessionState.APPROVED.value == "APPROVED"
    assert SessionState.EXECUTED.value == "EXECUTED"
    assert list(SessionState) == [
        SessionState.CREATED, SessionState.LOADED, SessionState.PLANNED,
        SessionState.ENRICHED, SessionState.VALIDATED, SessionState.APPROVED,
        SessionState.EXECUTED,
    ]


def test_rename_plan_state_enum():
    assert RenamePlanState.RAW.value == "RAW"
    assert RenamePlanState.PLANNED.value == "PLANNED"
    assert RenamePlanState.ENRICHED.value == "ENRICHED"
    assert RenamePlanState.VALIDATED.value == "VALIDATED"
    assert RenamePlanState.APPROVED.value == "APPROVED"
    assert RenamePlanState.EXECUTED.value == "EXECUTED"


def test_rename_plan_with_reasoning():
    from smart_renamer.backend.models import RenamePlan as BackendPlan
    plan = BackendPlan(
        file_id="abc123",
        original_path="/tmp/test.jpg",
        proposed_name="sunset_beach_01.jpg",
        tags=["sunset", "beach"],
        confidence=0.85,
        reasoning="Vision: identified sunset. Classifier: photo based on EXIF camera.",
        state=RenamePlanState.PLANNED,
    )
    assert plan.state == RenamePlanState.PLANNED
    assert plan.reasoning.startswith("Vision:")
    assert plan.confidence == 0.85


def test_rpc_request():
    req = RPCRequest(id="1", method="plan", params={"session_id": "sess_abc"})
    assert req.id == "1"
    assert req.method == "plan"
    assert req.params["session_id"] == "sess_abc"
    assert req.jsonrpc == "2.0"


def test_rpc_response_ok():
    resp = RPCResponse.ok(id="1", data={"plans": []})
    assert resp.status == "ok"
    assert resp.data["plans"] == []


def test_rpc_response_error():
    resp = RPCResponse.error(id="1", code="SESSION_NOT_FOUND", message="Session not found")
    assert resp.status == "error"
    assert resp.data["code"] == "SESSION_NOT_FOUND"


def test_session_initial_state():
    from pathlib import Path
    session = Session(session_id="sess_test", directory=Path("/tmp"))
    assert session.state == SessionState.CREATED
    assert len(session.plans) == 0


def test_session_status():
    from pathlib import Path
    session = Session(session_id="sess_test", directory=Path("/tmp"))
    session.file_count = 42
    status = session.get_status()
    assert status["state"] == "CREATED"
    assert status["file_count"] == 42
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_models.py -v 2>&1
```
Expected: ModuleNotFoundError / ImportError

- [ ] **Step 3: Write implementation**

Create `smart_renamer/backend/__init__.py`:
```python
"""
SmartRenamer backend package.

Persistent JSON-RPC backend for the OpenTUI frontend.
"""
```

Create `smart_renamer/backend/models.py`:
```python
from __future__ import annotations
import enum
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Any


class SessionState(str, enum.Enum):
    CREATED = "CREATED"
    LOADED = "LOADED"
    PLANNED = "PLANNED"
    ENRICHED = "ENRICHED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"


class RenamePlanState(str, enum.Enum):
    RAW = "RAW"
    PLANNED = "PLANNED"
    ENRICHED = "ENRICHED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"


class RenamePlan(BaseModel):
    file_id: str
    original_path: str
    proposed_name: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    state: RenamePlanState = RenamePlanState.PLANNED
    reasoning: str = ""


class Approval(BaseModel):
    file_id: str
    approved: bool = True
    custom_name: str | None = None  # user-edited name override


class ValidationReport(BaseModel):
    valid: bool = True
    conflicts: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    file_id: str
    success: bool
    old_path: str
    new_path: str
    error: str = ""


class UndoEntry(BaseModel):
    old_path: str
    new_path: str


class Session(BaseModel):
    session_id: str
    directory: Path
    config_path: Path | None = None
    state: SessionState = SessionState.CREATED
    file_count: int = 0
    plans: list[RenamePlan] = Field(default_factory=list)
    approvals: dict[str, Approval] = Field(default_factory=dict)
    undo_log: list[UndoEntry] = Field(default_factory=list)
    fingerprint: str = ""

    def get_status(self) -> dict:
        enriched = sum(1 for p in self.plans if p.state == RenamePlanState.ENRICHED)
        return {
            "state": self.state.value,
            "file_count": self.file_count,
            "enriched_count": enriched,
        }


class RPCRequest(BaseModel):
    id: str
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    jsonrpc: str = "2.0"


class RPCResponse(BaseModel):
    id: str
    status: str  # "ok" | "error"
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(cls, id: str, data: dict[str, Any] | None = None) -> RPCResponse:
        return cls(id=id, status="ok", data=data or {})

    @classmethod
    def error(cls, id: str, code: str, message: str) -> RPCResponse:
        return cls(id=id, status="error", data={"code": code, "message": message})
```

- [ ] **Step 4: Run test to verify it passes**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_models.py -v 2>&1
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add smart_renamer/backend/ tests/test_backend_models.py
git commit -m "feat: add backend package skeleton with session models and RPC types"
```

---

### Task 2: Cache System

**Files:**
- Create: `smart_renamer/backend/cache/__init__.py`
- Create: `smart_renamer/backend/cache/metadata_cache.py`
- Create: `smart_renamer/backend/cache/classification_cache.py`
- Create: `smart_renamer/backend/cache/vision_cache.py`
- Create: `tests/test_backend_cache.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_cache.py`:

```python
from pathlib import Path
import tempfile
from smart_renamer.backend.cache.metadata_cache import MetadataCache
from smart_renamer.backend.cache.classification_cache import ClassificationCache
from smart_renamer.backend.cache.vision_cache import VisionCache


def test_metadata_cache_set_get():
    cache = MetadataCache()
    cache.put("/tmp/test.jpg", {"dimensions": "1920x1080", "size": 1024})
    result = cache.get("/tmp/test.jpg")
    assert result is not None
    assert result["dimensions"] == "1920x1080"


def test_metadata_cache_miss():
    cache = MetadataCache()
    assert cache.get("/tmp/nonexistent.jpg") is None


def test_metadata_cache_clear():
    cache = MetadataCache()
    cache.put("/tmp/a.jpg", {"dim": "1"})
    cache.put("/tmp/b.jpg", {"dim": "2"})
    cache.clear()
    assert cache.get("/tmp/a.jpg") is None
    assert cache.get("/tmp/b.jpg") is None


def test_classification_cache_set_get():
    cache = ClassificationCache()
    cache.put("/tmp/test.jpg", (["screenshot", "image"], 0.85))
    result = cache.get("/tmp/test.jpg")
    assert result is not None
    assert result[0] == ["screenshot", "image"]
    assert result[1] == 0.85


def test_classification_cache_miss():
    cache = ClassificationCache()
    assert cache.get("/tmp/unknown.jpg") is None


def test_vision_cache_disk(tmp_path):
    cache = VisionCache(cache_dir=tmp_path / "vision_cache")
    cache.put("/tmp/test.jpg", ["sunset", "beach", "ocean"])
    result = cache.get("/tmp/test.jpg")
    assert result is not None
    assert "sunset" in result
    assert "ocean" in result


def test_vision_cache_persists(tmp_path):
    cache_dir = tmp_path / "vision_cache"
    cache = VisionCache(cache_dir=cache_dir)
    cache.put("/tmp/test.jpg", ["mountain"])
    cache2 = VisionCache(cache_dir=cache_dir)
    result = cache2.get("/tmp/test.jpg")
    assert result == ["mountain"]


def test_vision_cache_clear(tmp_path):
    cache = VisionCache(cache_dir=tmp_path / "vision_cache")
    cache.put("/tmp/a.jpg", ["tag1"])
    cache.put("/tmp/b.jpg", ["tag2"])
    cache.clear()
    assert cache.get("/tmp/a.jpg") is None


def test_vision_cache_skip_non_images(tmp_path):
    cache = VisionCache(cache_dir=tmp_path / "vision_cache")
    cache.put("/tmp/test.txt", ["tag"])
    result = cache.get("/tmp/test.txt")
    assert result is None  # non-image files should be skipped
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_cache.py -v 2>&1
```
Expected: ModuleNotFoundError

- [ ] **Step 3: Write implementation**

Create `smart_renamer/backend/cache/__init__.py`:
```python
from .metadata_cache import MetadataCache
from .classification_cache import ClassificationCache
from .vision_cache import VisionCache

__all__ = ["MetadataCache", "ClassificationCache", "VisionCache"]
```

Create `smart_renamer/backend/cache/metadata_cache.py`:
```python
from __future__ import annotations
from typing import Any


class MetadataCache:
    """In-memory cache for file metadata, scoped to a session."""

    def __init__(self):
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, path: str) -> dict[str, Any] | None:
        return self._store.get(path)

    def put(self, path: str, metadata: dict[str, Any]) -> None:
        self._store[path] = metadata

    def clear(self) -> None:
        self._store.clear()
```

Create `smart_renamer/backend/cache/classification_cache.py`:
```python
from __future__ import annotations


class ClassificationCache:
    """In-memory cache for classifier results, scoped to a session."""

    def __init__(self):
        self._store: dict[str, tuple[list[str], float]] = {}

    def get(self, path: str) -> tuple[list[str], float] | None:
        return self._store.get(path)

    def put(self, path: str, tags: list[str], confidence: float) -> None:
        self._store[path] = (tags, confidence)

    def clear(self) -> None:
        self._store.clear()
```

Create `smart_renamer/backend/cache/vision_cache.py`:
```python
from __future__ import annotations
import hashlib
import json
from pathlib import Path


class VisionCache:
    """Persistent disk cache for Gemini Vision results, keyed by file hash."""

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or Path.home() / ".smart_renamer" / "vision_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._in_memory: dict[str, list[str]] = {}

    def _cache_key(self, filepath: Path) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            h.update(f.read(8192))
        return h.hexdigest()[:16]

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, path: str) -> list[str] | None:
        p = Path(path)
        if p.suffix.lower() not in self.IMAGE_EXTENSIONS:
            return None
        if path in self._in_memory:
            return self._in_memory[path]
        key = self._cache_key(p)
        cache_file = self._cache_path(key)
        if cache_file.exists():
            tags = json.loads(cache_file.read_text())
            self._in_memory[path] = tags
            return tags
        return None

    def put(self, path: str, tags: list[str]) -> None:
        p = Path(path)
        if p.suffix.lower() not in self.IMAGE_EXTENSIONS:
            return
        self._in_memory[path] = tags
        key = self._cache_key(p)
        self._cache_path(key).write_text(json.dumps(tags))

    def clear(self) -> None:
        self._in_memory.clear()
        for f in self.cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_cache.py -v 2>&1
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add smart_renamer/backend/cache/ tests/test_backend_cache.py
git commit -m "feat: add backend cache system (metadata, classification, vision)"
```

---

### Task 3: Vision Decision Engine

**Files:**
- Create: `smart_renamer/backend/brain/__init__.py`
- Create: `smart_renamer/backend/brain/vision_decision.py`
- Create: `tests/test_backend_vision_decision.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_vision_decision.py`:

```python
from smart_renamer.backend.brain.vision_decision import VisionDecisionEngine


def test_skips_high_confidence_known_type():
    """Skip vision when confidence >= threshold AND type is known."""
    engine = VisionDecisionEngine(confidence_threshold=0.7)
    assert engine.should_enrich(confidence=0.85, file_type="photo") is False
    assert engine.should_enrich(confidence=0.7, file_type="wallpaper") is True   # >= threshold, enrich
    assert engine.should_enrich(confidence=0.9, file_type="screenshot") is False


def test_enriches_low_confidence():
    """Enrich when confidence is below threshold."""
    engine = VisionDecisionEngine(confidence_threshold=0.7)
    assert engine.should_enrich(confidence=0.45, file_type="photo") is True
    assert engine.should_enrich(confidence=0.3, file_type="wallpaper") is True


def test_enriches_unknown_type():
    """Enrich when type is unknown regardless of confidence."""
    engine = VisionDecisionEngine(confidence_threshold=0.7)
    assert engine.should_enrich(confidence=0.95, file_type="unknown") is True


def test_enriches_no_exif_non_wallpaper():
    """Enrich when no EXIF data and type is not wallpaper."""
    engine = VisionDecisionEngine(confidence_threshold=0.7)
    assert engine.should_enrich(confidence=0.8, file_type="photo", has_exif=False) is True


def test_skips_no_exif_wallpaper():
    """Skip when no EXIF but type is wallpaper (wallpapers rarely have EXIF)."""
    engine = VisionDecisionEngine(confidence_threshold=0.7)
    assert engine.should_enrich(confidence=0.8, file_type="wallpaper", has_exif=False) is False


def test_custom_threshold():
    engine = VisionDecisionEngine(confidence_threshold=0.5)
    assert engine.should_enrich(confidence=0.55, file_type="photo") is False
    assert engine.should_enrich(confidence=0.45, file_type="photo") is True


def test_handles_video_and_audio():
    """Video and audio are always enriched since classifier is less reliable."""
    engine = VisionDecisionEngine(confidence_threshold=0.7)
    assert engine.should_enrich(confidence=0.9, file_type="video") is True
    assert engine.should_enrich(confidence=0.9, file_type="audio") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_vision_decision.py -v 2>&1
```
Expected: ModuleNotFoundError

- [ ] **Step 3: Write implementation**

Create `smart_renamer/backend/brain/__init__.py`:
```python
from .vision_decision import VisionDecisionEngine

__all__ = ["VisionDecisionEngine"]
```

Create `smart_renamer/backend/brain/vision_decision.py`:
```python
from __future__ import annotations

KNOWN_TYPES = {"wallpaper", "photo", "screenshot", "meme"}
MEDIA_TYPES = {"video", "audio"}


class VisionDecisionEngine:
    """Decides whether to call Gemini Vision for a given file.

    Rules:
    1. Confidence >= threshold AND type in known types -> skip
    2. Confidence < threshold -> enrich
    3. Type is "unknown" -> enrich
    4. No EXIF data AND type != wallpaper -> enrich (likely random image)
    5. Video/audio always enrich (classifier is less reliable)
    6. Otherwise -> skip
    """

    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold

    def should_enrich(
        self,
        confidence: float,
        file_type: str,
        has_exif: bool = False,
    ) -> bool:
        if file_type in MEDIA_TYPES:
            return True
        if file_type == "unknown":
            return True
        if confidence < self.confidence_threshold:
            return True
        if confidence >= self.confidence_threshold and file_type not in KNOWN_TYPES:
            return True
        if not has_exif and file_type != "wallpaper":
            return True
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_vision_decision.py -v 2>&1
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add smart_renamer/backend/brain/ tests/test_backend_vision_decision.py
git commit -m "feat: add VisionDecisionEngine with configurable rules"
```

---

### Task 4: Session Manager

**Files:**
- Create: `smart_renamer/backend/session.py`
- Create: `smart_renamer/backend/config.py` (wraps existing Config)
- Create: `tests/test_backend_session.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_session.py`:

```python
from pathlib import Path
from smart_renamer.backend.session import SessionManager
from smart_renamer.backend.models import SessionState


def test_create_session():
    mgr = SessionManager()
    session = mgr.create_session(directory=Path("/tmp"))
    assert session.state == SessionState.CREATED
    assert session.session_id.startswith("sess_")
    assert len(session.session_id) > 8


def test_get_session():
    mgr = SessionManager()
    created = mgr.create_session(directory=Path("/tmp"))
    fetched = mgr.get_session(created.session_id)
    assert fetched is not None
    assert fetched.session_id == created.session_id


def test_get_session_not_found():
    mgr = SessionManager()
    assert mgr.get_session("nonexistent") is None


def test_destroy_session():
    mgr = SessionManager()
    s = mgr.create_session(directory=Path("/tmp"))
    assert mgr.get_session(s.session_id) is not None
    mgr.destroy_session(s.session_id)
    assert mgr.get_session(s.session_id) is None


def test_transition_valid():
    mgr = SessionManager()
    s = mgr.create_session(directory=Path("/tmp"))
    mgr.transition(s.session_id, SessionState.LOADED)
    mgr.transition(s.session_id, SessionState.PLANNED)
    mgr.transition(s.session_id, SessionState.ENRICHED)
    assert mgr.get_session(s.session_id).state == SessionState.ENRICHED


def test_transition_invalid():
    mgr = SessionManager()
    s = mgr.create_session(directory=Path("/tmp"))
    from smart_renamer.backend.session import InvalidTransitionError
    try:
        mgr.transition(s.session_id, SessionState.EXECUTED)
        assert False, "Expected InvalidTransitionError"
    except InvalidTransitionError:
        pass


def test_transition_back_to_planned():
    mgr = SessionManager()
    s = mgr.create_session(directory=Path("/tmp"))
    mgr.transition(s.session_id, SessionState.LOADED)
    mgr.transition(s.session_id, SessionState.PLANNED)
    mgr.transition(s.session_id, SessionState.ENRICHED)
    # Can re-run plan
    mgr.transition(s.session_id, SessionState.PLANNED)
    assert mgr.get_session(s.session_id).state == SessionState.PLANNED


def test_destroy_unknown_does_not_raise():
    mgr = SessionManager()
    mgr.destroy_session("does_not_exist")


def test_multiple_sessions():
    mgr = SessionManager()
    s1 = mgr.create_session(directory=Path("/tmp/a"))
    s2 = mgr.create_session(directory=Path("/tmp/b"))
    assert s1.session_id != s2.session_id
    assert len(mgr.list_sessions()) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_session.py -v 2>&1
```
Expected: ModuleNotFoundError

- [ ] **Step 3: Write implementation**

Create `smart_renamer/backend/config.py`:
```python
from __future__ import annotations
from pathlib import Path
from smart_renamer.config import Config as BaseConfig


class BackendConfig(BaseConfig):
    """Extends base Config with backend-specific settings."""

    def __init__(self, config_path: Path | None = None):
        self.cache_ttl: int = 3600
        self.log_level: str = "INFO"
        self.vision_rate_limit: float = 10.0  # requests per minute
        super().__init__(config_path)

    def _parse(self, path: Path) -> None:
        import tomllib
        data = tomllib.loads(path.read_text())
        general = data.get("general", {})
        self.template = general.get("template", self.template)
        self.dry_run = general.get("dry_run", self.dry_run)
        self.recursive = general.get("recursive", self.recursive)
        backend = data.get("backend", {})
        self.cache_ttl = backend.get("cache_ttl", self.cache_ttl)
        self.log_level = backend.get("log_level", self.log_level)
        self.vision_rate_limit = backend.get("vision_rate_limit", self.vision_rate_limit)
        gemini = data.get("gemini", {})
        if gemini.get("enabled") is not None:
            self.gemini_enabled = gemini["enabled"]
        if gemini.get("confidence_threshold") is not None:
            self.confidence_threshold = gemini["confidence_threshold"]
        if gemini.get("api_key"):
            self.gemini_api_key = gemini["api_key"]
        if not self.gemini_api_key:
            import os
            self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
```

Create `smart_renamer/backend/session.py`:
```python
from __future__ import annotations
import uuid
from pathlib import Path
from smart_renamer.backend.models import Session, SessionState


VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.CREATED: {SessionState.LOADED},
    SessionState.LOADED: {SessionState.PLANNED},
    SessionState.PLANNED: {SessionState.ENRICHED, SessionState.VALIDATED},
    SessionState.ENRICHED: {SessionState.PLANNED, SessionState.VALIDATED},
    SessionState.VALIDATED: {SessionState.APPROVED, SessionState.PLANNED, SessionState.ENRICHED},
    SessionState.APPROVED: {SessionState.EXECUTED},
    SessionState.EXECUTED: {SessionState.APPROVED},  # undo
}


class InvalidTransitionError(Exception):
    pass


class SessionManager:
    """Manages session lifecycle and state transitions."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create_session(self, directory: Path, config_path: Path | None = None) -> Session:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        session = Session(session_id=session_id, directory=directory, config_path=config_path)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def destroy_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[Session]:
        return list(self._sessions.values())

    def transition(self, session_id: str, target: SessionState) -> None:
        session = self.get_session(session_id)
        if session is None:
            raise InvalidTransitionError(f"Session {session_id} not found")
        valid_targets = VALID_TRANSITIONS.get(session.state, set())
        if target not in valid_targets:
            raise InvalidTransitionError(
                f"Cannot transition from {session.state.value} to {target.value}. "
                f"Allowed: {[s.value for s in valid_targets]}"
            )
        session.state = target
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_session.py -v 2>&1
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add smart_renamer/backend/session.py smart_renamer/backend/config.py tests/test_backend_session.py
git commit -m "feat: add SessionManager with state machine and BackendConfig"
```

---

### Task 5: Backend Planner (Integration Layer)

**Files:**
- Create: `smart_renamer/backend/planner.py`
- Create: `tests/test_backend_planner.py`

This module wraps the existing `smart_renamer.brain.planner.Planner` and integrates the cache system + vision decision engine.

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_planner.py`:

```python
from pathlib import Path
from smart_renamer.backend.planner import BackendPlanner
from smart_renamer.backend.models import RenamePlan, RenamePlanState


def test_plan_returns_rename_plans(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_text("fake-image-data")
    planner = BackendPlanner()
    plans = planner.plan([f])
    assert len(plans) == 1
    plan = plans[0]
    assert plan.original_path == str(f)
    assert plan.proposed_name.endswith(".jpg")
    assert len(plan.tags) > 0
    assert plan.confidence > 0
    assert plan.state == RenamePlanState.PLANNED
    assert plan.reasoning != ""


def test_plan_multiple_files(tmp_path):
    files = []
    for i in range(5):
        f = tmp_path / f"img_{i}.jpg"
        f.write_text(f"fake-data-{i}")
        files.append(f)
    planner = BackendPlanner()
    plans = planner.plan(files)
    assert len(plans) == 5
    for plan in plans:
        assert plan.state == RenamePlanState.PLANNED


def test_enrich_with_decision(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_text("fake-image-data")
    planner = BackendPlanner()
    plans = planner.plan([f])

    class FakeVisionRouter:
        def is_available(self):
            return True
        def enrich(self, path):
            return ["sunset", "beach", "ocean"]

    decision_engine = type("FakeDecision", (), {"should_enrich": lambda self, **kw: True})()
    enriched = planner.enrich(plans, vision_router=FakeVisionRouter(), decision_engine=decision_engine)
    assert len(enriched) == 1
    plan = enriched[0]
    assert "sunset" in plan.tags
    assert plan.state == RenamePlanState.ENRICHED
    assert plan.confidence >= 0.8


def test_enrich_skips_non_images(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("text-data")
    planner = BackendPlanner()
    plans = planner.plan([f])
    assert len(plans) == 1

    class FakeVisionRouter:
        def is_available(self):
            return True
        def enrich(self, path):
            return ["some", "tags"]

    decision_engine = type("FakeDecision", (), {"should_enrich": lambda self, **kw: True})()
    enriched = planner.enrich(plans, vision_router=FakeVisionRouter(), decision_engine=decision_engine)
    plan = enriched[0]
    # non-image files won't have vision tags (vision_router.enrich skips non-images)
    assert plan.state == RenamePlanState.ENRICHED
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_planner.py -v 2>&1
```
Expected: ModuleNotFoundError

- [ ] **Step 3: Write implementation**

Create `smart_renamer/backend/planner.py`:
```python
from __future__ import annotations
from pathlib import Path
from smart_renamer.brain.planner import Planner
from smart_renamer.brain.metadata_extractor import MetadataExtractor
from smart_renamer.brain.classifier import Classifier
from smart_renamer.brain.template_engine import TemplateEngine
from smart_renamer.backend.models import RenamePlan, RenamePlanState
from smart_renamer.backend.cache import MetadataCache, ClassificationCache
from smart_renamer.backend.brain import VisionDecisionEngine


class BackendPlanner:
    """Integrates existing brain modules with caching and vision decision engine."""

    def __init__(
        self,
        template: str = "{tags}_{index}",
        confidence_threshold: float = 0.7,
    ):
        self._planner = Planner(template=template)
        self._metadata_extractor = MetadataExtractor()
        self._classifier = Classifier()
        self._template_engine = TemplateEngine(template)
        self._metadata_cache = MetadataCache()
        self._classification_cache = ClassificationCache()
        self._decision_engine = VisionDecisionEngine(
            confidence_threshold=confidence_threshold
        )

    def plan(self, file_paths: list[Path]) -> list[RenamePlan]:
        plans: list[RenamePlan] = []
        for idx, filepath in enumerate(file_paths, start=1):
            if not filepath.is_file():
                continue
            metadata = self._metadata_extractor.extract(filepath)
            self._metadata_cache.put(str(filepath), {
                "dimensions": f"{metadata.dimensions[0]}x{metadata.dimensions[1]}" if metadata.dimensions else "",
                "size": metadata.file_size,
                "camera": metadata.exif_camera or "",
                "date": metadata.exif_date_taken.isoformat() if metadata.exif_date_taken else "",
                "file_type": metadata.file_type,
            })
            classifier_tags, confidence = self._classifier.classify(metadata)
            self._classification_cache.put(str(filepath), classifier_tags, confidence)
            reasoning = f"Classifier: {', '.join(classifier_tags)} (confidence={confidence:.2f})"
            file_id = self._metadata_extractor.compute_file_id(filepath)
            date_str = metadata.exif_date_taken.strftime("%Y-%m-%d") if metadata.exif_date_taken else ""
            summary = self._planner._build_summary(metadata, classifier_tags)
            proposed = self._template_engine.generate(
                classifier_tags, idx, metadata.file_type, summary, date=date_str
            )
            plans.append(RenamePlan(
                file_id=file_id,
                original_path=str(filepath),
                proposed_name=proposed,
                tags=classifier_tags,
                confidence=round(confidence, 2),
                state=RenamePlanState.PLANNED,
                reasoning=reasoning,
            ))
        return plans

    def enrich(
        self,
        plans: list[RenamePlan],
        vision_router,
        decision_engine: VisionDecisionEngine | None = None,
    ) -> list[RenamePlan]:
        engine = decision_engine or self._decision_engine
        if not vision_router or not vision_router.is_available():
            for p in plans:
                p.state = RenamePlanState.ENRICHED
            return plans

        enriched: list[RenamePlan] = []
        for idx, plan in enumerate(plans, start=1):
            filepath = Path(plan.original_path)
            metadata = self._metadata_extractor.extract(filepath)
            has_exif = bool(metadata.exif_camera or metadata.exif_date_taken)
            file_type = next(
                (t for t in plan.tags if t in {"photo", "wallpaper", "screenshot", "meme", "video", "audio", "unknown"}),
                "unknown"
            )
            if not engine.should_enrich(
                confidence=plan.confidence,
                file_type=file_type,
                has_exif=has_exif,
            ):
                plan.state = RenamePlanState.ENRICHED
                enriched.append(plan)
                continue

            vision_tags = vision_router.enrich(filepath)
            if vision_tags:
                type_tag = next(
                    (t for t in plan.tags if t in {"photo", "wallpaper", "screenshot", "meme", "video", "audio"}),
                    None
                )
                if type_tag:
                    vision_tags.append(type_tag)
                date_str = metadata.exif_date_taken.strftime("%Y-%m-%d") if metadata.exif_date_taken else ""
                summary = self._planner._build_summary(metadata, vision_tags)
                proposed = self._template_engine.generate(
                    vision_tags, idx, metadata.file_type, summary, date=date_str
                )
                plan.tags = vision_tags
                plan.proposed_name = proposed
                plan.confidence = 0.85
                plan.reasoning = f"Vision: {', '.join(vision_tags)}"
            plan.state = RenamePlanState.ENRICHED
            enriched.append(plan)
        return enriched
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_planner.py -v 2>&1
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add smart_renamer/backend/planner.py tests/test_backend_planner.py
git commit -m "feat: add BackendPlanner with cache integration and vision decision"
```

---

### Task 6: Validator + Executor with Undo

**Files:**
- Create: `smart_renamer/backend/validator.py`
- Create: `smart_renamer/backend/executor.py`
- Create: `tests/test_backend_validator.py`
- Create: `tests/test_backend_executor.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_validator.py`:

```python
from smart_renamer.backend.validator import BackendValidator
from smart_renamer.backend.models import RenamePlan, Approval


def make_plan(file_id: str, name: str) -> RenamePlan:
    return RenamePlan(file_id=file_id, original_path=f"/tmp/{file_id}.jpg", proposed_name=name)


def test_validates_clean_plans():
    plans = [make_plan("a", "photo_01.jpg"), make_plan("b", "photo_02.jpg")]
    approvals = [Approval(file_id="a", approved=True), Approval(file_id="b", approved=True)]
    validator = BackendValidator()
    report = validator.validate(plans, approvals)
    assert report.valid is True
    assert len(report.conflicts) == 0


def test_detects_duplicate_names():
    plans = [make_plan("a", "photo_01.jpg"), make_plan("b", "photo_01.jpg")]
    approvals = [Approval(file_id="a"), Approval(file_id="b")]
    validator = BackendValidator()
    report = validator.validate(plans, approvals)
    assert report.valid is False
    assert len(report.conflicts) > 0
    assert any("duplicate" in c.get("reason", "").lower() for c in report.conflicts)


def test_detects_invalid_chars():
    plans = [make_plan("a", "photo<b>.jpg")]
    approvals = [Approval(file_id="a")]
    validator = BackendValidator()
    report = validator.validate(plans, approvals)
    assert report.valid is False


def test_detects_path_too_long():
    plans = [make_plan("a", "x" * 300 + ".jpg")]
    approvals = [Approval(file_id="a")]
    validator = BackendValidator()
    report = validator.validate(plans, approvals)
    assert report.valid is False


def test_skips_unapproved_plans():
    plans = [make_plan("a", "photo_01.jpg"), make_plan("b", "photo_02.jpg")]
    approvals = [Approval(file_id="a", approved=True), Approval(file_id="b", approved=False)]
    validator = BackendValidator()
    report = validator.validate(plans, approvals)
    assert report.valid is True
    assert len(plans) == 2  # unapproved plans are kept but not validated
```

Create `tests/test_backend_executor.py`:

```python
from pathlib import Path
from smart_renamer.backend.executor import BackendExecutor
from smart_renamer.backend.models import RenamePlan, RenamePlanState


def make_plan(file_id: str, src: Path, name: str) -> RenamePlan:
    return RenamePlan(
        file_id=file_id,
        original_path=str(src),
        proposed_name=name,
        state=RenamePlanState.APPROVED,
    )


def test_execute_success(tmp_path):
    src = tmp_path / "old.jpg"
    src.write_text("data")
    plan = make_plan("f1", src, "new.jpg")
    executor = BackendExecutor()
    results = executor.execute([plan], target_dir=tmp_path)
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].file_id == "f1"
    assert (tmp_path / "new.jpg").exists()
    assert not src.exists()


def test_execute_source_missing(tmp_path):
    src = tmp_path / "missing.jpg"
    plan = make_plan("f1", src, "new.jpg")
    executor = BackendExecutor()
    results = executor.execute([plan], target_dir=tmp_path)
    assert results[0].success is False
    assert "not found" in results[0].error.lower()


def test_execute_target_exists(tmp_path):
    src = tmp_path / "old.jpg"
    src.write_text("source-data")
    dst = tmp_path / "existing.jpg"
    dst.write_text("target-data")
    plan = make_plan("f1", src, "existing.jpg")
    executor = BackendExecutor()
    results = executor.execute([plan], target_dir=tmp_path)
    assert results[0].success is False
    assert "already exists" in results[0].error.lower()


def test_undo_restores_files(tmp_path):
    src = tmp_path / "old.jpg"
    src.write_text("data")
    plan = make_plan("f1", src, "new.jpg")
    executor = BackendExecutor()
    results = executor.execute([plan], target_dir=tmp_path)
    assert results[0].success is True
    assert (tmp_path / "new.jpg").exists()

    undone = executor.undo(results, target_dir=tmp_path)
    assert len(undone) == 1
    assert (tmp_path / "old.jpg").exists()
    assert not (tmp_path / "new.jpg").exists()


def test_undo_partial_failure(tmp_path):
    src1 = tmp_path / "old1.jpg"
    src1.write_text("data1")
    src2 = tmp_path / "old2.jpg"
    src2.write_text("data2")
    plan1 = make_plan("f1", src1, "new1.jpg")
    plan2 = make_plan("f2", src2, "new2.jpg")
    executor = BackendExecutor()

    # Simulate partial execution: first succeeds, second fails
    r1 = executor.execute([plan1], target_dir=tmp_path)
    # Manually remove target to simulate error
    (tmp_path / "new1.jpg").unlink()
    results = [r1[0], type("Res", (), {"file_id": "f2", "success": False, "old_path": str(src2), "new_path": str(tmp_path / "new2.jpg"), "error": "test"})()]

    undone = executor.undo(results, target_dir=tmp_path)
    assert (tmp_path / "old1.jpg").exists() or len(undone) > 0


def test_execute_writes_undo_log(tmp_path):
    src = tmp_path / "old.jpg"
    src.write_text("data")
    plan = make_plan("f1", src, "new.jpg")
    executor = BackendExecutor()
    executor.execute([plan], target_dir=tmp_path)

    undo_dir = Path.home() / ".smart_renamer" / "undo"
    assert undo_dir.exists()
    log_files = list(undo_dir.glob("*.json"))
    assert len(log_files) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_validator.py tests/test_backend_executor.py -v 2>&1
```
Expected: ModuleNotFoundError

- [ ] **Step 3: Write implementation**

Create `smart_renamer/backend/validator.py`:
```python
from __future__ import annotations
import re
from pathlib import Path
from smart_renamer.backend.models import RenamePlan, Approval, ValidationReport


INVALID_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*]')
RESERVED_NAMES = {"con", "prn", "aux", "nul", "com1", "com2", "com3", "com4",
                   "com5", "com6", "com7", "com8", "com9", "lpt1", "lpt2", "lpt3",
                   "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"}
MAX_PATH_LENGTH = 255


class BackendValidator:
    def validate(
        self,
        plans: list[RenamePlan],
        approvals: list[Approval],
    ) -> ValidationReport:
        conflicts: list[dict] = []
        warnings: list[str] = []
        approved_ids = {a.file_id for a in approvals if a.approved}
        approved_plans = [p for p in plans if p.file_id in approved_ids]

        if not approved_plans:
            return ValidationReport(valid=False, conflicts=[{
                "reason": "No plans approved",
                "file_ids": [],
                "proposed_name": "",
            }])

        proposed_names: dict[str, list[str]] = {}
        for p in approved_plans:
            name = p.proposed_name
            if name in proposed_names:
                conflicts.append({
                    "reason": f"Duplicate proposed name: {name}",
                    "file_ids": [*proposed_names[name], p.file_id],
                    "proposed_name": name,
                })
            proposed_names.setdefault(name, []).append(p.file_id)

            if INVALID_CHARS_PATTERN.search(name):
                conflicts.append({
                    "reason": f"Invalid characters in: {name}",
                    "file_ids": [p.file_id],
                    "proposed_name": name,
                })

            stem = Path(name).stem.lower()
            if stem in RESERVED_NAMES:
                conflicts.append({
                    "reason": f"Reserved name: {stem}",
                    "file_ids": [p.file_id],
                    "proposed_name": name,
                })

            if len(name) > MAX_PATH_LENGTH:
                conflicts.append({
                    "reason": f"Name exceeds {MAX_PATH_LENGTH} chars: {len(name)}",
                    "file_ids": [p.file_id],
                    "proposed_name": name,
                })

        return ValidationReport(
            valid=len(conflicts) == 0,
            conflicts=conflicts,
            warnings=warnings,
        )
```

Create `smart_renamer/backend/executor.py`:
```python
from __future__ import annotations
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from smart_renamer.backend.models import RenamePlan, ExecutionResult, UndoEntry


class BackendExecutor:
    def __init__(self):
        self._undo_dir = Path.home() / ".smart_renamer" / "undo"
        self._undo_dir.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        plans: list[RenamePlan],
        target_dir: Path,
        session_id: str = "",
    ) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        undo_entries: list[dict] = []

        for plan in plans:
            src = Path(plan.original_path)
            dst = target_dir / plan.proposed_name

            if not src.exists():
                results.append(ExecutionResult(
                    file_id=plan.file_id,
                    success=False,
                    old_path=str(src),
                    new_path=str(dst),
                    error=f"Source not found: {src}",
                ))
                continue

            if dst.exists():
                results.append(ExecutionResult(
                    file_id=plan.file_id,
                    success=False,
                    old_path=str(src),
                    new_path=str(dst),
                    error=f"Target already exists: {dst}",
                ))
                continue

            try:
                shutil.move(str(src), str(dst))
                results.append(ExecutionResult(
                    file_id=plan.file_id,
                    success=True,
                    old_path=str(src),
                    new_path=str(dst),
                ))
                undo_entries.append({"old_path": str(dst), "new_path": str(src)})
            except OSError as e:
                results.append(ExecutionResult(
                    file_id=plan.file_id,
                    success=False,
                    old_path=str(src),
                    new_path=str(dst),
                    error=str(e),
                ))

        # Write undo log
        if undo_entries:
            self._save_undo(session_id, undo_entries)

        return results

    def undo(
        self,
        results: list[ExecutionResult],
        target_dir: Path,
    ) -> list[UndoEntry]:
        undone: list[UndoEntry] = []
        successful = [r for r in results if r.success]

        for r in reversed(successful):
            src = Path(r.new_path)
            dst = Path(r.old_path)

            if not src.exists():
                continue

            try:
                shutil.move(str(src), str(dst))
                undone.append(UndoEntry(old_path=str(dst), new_path=str(src)))
            except OSError:
                pass

        return undone

    def _save_undo(self, session_id: str, entries: list[dict]) -> None:
        if not session_id:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            session_id = f"session_{ts}"
        log_file = self._undo_dir / f"{session_id}.json"
        log_file.write_text(json.dumps(entries, indent=2))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_validator.py tests/test_backend_executor.py -v 2>&1
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add smart_renamer/backend/validator.py smart_renamer/backend/executor.py tests/test_backend_validator.py tests/test_backend_executor.py
git commit -m "feat: add BackendValidator and BackendExecutor with undo support"
```

---

### Task 7: JSON-RPC Server

**Files:**
- Create: `smart_renamer/backend/server.py`
- Create: `tests/test_backend_server.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_server.py`:

```python
import json
import io
from pathlib import Path
from smart_renamer.backend.server import RPCServer, RPCHandler


def test_handle_request_invalid_json():
    handler = RPCHandler()
    result = handler.handle_line(b"not json\n")
    assert result is None  # invalid JSON returns None


def test_handle_request_missing_method():
    handler = RPCHandler()
    req = json.dumps({"id": "1", "method": "", "params": {}}) + "\n"
    result = handler.handle_line(req.encode())
    assert result is not None
    resp = json.loads(result.decode())
    assert resp["status"] == "error"
    assert resp["data"]["code"] == "INVALID_PARAMS"


def test_handle_unknown_method():
    handler = RPCHandler()
    req = json.dumps({"id": "1", "method": "nonexistent", "params": {}}) + "\n"
    result = handler.handle_line(req.encode())
    resp = json.loads(result.decode())
    assert resp["status"] == "error"
    assert resp["data"]["code"] == "UNKNOWN_METHOD"


def test_handle_session_create():
    handler = RPCHandler()
    req = json.dumps({
        "id": "1",
        "method": "session.create",
        "params": {"directory": "/tmp"},
    }) + "\n"
    result = handler.handle_line(req.encode())
    resp = json.loads(result.decode())
    assert resp["status"] == "ok"
    assert "session_id" in resp["data"]
    assert resp["data"]["state"] == "CREATED"


def test_handle_session_status():
    handler = RPCHandler()
    req1 = json.dumps({"id": "1", "method": "session.create", "params": {"directory": "/tmp"}}) + "\n"
    resp1 = json.loads(handler.handle_line(req1.encode()).decode())
    sid = resp1["data"]["session_id"]

    req2 = json.dumps({"id": "2", "method": "session.status", "params": {"session_id": sid}}) + "\n"
    resp2 = json.loads(handler.handle_line(req2.encode()).decode())
    assert resp2["status"] == "ok"
    assert resp2["data"]["state"] == "CREATED"


def test_handle_session_not_found():
    handler = RPCHandler()
    req = json.dumps({"id": "1", "method": "session.status", "params": {"session_id": "bad_id"}}) + "\n"
    resp = json.loads(handler.handle_line(req.encode()).decode())
    assert resp["status"] == "error"
    assert resp["data"]["code"] == "SESSION_NOT_FOUND"


def test_handle_plan(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_text("fake-data")
    handler = RPCHandler()
    req1 = json.dumps({"id": "1", "method": "session.create", "params": {"directory": str(tmp_path)}}) + "\n"
    resp1 = json.loads(handler.handle_line(req1.encode()).decode())
    sid = resp1["data"]["session_id"]

    req2 = json.dumps({"id": "2", "method": "plan", "params": {"session_id": sid}}) + "\n"
    resp2 = json.loads(handler.handle_line(req2.encode()).decode())
    assert resp2["status"] == "ok"
    assert len(resp2["data"]["plans"]) > 0


def test_rpc_server_reads_and_writes(tmp_path):
    f = tmp_path / "test.jpg"
    f.write_text("data")
    stdin = io.BytesIO()
    stdout = io.BytesIO()
    req = json.dumps({"id": "1", "method": "session.create", "params": {"directory": str(tmp_path)}}) + "\n"
    stdin.write(req.encode())
    stdin.seek(0)

    server = RPCServer(stdin=stdin, stdout=stdout)
    server.run(max_requests=1)
    output = stdout.getvalue()
    resp = json.loads(output.strip())
    assert resp["status"] == "ok"
    assert "session_id" in resp["data"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_server.py -v 2>&1
```
Expected: ModuleNotFoundError

- [ ] **Step 3: Write implementation**

Create `smart_renamer/backend/server.py`:
```python
from __future__ import annotations
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from smart_renamer.backend.models import RPCRequest, RPCResponse, SessionState, Approval
from smart_renamer.backend.session import SessionManager, InvalidTransitionError
from smart_renamer.backend.config import BackendConfig
from smart_renamer.backend.planner import BackendPlanner
from smart_renamer.backend.validator import BackendValidator
from smart_renamer.backend.executor import BackendExecutor
from smart_renamer.brain.vision_router import VisionRouter


MethodHandler = Callable[[dict[str, Any]], dict[str, Any]]


class RPCHandler:
    def __init__(self):
        self._session_mgr = SessionManager()
        self._config: BackendConfig | None = None
        self._planner: BackendPlanner | None = None
        self._validator = BackendValidator()
        self._executor = BackendExecutor()
        self._vision_router: VisionRouter | None = None

        self._methods: dict[str, MethodHandler] = {
            "session.create": self._handle_session_create,
            "session.destroy": self._handle_session_destroy,
            "session.status": self._handle_session_status,
            "plan": self._handle_plan,
            "enrich": self._handle_enrich,
            "validate": self._handle_validate,
            "execute": self._handle_execute,
            "undo": self._handle_undo,
            "preview": self._handle_preview,
        }

    def handle_line(self, data: bytes) -> bytes | None:
        try:
            raw = json.loads(data.decode().strip())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        req = RPCRequest(**raw)
        if not req.method:
            return self._error(req.id, "INVALID_PARAMS", "method is required")

        handler = self._methods.get(req.method)
        if handler is None:
            return self._error(req.id, "UNKNOWN_METHOD", f"Unknown method: {req.method}")

        try:
            result = handler(req.params)
            return self._ok(req.id, result)
        except InvalidTransitionError as e:
            return self._error(req.id, "INVALID_STATE", str(e))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            return self._error(req.id, "INTERNAL_ERROR", str(e))

    def _ok(self, id: str, data: dict[str, Any]) -> bytes:
        return json.dumps({"id": id, "status": "ok", "data": data}).encode() + b"\n"

    def _error(self, id: str, code: str, message: str) -> bytes:
        return json.dumps({
            "id": id,
            "status": "error",
            "data": {"code": code, "message": message},
        }).encode() + b"\n"

    def _get_session(self, params: dict[str, Any]) -> tuple:
        sid = params.get("session_id", "")
        session = self._session_mgr.get_session(sid)
        if session is None:
            raise InvalidTransitionError(f"Session {sid} not found")
        config = self._load_config(session.config_path)
        return session, config

    def _load_config(self, config_path: Path | None = None) -> BackendConfig:
        if self._config is not None and config_path is None:
            return self._config
        cfg = BackendConfig(config_path)
        if config_path is None:
            self._config = cfg
        return cfg

    def _get_planner(self, config: BackendConfig) -> BackendPlanner:
        if self._planner is None:
            self._planner = BackendPlanner(
                template=config.template,
                confidence_threshold=config.confidence_threshold,
            )
        return self._planner

    def _get_vision_router(self, config: BackendConfig) -> VisionRouter | None:
        if self._vision_router is None and config.gemini_enabled and config.gemini_api_key:
            self._vision_router = VisionRouter(api_key=config.gemini_api_key)
        return self._vision_router if config.gemini_enabled else None

    def _handle_session_create(self, params: dict[str, Any]) -> dict[str, Any]:
        directory = Path(params["directory"])
        config_path = Path(params["config_path"]) if params.get("config_path") else None
        session = self._session_mgr.create_session(directory, config_path)

        # Load and fingerprint
        session.file_count = len([
            f for f in sorted(directory.iterdir())
            if f.is_file() and f.suffix.lower() in {
                ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
                ".mp4", ".mov", ".avi", ".mkv",
                ".mp3", ".wav", ".flac",
            }
        ])
        self._session_mgr.transition(session.session_id, SessionState.LOADED)

        return session.get_status()

    def _handle_session_destroy(self, params: dict[str, Any]) -> dict[str, Any]:
        sid = params.get("session_id", "")
        self._session_mgr.destroy_session(sid)
        return {}

    def _handle_session_status(self, params: dict[str, Any]) -> dict[str, Any]:
        session, _ = self._get_session(params)
        return session.get_status()

    def _handle_plan(self, params: dict[str, Any]) -> dict[str, Any]:
        session, config = self._get_session(params)
        directory = session.directory
        files = sorted(directory.iterdir())
        files = [f for f in files if f.is_file() and f.suffix.lower() in {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
            ".mp4", ".mov", ".avi", ".mkv",
            ".mp3", ".wav", ".flac",
        }]

        planner = self._get_planner(config)
        plans = planner.plan(files)
        session.plans = plans
        self._session_mgr.transition(session.session_id, SessionState.PLANNED)

        return {
            "plans": [p.model_dump() for p in plans],
        }

    def _handle_enrich(self, params: dict[str, Any]) -> dict[str, Any]:
        session, config = self._get_session(params)
        planner = self._get_planner(config)
        vr = self._get_vision_router(config)

        file_ids = params.get("file_ids")
        targets = [p for p in session.plans if file_ids is None or p.file_id in file_ids]

        enriched = planner.enrich(targets, vr)
        self._session_mgr.transition(session.session_id, SessionState.ENRICHED)

        return {
            "plans": [p.model_dump() for p in enriched],
            "enriched_count": len(enriched),
        }

    def _handle_validate(self, params: dict[str, Any]) -> dict[str, Any]:
        session, _ = self._get_session(params)
        approvals_data = params.get("approvals", [])
        approvals = [Approval(**a) for a in approvals_data]

        report = self._validator.validate(session.plans, approvals)
        return report.model_dump()

    def _handle_execute(self, params: dict[str, Any]) -> dict[str, Any]:
        session, _ = self._get_session(params)
        self._session_mgr.transition(session.session_id, SessionState.APPROVED)
        approved = [p for p in session.plans]
        results = self._executor.execute(approved, session.directory, session.session_id)
        self._session_mgr.transition(session.session_id, SessionState.EXECUTED)

        return {
            "results": [r.model_dump() for r in results],
        }

    def _handle_undo(self, params: dict[str, Any]) -> dict[str, Any]:
        session, _ = self._get_session(params)
        results_data = params.get("results", [])
        from smart_renamer.backend.models import ExecutionResult
        results = [ExecutionResult(**r) for r in results_data]

        undone = self._executor.undo(results, session.directory)
        self._session_mgr.transition(session.session_id, SessionState.APPROVED)

        return {
            "undone_count": len(undone),
            "entries": [u.model_dump() for u in undone],
        }

    def _handle_preview(self, params: dict[str, Any]) -> dict[str, Any]:
        session, _ = self._get_session(params)
        file_id = params.get("file_id", "")
        plan = next((p for p in session.plans if p.file_id == file_id), None)
        if plan is None:
            return {}

        width = params.get("width", 40)
        height = params.get("height", 20)

        try:
            from PIL import Image
            img = Image.open(plan.original_path)
            img = img.resize((width, height))
            img = img.convert("L")  # grayscale
            ramp = " .:-=+*#%@"
            pixels = img.getdata()
            ascii_rows = []
            for y in range(height):
                row = ""
                for x in range(width):
                    idx = pixels[y * width + x] * (len(ramp) - 1) // 255
                    row += ramp[min(idx, len(ramp) - 1)]
                ascii_rows.append(row)
            ascii_art = "\n".join(ascii_rows)
            return {
                "ascii": ascii_art,
                "dimensions": f"{img.size[0]}x{img.size[1]}",
                "file_size": f"{Path(plan.original_path).stat().st_size / 1024:.0f}KB",
            }
        except Exception:
            return {
                "ascii": "",
                "dimensions": "",
                "file_size": "",
            }


class RPCServer:
    def __init__(self, stdin=None, stdout=None):
        self._stdin = stdin or sys.stdin.buffer
        self._stdout = stdout or sys.stdout.buffer
        self._handler = RPCHandler()

    def run(self, max_requests: int | None = None) -> None:
        requests_handled = 0
        for line in self._stdin:
            if not line.strip():
                continue
            response = self._handler.handle_line(line)
            if response is not None:
                self._stdout.write(response)
                self._stdout.flush()
            requests_handled += 1
            if max_requests is not None and requests_handled >= max_requests:
                break
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/test_backend_server.py -v 2>&1
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add smart_renamer/backend/server.py tests/test_backend_server.py
git commit -m "feat: add JSON-RPC server with session/plan/enrich/validate/execute/undo/preview methods"
```

---

### Task 8: Backend Entry Point

**Files:**
- Create: `smart_renamer/backend/__main__.py`

- [ ] **Step 1: Write implementation**

Create `smart_renamer/backend/__main__.py`:
```python
"""
SmartRenamer Backend Server

Run: python -m smart_renamer.backend
Reads JSON-RPC 2.0 requests from stdin, writes responses to stdout.
Errors go to stderr as plain text.
"""
from __future__ import annotations
import sys
import signal
from smart_renamer.backend.server import RPCServer


def main():
    # Handle graceful shutdown
    server = RPCServer()

    def shutdown(signum, frame):
        sys.stderr.write("\nShutting down SmartRenamer backend...\n")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        server.run()
    except BrokenPipeError:
        # TUI disconnected
        sys.stderr.write("Backend: TUI disconnected\n")
        sys.exit(0)
    except KeyboardInterrupt:
        sys.stderr.write("Backend: shutdown by interrupt\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Quick smoke test**

```bash
echo '{"id":"1","method":"session.create","params":{"directory":"/tmp"}}' | PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m smart_renamer.backend 2>/dev/null
```
Expected: `{"id":"1","status":"ok","data":{"state":"LOADED","file_count":0,"enriched_count":0}}`

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/backend/__main__.py
git commit -m "feat: add backend entry point (python -m smart_renamer.backend)"
```

---

### Task 9: Run All Backend Tests

- [ ] **Step 1: Run full test suite**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/ -v 2>&1
```
Expected: ~60+ tests, all PASS

- [ ] **Step 2: If any fail, fix and re-run**

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: all backend tests passing"
```

---

### Task 10: Scaffold OpenTUI Project

**Files:**
- Create: `smart_renamer/tui/package.json`
- Create: `smart_renamer/tui/tsconfig.json`
- Create: `smart_renamer/tui/src/index.tsx`

- [ ] **Step 1: Scaffold directory and config**

```bash
mkdir -p /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui/src/rpc
mkdir -p /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui/src/components
mkdir -p /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui/src/state
```

Create `smart_renamer/tui/package.json`:
```json
{
  "name": "smart-renamer-tui",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "bun run src/index.tsx",
    "start": "bun run src/index.tsx"
  },
  "dependencies": {
    "@opentui/core": "^0.0.25",
    "@opentui/react": "^0.0.23",
    "react": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "typescript": "^5.4.0"
  }
}
```

Create `smart_renamer/tui/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

Create `smart_renamer/tui/src/index.tsx`:
```tsx
import { createCliRenderer } from "@opentui/core"
import { createRoot } from "@opentui/react"
import { App } from "./components/App"

async function main() {
  const renderer = await createCliRenderer({
    exitOnCtrlC: false,
  })

  const root = createRoot(renderer)
  root.render(<App />)
}

main().catch((err) => {
  console.error("Fatal error:", err)
  process.exit(1)
})
```

- [ ] **Step 2: Install dependencies**

```bash
cd /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui && bun install 2>&1
```
Expected: bun installs all dependencies

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/tui/
git commit -m "feat: scaffold OpenTUI project with package.json and entry point"
```

---

### Task 11: RPC Client (TypeScript)

**Files:**
- Create: `smart_renamer/tui/src/rpc/types.ts`
- Create: `smart_renamer/tui/src/rpc/client.ts`

- [ ] **Step 1: Write types**

Create `smart_renamer/tui/src/rpc/types.ts`:
```typescript
export interface RPCRequest {
  id: string
  method: string
  params: Record<string, unknown>
  jsonrpc: string
}

export interface RPCResponse {
  id: string
  status: "ok" | "error"
  data: Record<string, unknown>
}

export interface RenamePlan {
  file_id: string
  original_path: string
  proposed_name: string
  tags: string[]
  confidence: number
  state: string
  reasoning: string
}

export interface SessionStatus {
  state: string
  file_count: number
  enriched_count: number
}

export interface ValidationReport {
  valid: boolean
  conflicts: Array<{ reason: string; file_ids: string[]; proposed_name: string }>
  warnings: string[]
}

export interface ExecutionResult {
  file_id: string
  success: boolean
  old_path: string
  new_path: string
  error: string
}

export interface PreviewData {
  ascii: string
  dimensions: string
  file_size: string
}

export interface Approval {
  file_id: string
  approved: boolean
  custom_name?: string
}
```

Create `smart_renamer/tui/src/rpc/client.ts`:
```typescript
import type { RPCResponse, RenamePlan, SessionStatus, ValidationReport, ExecutionResult, PreviewData, Approval } from "./types"

let requestId = 0

function nextId(): string {
  return String(++requestId)
}

export class RPCClient {
  private process: Deno.ChildProcess | null = null
  private stdin: WritableStream<Uint8Array> | null = null
  private reader: ReadableStreamDefaultReader<Uint8Array> | null = null
  private buffer: string = ""
  private pending = new Map<string, { resolve: (data: unknown) => void; reject: (err: Error) => void }>()

  async start(pythonCmd: string[]): Promise<void> {
    const cmd = new Deno.Command(pythonCmd[0], {
      args: pythonCmd.slice(1),
      stdin: "piped",
      stdout: "piped",
      stderr: "piped",
    })
    this.process = cmd.spawn()
    this.stdin = this.process.stdin
    this.reader = this.process.stdout.getReader()

    this._readLoop()
  }

  private async _readLoop(): Promise<void> {
    const decoder = new TextDecoder()
    while (this.reader) {
      const { done, value } = await this.reader.read()
      if (done) break

      this.buffer += decoder.decode(value, { stream: true })
      const lines = this.buffer.split("\n")
      this.buffer = lines.pop() || ""

      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const resp: RPCResponse = JSON.parse(line)
          const p = this.pending.get(resp.id)
          if (p) {
            this.pending.delete(resp.id)
            if (resp.status === "ok") {
              p.resolve(resp.data)
            } else {
              p.reject(new Error(String(resp.data?.message || "RPC error")))
            }
          }
        } catch {
          // skip malformed lines
        }
      }
    }
  }

  async request(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    return new Promise((resolve, reject) => {
      const id = nextId()
      this.pending.set(id, { resolve, reject })

      const req = JSON.stringify({ id, method, params, jsonrpc: "2.0" }) + "\n"
      const encoder = new TextEncoder()
      this.stdin!.write(encoder.encode(req))
    })
  }

  // ---- High-level API ----

  async createSession(directory: string, configPath?: string): Promise<SessionStatus> {
    return (await this.request("session.create", { directory, config_path: configPath })) as SessionStatus
  }

  async getSessionStatus(sessionId: string): Promise<SessionStatus> {
    return (await this.request("session.status", { session_id: sessionId })) as SessionStatus
  }

  async destroySession(sessionId: string): Promise<void> {
    await this.request("session.destroy", { session_id: sessionId })
  }

  async plan(sessionId: string): Promise<{ plans: RenamePlan[] }> {
    return (await this.request("plan", { session_id: sessionId })) as { plans: RenamePlan[] }
  }

  async enrich(sessionId: string, fileIds?: string[]): Promise<{ plans: RenamePlan[]; enriched_count: number }> {
    const params: Record<string, unknown> = { session_id: sessionId }
    if (fileIds) params.file_ids = fileIds
    return (await this.request("enrich", params)) as { plans: RenamePlan[]; enriched_count: number }
  }

  async validate(sessionId: string, approvals: Approval[]): Promise<ValidationReport> {
    return (await this.request("validate", { session_id: sessionId, approvals })) as ValidationReport
  }

  async execute(sessionId: string): Promise<{ results: ExecutionResult[] }> {
    return (await this.request("execute", { session_id: sessionId })) as { results: ExecutionResult[] }
  }

  async undo(sessionId: string, results: ExecutionResult[]): Promise<{ undone_count: number }> {
    return (await this.request("undo", { session_id: sessionId, results })) as { undone_count: number }
  }

  async preview(sessionId: string, fileId: string): Promise<PreviewData> {
    return (await this.request("preview", { session_id: sessionId, file_id: fileId })) as PreviewData
  }

  stop(): void {
    this.process?.kill("SIGTERM")
    this.reader?.cancel()
  }
}
```

- [ ] **Step 2: No test for this task (TypeScript compilation is the check)**

```bash
cd /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui && bun run src/index.tsx 2>&1 &
bun_pid=$!
sleep 2
kill $bun_pid 2>/dev/null
wait $bun_pid 2>/dev/null
```
Expected: Compiles and starts without TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/tui/src/rpc/
git commit -m "feat: add TypeScript RPC client with high-level API"
```

---

### Task 12: TUI State Store

**Files:**
- Create: `smart_renamer/tui/src/state/store.ts`

- [ ] **Step 1: Write the store**

Create `smart_renamer/tui/src/state/store.ts`:
```typescript
import type { RenamePlan, ExecutionResult, SessionStatus, ValidationReport, PreviewData } from "../rpc/types"

export interface TUIState {
  // Session
  sessionId: string
  sessionStatus: SessionStatus | null
  directory: string

  // Plans
  plans: RenamePlan[]
  enrichedCount: number

  // Approvals (file_id -> approved)
  approvals: Record<string, boolean>

  // Names (file_id -> user-edited name override)
  editedNames: Record<string, string>

  // UI
  selectedIndex: number
  previewData: PreviewData | null
  previewLoading: boolean
  statusMessage: string
  validationReport: ValidationReport | null
  executionResults: ExecutionResult[] | null

  // Loading states
  loading: boolean
  enriching: boolean
  executing: boolean
}

export function createInitialState(directory: string): TUIState {
  return {
    sessionId: "",
    sessionStatus: null,
    directory,
    plans: [],
    enrichedCount: 0,
    approvals: {},
    editedNames: {},
    selectedIndex: 0,
    previewData: null,
    previewLoading: false,
    statusMessage: "Starting...",
    validationReport: null,
    executionResults: null,
    loading: true,
    enriching: false,
    executing: false,
  }
}

export function toggleApproval(state: TUIState, fileId: string): TUIState {
  return {
    ...state,
    approvals: {
      ...state.approvals,
      [fileId]: !state.approvals[fileId],
    },
  }
}

export function approveAll(state: TUIState): TUIState {
  const approvals: Record<string, boolean> = {}
  for (const p of state.plans) {
    approvals[p.file_id] = true
  }
  return { ...state, approvals }
}

export function setEditedName(state: TUIState, fileId: string, name: string): TUIState {
  return {
    ...state,
    editedNames: { ...state.editedNames, [fileId]: name },
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui && bun x tsc --noEmit 2>&1
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/tui/src/state/
git commit -m "feat: add TUI state store with approval management"
```

---

### Task 13: App Shell + Main Layout

**Files:**
- Create: `smart_renamer/tui/src/components/App.tsx`

- [ ] **Step 1: Write App component**

Create `smart_renamer/tui/src/components/App.tsx`:
```tsx
import { useState, useEffect, useCallback } from "react"
import { useKeyboard, useRenderer } from "@opentui/react"
import { RPCClient } from "../rpc/client"
import { createInitialState, TUIState, toggleApproval, approveAll } from "../state/store"
import { FileGrid } from "./FileGrid"
import { PreviewPanel } from "./PreviewPanel"
import { Controls } from "./Controls"
import { StatusBar } from "./StatusBar"
import type { Approval } from "../rpc/types"

const TARGET_DIR = process.argv[2] || process.cwd()

export function App() {
  const renderer = useRenderer()
  const [state, setState] = useState<TUIState>(() => createInitialState(TARGET_DIR))
  const rpcRef = useState<RPCClient | null>(null)

  // Initialize: spawn backend, create session, plan
  useEffect(() => {
    const rpc = new RPCClient()
    rpcRef[1](rpc)

    const pythonCmd = [
      "python3",
      "-m", "smart_renamer.backend",
    ]

    async function init() {
      try {
        await rpc.start(pythonCmd)
        setState(s => ({ ...s, statusMessage: "Creating session..." }))

        const status = await rpc.createSession(TARGET_DIR)
        setState(s => ({
          ...s,
          sessionId: (status as unknown as { session_id: string }).session_id || "sess_1",
          sessionStatus: status,
          statusMessage: `Scanning ${status.file_count} files...`,
        }))

        setState(s => ({ ...s, statusMessage: "Planning..." }))
        const planResult = await rpc.plan(s.sessionId) as unknown as { plans: any[] }
        const plans = planResult.plans
        const approvals: Record<string, boolean> = {}
        for (const p of plans) {
          approvals[p.file_id] = true
        }

        setState(s => ({
          ...s,
          plans,
          approvals,
          loading: false,
          statusMessage: `Ready — ${plans.length} files`,
        }))

        // Start enrichment
        if (plans.length > 0) {
          setState(s => ({ ...s, enriching: true, statusMessage: "Enriching with AI..." }))
          const enrichResult = await rpc.enrich(s.sessionId) as unknown as { plans: any[]; enriched_count: number }
          setState(s => ({
            ...s,
            plans: enrichResult.plans,
            enrichedCount: enrichResult.enriched_count,
            enriching: false,
            statusMessage: `Ready — ${enrichResult.enriched_count} enriched`,
          }))
        }
      } catch (err) {
        setState(s => ({
          ...s,
          loading: false,
          statusMessage: `Error: ${err instanceof Error ? err.message : String(err)}`,
        }))
      }
    }

    init()

    return () => {
      rpc.stop()
    }
  }, [])

  // Keyboard handling
  useKeyboard((key) => {
    if (key.name === "escape" || (key.ctrl && key.name === "c")) {
      rpcRef[0]?.stop()
      renderer.destroy()
      return
    }

    if (key.name === "q") {
      rpcRef[0]?.stop()
      renderer.destroy()
      return
    }

    if (!state.loading && !state.executing) {
      if (key.name === "j" || key.name === "down") {
        setState(s => ({
          ...s,
          selectedIndex: Math.min(s.plans.length - 1, s.selectedIndex + 1),
          previewData: null,
          previewLoading: true,
        }))
        return
      }

      if (key.name === "k" || key.name === "up") {
        setState(s => ({
          ...s,
          selectedIndex: Math.max(0, s.selectedIndex - 1),
          previewData: null,
          previewLoading: true,
        }))
        return
      }

      if (key.name === "space") {
        const plan = state.plans[state.selectedIndex]
        if (plan) {
          setState(s => toggleApproval(s, plan.file_id))
        }
        return
      }

      if (key.name === "a") {
        setState(s => approveAll(s))
        return
      }

      if (key.name === "r") {
        setState(s => ({
          ...s,
          approvals: {},
        }))
        return
      }

      if (key.name === "e") {
        handleExecute()
        return
      }
    }
  })

  // Load preview when selected index changes
  useEffect(() => {
    const plan = state.plans[state.selectedIndex]
    if (!plan || !state.sessionId) return

    setState(s => ({ ...s, previewLoading: true }))

    rpcRef[0]?.preview(state.sessionId, plan.file_id).then((data) => {
      setState(s => ({ ...s, previewData: data as any, previewLoading: false }))
    }).catch(() => {
      setState(s => ({ ...s, previewLoading: false }))
    })
  }, [state.selectedIndex, state.sessionId])

  const handleExecute = useCallback(async () => {
    if (!state.sessionId || state.executing) return

    const approvals: Approval[] = state.plans.map(p => ({
      file_id: p.file_id,
      approved: state.approvals[p.file_id] ?? false,
      custom_name: state.editedNames[p.file_id],
    }))

    setState(s => ({ ...s, executing: true, statusMessage: "Validating..." }))

    try {
      const rpc = rpcRef[0]!
      const validationResult = await rpc.validate(state.sessionId, approvals) as any
      setState(s => ({ ...s, validationReport: validationResult }))

      if (!validationResult.valid) {
        setState(s => ({
          ...s,
          executing: false,
          statusMessage: `Validation failed — ${validationResult.conflicts?.length || 0} conflicts`,
        }))
        return
      }

      setState(s => ({ ...s, statusMessage: "Executing..." }))
      const execResult = await rpc.execute(state.sessionId) as any
      setState(s => ({
        ...s,
        executionResults: execResult.results,
        executing: false,
        statusMessage: `Done — ${execResult.results.filter((r: any) => r.success).length} renamed`,
      }))
    } catch (err) {
      setState(s => ({
        ...s,
        executing: false,
        statusMessage: `Error: ${err instanceof Error ? err.message : String(err)}`,
      }))
    }
  }, [state.sessionId, state.executing, state.plans, state.approvals, state.editedNames])

  const selectedPlan = state.plans[state.selectedIndex]

  return (
    <box flexDirection="column" height="100%">
      <box border borderStyle="rounded" paddingX={1} height={1}>
        <text>
          <strong>SmartRenamer</strong>
          {" "}<span dim>{state.sessionStatus ? `[${state.sessionStatus.state}]` : "[connecting]"}</span>
          {" "}<span dim>{state.plans.length} files</span>
          {" "}{state.enrichedCount > 0 ? <span fg="green">[AI]</span> : null}
        </text>
      </box>

      <box flexGrow={1} flexDirection="row">
        <box flexGrow={2} border borderStyle="rounded">
          <FileGrid
            plans={state.plans}
            approvals={state.approvals}
            selectedIndex={state.selectedIndex}
            loading={state.loading}
          />
        </box>
        <box width={35} border borderStyle="rounded" padding={1}>
          <PreviewPanel
            plan={selectedPlan || null}
            previewData={state.previewData}
            loading={state.previewLoading}
          />
        </box>
      </box>

      <box height={3} paddingX={1} flexDirection="row" gap={2}>
        <Controls onExecute={handleExecute} executing={state.executing} />
      </box>

      <StatusBar message={state.statusMessage} />
    </box>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui && bun x tsc --noEmit 2>&1
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/tui/src/components/App.tsx
git commit -m "feat: add App shell with keyboard handling and init flow"
```

---

### Task 14: FileGrid Component

**Files:**
- Create: `smart_renamer/tui/src/components/FileGrid.tsx`

- [ ] **Step 1: Write FileGrid**

Create `smart_renamer/tui/src/components/FileGrid.tsx`:
```tsx
import type { RenamePlan } from "../rpc/types"

interface FileGridProps {
  plans: RenamePlan[]
  approvals: Record<string, boolean>
  selectedIndex: number
  loading: boolean
}

export function FileGrid({ plans, approvals, selectedIndex, loading }: FileGridProps) {
  if (loading) {
    return (
      <box height="100%" justifyContent="center" alignItems="center">
        <text>Loading...</text>
      </box>
    )
  }

  if (plans.length === 0) {
    return (
      <box height="100%" justifyContent="center" alignItems="center">
        <text dim>No files found</text>
      </box>
    )
  }

  return (
    <scrollbox focused height="100%">
      {/* Column headers */}
      <box flexDirection="row" paddingX={1}>
        <text width={3}><strong>✓</strong></text>
        <text width={28}><strong>Original</strong></text>
        <text width={38}><strong>Proposed</strong></text>
        <text width={8}><strong>Conf</strong></text>
        <text width={20}><strong>Tags</strong></text>
      </box>
      <box height={1} /> {/* spacer */}

      {/* File rows */}
      {plans.map((plan, i) => {
        const isSelected = i === selectedIndex
        const approved = approvals[plan.file_id] ?? false
        const bgColor = isSelected ? "#335577" : undefined
        const confColor = plan.confidence > 0.7 ? "green" : plan.confidence > 0.4 ? "yellow" : "red"

        return (
          <box key={plan.file_id} flexDirection="row" paddingX={1} backgroundColor={bgColor}>
            <text width={3}>{approved ? <span fg="green">✓</span> : " "}</text>
            <text width={28} dim={!approved}>
              {plan.original_path.split("/").pop() || plan.original_path}
            </text>
            <text width={38} fg={approved ? "#FFFFFF" : "#888888"}>
              {plan.proposed_name}
            </text>
            <text width={8} fg={confColor}>
              {Math.round(plan.confidence * 100)}%
            </text>
            <text width={20} dim>
              {plan.tags.slice(0, 2).join(", ")}
            </text>
          </box>
        )
      })}
    </scrollbox>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui && bun x tsc --noEmit 2>&1
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/tui/src/components/FileGrid.tsx
git commit -m "feat: add FileGrid component with selection and approval display"
```

---

### Task 15: PreviewPanel + ImagePreview

**Files:**
- Create: `smart_renamer/tui/src/components/PreviewPanel.tsx`

- [ ] **Step 1: Write PreviewPanel**

Create `smart_renamer/tui/src/components/PreviewPanel.tsx`:
```tsx
import type { RenamePlan, PreviewData } from "../rpc/types"

interface PreviewPanelProps {
  plan: RenamePlan | null
  previewData: PreviewData | null
  loading: boolean
}

export function PreviewPanel({ plan, previewData, loading }: PreviewPanelProps) {
  if (!plan) {
    return (
      <box height="100%" justifyContent="center" alignItems="center">
        <text dim>Select a file to preview</text>
      </box>
    )
  }

  return (
    <box flexDirection="column" height="100%">
      {/* ASCII Image Preview */}
      <box
        border
        borderStyle="rounded"
        height={14}
        justifyContent="center"
        alignItems="center"
        padding={1}
      >
        {loading ? (
          <text dim>Loading preview...</text>
        ) : previewData?.ascii ? (
          <text>
            {previewData.ascii.split("\n").map((line, i) => (
              <span key={i}>{line}<br /></span>
            ))}
          </text>
        ) : (
          <text dim>No preview available</text>
        )}
      </box>

      {/* Metadata / Details */}
      <box flexDirection="column" paddingY={1}>
        <text><span dim>Old: </span>{plan.original_path.split("/").pop()}</text>
        <text><span dim>New: </span>
          <span fg={plan.confidence > 0.7 ? "green" : "yellow"}>
            {plan.proposed_name}
          </span>
        </text>
        <text><span dim>Tags: </span>{plan.tags.join(", ")}</text>
        <text>
          <span dim>Confidence: </span>
          <span fg={plan.confidence > 0.7 ? "green" : plan.confidence > 0.4 ? "yellow" : "red"}>
            {Math.round(plan.confidence * 100)}%
          </span>
        </text>
        {previewData && (
          <>
            <text><span dim>Dimensions: </span>{previewData.dimensions || "—"}</text>
            <text><span dim>Size: </span>{previewData.file_size || "—"}</text>
          </>
        )}
        <box height={1} />
        <text dim>{plan.reasoning}</text>
      </box>

      {/* Reasoning */}
      <box flexDirection="column" paddingTop={1}>
        <text dim fg="#888888">
          {plan.reasoning}
        </text>
      </box>
    </box>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui && bun x tsc --noEmit 2>&1
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/tui/src/components/PreviewPanel.tsx
git commit -m "feat: add PreviewPanel with ASCII image preview and metadata"
```

---

### Task 16: Controls + StatusBar

**Files:**
- Create: `smart_renamer/tui/src/components/Controls.tsx`
- Create: `smart_renamer/tui/src/components/StatusBar.tsx`

- [ ] **Step 1: Write Controls and StatusBar**

Create `smart_renamer/tui/src/components/Controls.tsx`:
```tsx
interface ControlsProps {
  onExecute: () => void
  executing: boolean
}

export function Controls({ onExecute, executing }: ControlsProps) {
  return (
    <box flexDirection="row" gap={2} height={3} alignItems="center">
      <text dim>Space:toggle</text>
      <text dim>A:approve_all</text>
      <text dim>R:reject_all</text>
      <text
        border
        borderStyle="rounded"
        paddingX={1}
        onMouseDown={onExecute}
      >
        <span fg={executing ? "yellow" : "green"}>
          {executing ? "Executing..." : "Execute (E)"}
        </span>
      </text>
      <text dim>Q:quit</text>
    </box>
  )
}
```

Create `smart_renamer/tui/src/components/StatusBar.tsx`:
```tsx
interface StatusBarProps {
  message: string
}

export function StatusBar({ message }: StatusBarProps) {
  return (
    <box height={1} paddingX={1}>
      <text dim>{message}</text>
    </box>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui && bun x tsc --noEmit 2>&1
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add smart_renamer/tui/src/components/Controls.tsx smart_renamer/tui/src/components/StatusBar.tsx
git commit -m "feat: add Controls and StatusBar components"
```

---

### Task 17: Integration and Dry Run Test

- [ ] **Step 1: Start backend and test end-to-end**

```bash
# Terminal 1: Start backend
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m smart_renamer.backend &
BACKEND_PID=$!

# Send test commands
echo '{"id":"1","method":"session.create","params":{"directory":"/home/akash/Downloads/Sideshow Wallpaper-20260603T195332Z-3-001/Sideshow Wallpaper"}}' | PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m smart_renamer.backend 2>/dev/null

kill $BACKEND_PID 2>/dev/null
```

Expected: Valid JSON-RPC response with session status

- [ ] **Step 2: Try TUI startup (may need terminal)**

```bash
cd /home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation/smart_renamer/tui && PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation bun run src/index.tsx 2>&1 &
sleep 3
kill %1 2>/dev/null
```

Expected: TUI starts without crashing (will show partial render in background)

- [ ] **Step 3: Run all tests**

```bash
PYTHONPATH=/home/akash/Projects/Test\ Project/.worktrees/smart-renamer-implementation .venv/bin/python -m pytest tests/ -v 2>&1
```
Expected: All tests PASS

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete SmartRenamer redesign with OpenTUI and persistent backend"
git push origin smart-renamer-implementation
```
