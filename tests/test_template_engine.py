from smart_renamer.brain.template_engine import TemplateEngine


def test_default_template():
    engine = TemplateEngine()
    result = engine.generate(["sunset", "beach"], 1, ".jpg")
    assert result == "sunset_beach_01.jpg"


def test_custom_template():
    engine = TemplateEngine("{tags}_{date}_{index}")
    result = engine.generate(["mountain"], 3, ".png", date="2024-06-01")
    assert result == "mountain_2024-06-01_03.png"


def test_sanitizes_invalid_chars():
    engine = TemplateEngine("{tags}_{index}")
    result = engine.generate(["cool:pic"], 1, ".jpg")
    assert ":" not in result
    assert result.endswith(".jpg")


def test_handles_empty_tags():
    engine = TemplateEngine()
    result = engine.generate([], 1, ".png")
    assert result.startswith("untagged")


def test_max_length_200():
    engine = TemplateEngine()
    long_tags = ["a" * 50] * 10
    result = engine.generate(long_tags, 1, ".jpg")
    assert len(result[:-4]) <= 200


def test_slugify_metadata_summary():
    engine = TemplateEngine("{summary}_{tags}_{index}")
    result = engine.generate(["photo"], 1, ".jpg", "Golden Hour Sunset!!")
    assert "!!" not in result
    assert result.endswith(".jpg")


def test_invalid_template_key_raises():
    try:
        TemplateEngine("{unknown}")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "unknown" in str(e)
