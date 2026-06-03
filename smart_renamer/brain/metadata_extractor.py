import hashlib
from datetime import datetime
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS
from smart_renamer.models import FileMetadata


class MetadataExtractor:
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}

    def extract(self, path: Path) -> FileMetadata:
        stats = path.stat()
        metadata = FileMetadata(
            path=path,
            size_bytes=stats.st_size,
            file_type=path.suffix.lower(),
            created_at=datetime.fromtimestamp(stats.st_ctime),
            modified_at=datetime.fromtimestamp(stats.st_mtime),
        )
        if path.suffix.lower() in self.IMAGE_EXTENSIONS:
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
        except (OSError, ValueError, TypeError, AttributeError):
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
        except (TypeError, KeyError, ValueError, IndexError):
            pass
        return None

    def compute_file_id(self, path: Path) -> str:
        hasher = hashlib.md5()
        hasher.update(str(path.resolve()).encode())
        return hasher.hexdigest()[:12]
