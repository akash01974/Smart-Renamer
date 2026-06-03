from smart_renamer.models import FileMetadata


class Classifier:
    SCREEN_RESOLUTIONS = {(1920, 1080), (2560, 1440), (3840, 2160), (1366, 768), (1440, 900)}

    def classify(self, metadata: FileMetadata) -> tuple[list[str], float]:
        tags: list[str] = []
        confidence = 0.5

        if self._is_screenshot(metadata):
            tags.append("screenshot")
            confidence = 0.8
        elif self._is_wallpaper(metadata):
            tags.append("wallpaper")
            confidence = 0.7
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

    def _is_screenshot(self, m: FileMetadata) -> bool:
        if m.dimensions is None:
            return False
        return m.dimensions in self.SCREEN_RESOLUTIONS and not self._has_exif_camera(m)

    def _is_wallpaper(self, m: FileMetadata) -> bool:
        if m.dimensions is None:
            return False
        w, h = m.dimensions
        return (w >= 1920 and h >= 1080) and not self._has_exif_camera(m)

    def _is_meme(self, m: FileMetadata) -> bool:
        if m.dimensions is None:
            return False
        w, h = m.dimensions
        return 200 <= w <= 800 and 200 <= h <= 800 and not self._has_exif_camera(m)

    def _has_exif_camera(self, m: FileMetadata) -> bool:
        return m.exif_camera is not None
