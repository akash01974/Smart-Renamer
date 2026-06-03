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
