import json
import shutil
from datetime import datetime
from pathlib import Path
from smart_renamer.models import RenamePlan, ExecutionResult, UndoEntry


class Executor:
    def __init__(self, undo_dir: Path | None = None):
        self.undo_dir = undo_dir or Path.home() / ".smart_renamer" / "undo"
        self.undo_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, plans: list[RenamePlan], target_dir: Path) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        undo_entries: list[UndoEntry] = []
        for plan in plans:
            new_path = target_dir / plan.proposed_new_name
            try:
                if new_path.exists():
                    results.append(ExecutionResult(
                        file_id=plan.file_id, success=False,
                        old_path=plan.old_path, error="Target exists"
                    ))
                    continue
                if not plan.old_path.exists():
                    results.append(ExecutionResult(
                        file_id=plan.file_id, success=False,
                        old_path=plan.old_path, error="Source not found"
                    ))
                    continue
                shutil.move(str(plan.old_path), str(new_path))
                undo_entries.append(UndoEntry(old_path=new_path, new_path=plan.old_path))
                results.append(ExecutionResult(
                    file_id=plan.file_id, success=True,
                    old_path=plan.old_path, new_path=new_path
                ))
            except OSError as e:
                results.append(ExecutionResult(
                    file_id=plan.file_id, success=False,
                    old_path=plan.old_path, error=str(e)
                ))
        if undo_entries:
            self._save_undo(undo_entries)
        return results

    def _save_undo(self, entries: list[UndoEntry]) -> Path:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        undo_file = self.undo_dir / f"{session_id}.json"
        data = [{"old_path": str(e.old_path), "new_path": str(e.new_path)} for e in entries]
        undo_file.write_text(json.dumps(data, indent=2))
        return undo_file
