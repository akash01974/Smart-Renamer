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
