import sys
from pathlib import Path
from smart_renamer.config import Config
from smart_renamer.brain.planner import Planner
from smart_renamer.brain.vision_router import VisionRouter
from smart_renamer.validator import Validator
from smart_renamer.executor import Executor


def cli():
    args = sys.argv[1:]
    use_tui = "--tui" in args or "-t" in args
    target_dir = None
    for a in args:
        if not a.startswith("-"):
            target_dir = Path(a)
            break
    target_dir = target_dir or Path.cwd()
    if use_tui:
        from smart_renamer.tui.app import SmartRenamerApp
        app = SmartRenamerApp(target_dir)
        app.run()
        return
    config = Config()
    vision_router = VisionRouter(api_key=config.gemini_api_key) if config.gemini_enabled else None
    planner = Planner(template=config.template)
    files = sorted(target_dir.iterdir()) if not config.recursive else sorted(target_dir.rglob("*"))
    files = [f for f in files if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".flac"}]
    if not files:
        print("No supported media files found.")
        sys.exit(0)
    plans = planner.plan(files, vision_router)
    validator = Validator()
    report = validator.validate(plans, target_dir)
    if report.conflicts:
        print("Validation conflicts found:")
        for c in report.conflicts:
            print(f"  - {c.reason}: {c.proposed_name}")
        sys.exit(1)
    print(f"Planned renames for {len(plans)} files:")
    for plan in plans:
        marker = "[DRY RUN]" if config.dry_run else "[EXECUTE]"
        print(f"  {marker} {plan.old_path.name} -> {plan.proposed_new_name}  (conf: {plan.confidence})")
    if not config.dry_run:
        executor = Executor()
        results = executor.execute(plans, target_dir)
        success = sum(1 for r in results if r.success)
        print(f"Renamed {success}/{len(results)} files.")
    else:
        print("Dry run -- no files changed. Set dry_run = false to execute.")


if __name__ == "__main__":
    cli()
