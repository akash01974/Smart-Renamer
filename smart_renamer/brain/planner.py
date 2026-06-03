from pathlib import Path
from smart_renamer.models import RenamePlan
from smart_renamer.brain.metadata_extractor import MetadataExtractor
from smart_renamer.brain.classifier import Classifier
from smart_renamer.brain.template_engine import TemplateEngine


class Planner:
    def __init__(self, template: str = "{tags}_{index}"):
        self.metadata_extractor = MetadataExtractor()
        self.classifier = Classifier()
        self.template_engine = TemplateEngine(template)

    def plan(self, files: list[Path], vision_router=None) -> list[RenamePlan]:
        plans: list[RenamePlan] = []
        for idx, filepath in enumerate(sorted(files), start=1):
            if not filepath.is_file():
                continue
            metadata = self.metadata_extractor.extract(filepath)
            tags, confidence = self.classifier.classify(metadata)
            metadata_summary = self._build_summary(metadata, tags)
            if vision_router and confidence < 0.6:
                vision_tags = vision_router.enrich(filepath)
                if vision_tags:
                    tags = vision_tags
                    confidence = 0.85
            file_id = self.metadata_extractor.compute_file_id(filepath)
            date_str = ""
            if metadata.exif_date_taken:
                date_str = metadata.exif_date_taken.strftime("%Y-%m-%d")
            new_name = self.template_engine.generate(tags, idx, metadata.file_type, metadata_summary, date=date_str)
            plans.append(RenamePlan(
                file_id=file_id,
                old_path=filepath,
                proposed_new_name=new_name,
                confidence=round(confidence, 2),
                tags=tags,
                metadata_summary=metadata_summary,
            ))
        return plans

    def _build_summary(self, metadata, tags: list[str]) -> str:
        parts = []
        if metadata.dimensions:
            parts.append(f"{metadata.dimensions[0]}x{metadata.dimensions[1]}")
        if metadata.exif_camera:
            parts.append(metadata.exif_camera)
        if metadata.exif_date_taken:
            parts.append(metadata.exif_date_taken.strftime("%Y-%m-%d"))
        parts.append(", ".join(tags))
        return " | ".join(parts)
