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
