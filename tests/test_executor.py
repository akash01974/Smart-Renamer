from pathlib import Path
from smart_renamer.models import RenamePlan
from smart_renamer.executor import Executor


def test_execute_rename_success(tmp_path):
    src = tmp_path / "old.jpg"
    src.write_text("data")
    plans = [
        RenamePlan(file_id="a", old_path=src, proposed_new_name="new.jpg", confidence=0.9, tags=[], metadata_summary=""),
    ]
    ex = Executor(undo_dir=tmp_path / "undo")
    results = ex.execute(plans, tmp_path)
    assert results[0].success
    assert (tmp_path / "new.jpg").exists()
    assert not src.exists()


def test_execute_skips_missing_source(tmp_path):
    plans = [
        RenamePlan(file_id="a", old_path=tmp_path / "nonexistent.jpg", proposed_new_name="new.jpg", confidence=0.9, tags=[], metadata_summary=""),
    ]
    ex = Executor(undo_dir=tmp_path / "undo")
    results = ex.execute(plans, tmp_path)
    assert not results[0].success
    assert results[0].error == "Source not found"


def test_execute_skips_existing_target(tmp_path):
    src = tmp_path / "old.jpg"
    src.write_text("data")
    existing = tmp_path / "existing.jpg"
    existing.write_text("other")
    plans = [
        RenamePlan(file_id="a", old_path=src, proposed_new_name="existing.jpg", confidence=0.9, tags=[], metadata_summary=""),
    ]
    ex = Executor(undo_dir=tmp_path / "undo")
    results = ex.execute(plans, tmp_path)
    assert not results[0].success
    assert "Target exists" in results[0].error
