from smart_renamer.models import FileMetadata
from smart_renamer.brain.classifier import Classifier
from pathlib import Path


def test_classifies_wallpaper():
    meta = FileMetadata(
        path=Path("test.jpg"),
        dimensions=(1920, 1200),
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


def test_classifies_meme():
    meta = FileMetadata(
        path=Path("meme.png"),
        dimensions=(500, 500),
        file_type=".png",
    )
    tags, conf = Classifier().classify(meta)
    assert "meme" in tags


def test_classifies_audio():
    meta = FileMetadata(path=Path("song.mp3"), file_type=".mp3")
    tags, conf = Classifier().classify(meta)
    assert "audio" in tags


def test_image_tag_appended():
    meta = FileMetadata(path=Path("img.jpg"), file_type=".jpg")
    tags, conf = Classifier().classify(meta)
    assert "image" in tags


def test_dated_tag_with_exif_date():
    from datetime import datetime
    meta = FileMetadata(
        path=Path("photo.jpg"),
        dimensions=(4000, 3000),
        file_type=".jpg",
        exif_camera="Nikon",
        exif_date_taken=datetime(2024, 6, 1, 12, 0, 0),
    )
    tags, conf = Classifier().classify(meta)
    assert "photo" in tags
    assert "dated" in tags
    assert "nikon" in tags


def test_wallpaper_excludes_screen_resolutions():
    meta = FileMetadata(
        path=Path("wall.png"),
        dimensions=(1920, 1080),
        file_type=".png",
    )
    tags, conf = Classifier().classify(meta)
    assert "screenshot" in tags
    assert "wallpaper" not in tags
