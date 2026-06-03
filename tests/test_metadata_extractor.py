from pathlib import Path
from smart_renamer.brain import MetadataExtractor
from smart_renamer.models import FileMetadata


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


def test_extract_image_dimensions(tmp_path):
    from PIL import Image
    img_path = tmp_path / "test.png"
    img = Image.new("RGB", (100, 200))
    img.save(img_path)
    extractor = MetadataExtractor()
    meta = extractor.extract(img_path)
    assert meta.dimensions == (100, 200)


def test_extract_non_image_returns_no_dimensions(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"\x00\x01\x02")
    extractor = MetadataExtractor()
    meta = extractor.extract(f)
    assert meta.dimensions is None


def test_extract_nonexistent_file_raises(tmp_path):
    import pytest
    extractor = MetadataExtractor()
    with pytest.raises(FileNotFoundError):
        extractor.extract(tmp_path / "does_not_exist.jpg")


def test_gps_parse_directly():
    from smart_renamer.brain.metadata_extractor import MetadataExtractor
    extractor = MetadataExtractor()
    gps = {
        1: "N",
        2: (37, 46, 29.64),
        3: "W",
        4: (122, 25, 9.12),
    }
    result = extractor._parse_gps(gps)
    assert result is not None
    assert abs(result[0] - 37.7749) < 0.01
    assert abs(result[1] - (-122.4192)) < 0.01
