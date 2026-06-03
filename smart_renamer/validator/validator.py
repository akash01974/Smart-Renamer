import os
import re
from collections import Counter
from pathlib import Path
from smart_renamer.models import RenamePlan, ValidationReport, Conflict


class Validator:
    MAX_PATH_LENGTH = 255
    INVALID_CHARS = re.compile(r'[<>:"/\\|?*]')
    RESERVED_NAMES = {"con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"}

    def validate(self, plans: list[RenamePlan], target_dir: Path) -> ValidationReport:
        report = ValidationReport()
        proposed_names = [p.proposed_new_name for p in plans]
        duplicates = {name: idxs for name, idxs in Counter(proposed_names).items() if idxs > 1}
        for name, count in duplicates.items():
            conflicted = [p for p in plans if p.proposed_new_name == name]
            report.conflicts.append(Conflict(
                file_ids=[p.file_id for p in conflicted],
                proposed_name=name,
                reason=f"{count} files would get the same name"
            ))
        for plan in plans:
            full_path = target_dir / plan.proposed_new_name
            if full_path.exists() and full_path != plan.old_path:
                report.conflicts.append(Conflict(
                    file_ids=[plan.file_id],
                    proposed_name=plan.proposed_new_name,
                    reason="Target file already exists"
                ))
            if len(str(full_path)) > self.MAX_PATH_LENGTH:
                report.warnings.append(f"Path too long: {plan.proposed_new_name} ({len(str(full_path))} chars)")
            name_stem = Path(plan.proposed_new_name).stem.lower()
            if name_stem in self.RESERVED_NAMES:
                report.warnings.append(f"Reserved filename: {plan.proposed_new_name}")
            if self.INVALID_CHARS.search(plan.proposed_new_name):
                report.warnings.append(f"Invalid characters in: {plan.proposed_new_name}")
        return report
