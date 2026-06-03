from smart_renamer.models import RenamePlan, ExecutionResult, ValidationReport, Conflict, UndoEntry, FileMetadata
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


def test_file_metadata_defaults():
    meta = FileMetadata(path=Path("/tmp/test.jpg"))
    assert meta.path == Path("/tmp/test.jpg")
    assert meta.size_bytes == 0
    assert meta.dimensions is None
    assert meta.dominant_colors == []


def test_file_metadata_with_all_fields():
    from datetime import datetime
    dt = datetime(2024, 6, 1, 12, 0, 0)
    meta = FileMetadata(
        path=Path("/tmp/photo.jpg"),
        size_bytes=2048576,
        dimensions=(3840, 2160),
        file_type=".jpg",
        created_at=dt,
        modified_at=dt,
        exif_camera="Canon EOS 5D",
        exif_date_taken=dt,
        exif_gps=(37.7749, -122.4194),
        is_animated=False,
        dominant_colors=["#123456", "#789abc"],
    )
    assert meta.size_bytes == 2048576
    assert meta.dimensions == (3840, 2160)
    assert meta.exif_camera == "Canon EOS 5D"
    assert meta.exif_gps == (37.7749, -122.4194)
