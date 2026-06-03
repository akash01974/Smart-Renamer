from pathlib import Path
from smart_renamer.brain.planner import Planner


def test_planner_skips_non_files(tmp_path):
    d = tmp_path / "subdir"
    d.mkdir()
    planner = Planner()
    plans = planner.plan([d])
    assert len(plans) == 0


def test_planner_generates_renames_for_files(tmp_path):
    f1 = tmp_path / "photo.jpg"
    f1.write_text("fake-jpeg-data")
    f2 = tmp_path / "wallpaper.png"
    f2.write_text("fake-png-data")
    planner = Planner()
    plans = planner.plan([f1, f2])
    assert len(plans) == 2
    for plan in plans:
        assert plan.proposed_new_name.endswith((".jpg", ".png"))
        assert plan.confidence > 0
        assert len(plan.file_id) == 12
