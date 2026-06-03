from pathlib import Path
from pydantic import BaseModel


class RenamePlan(BaseModel):
    file_id: str
    old_path: Path
    proposed_new_name: str
    confidence: float
    tags: list[str]
    metadata_summary: str
