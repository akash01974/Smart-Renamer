from smart_renamer.brain.vision_router import VisionRouter
from pathlib import Path


def test_vision_router_unavailable_without_key():
    router = VisionRouter(api_key="")
    assert not router.is_available()
    assert router.enrich(Path("test.jpg")) == []


def test_vision_router_skips_non_images():
    router = VisionRouter(api_key="fake")
    assert router.enrich(Path("test.txt")) == []


def test_cache_hit(tmp_path):
    img = tmp_path / "test.jpg"
    img.write_text("fake-data")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    router = VisionRouter(api_key="fake", cache_dir=cache_dir)
    key = router._cache_key(img)
    cache_file = cache_dir / f"{key}.json"
    import json
    cache_file.write_text(json.dumps(["sunset", "ocean"]))
    result = router.enrich(img)
    assert result == ["sunset", "ocean"]
