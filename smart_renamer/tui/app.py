from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, DataTable, Static, Button, Label
from textual.screen import Screen
from textual.binding import Binding
from textual.reactive import reactive
from smart_renamer.brain.planner import Planner
from smart_renamer.brain.vision_router import VisionRouter
from smart_renamer.validator import Validator
from smart_renamer.executor import Executor
from smart_renamer.config import Config


class FileTable(DataTable):
    def __init__(self, plans: list, **kwargs):
        super().__init__(**kwargs)
        self.plans = plans
        self.approved = {p.file_id: True for p in plans}

    def on_mount(self) -> None:
        self.add_columns("\u2713", "Old Name", "Proposed Name", "Confidence", "Tags")
        for plan in self.plans:
            check = "\u2713" if self.approved[plan.file_id] else " "
            tags_str = ", ".join(plan.tags[:3])
            self.add_row(check, plan.old_path.name, plan.proposed_new_name, f"{plan.confidence:.0%}", tags_str)

    def toggle_file(self, file_id: str) -> None:
        self.approved[file_id] = not self.approved[file_id]
        self.clear()
        self.on_mount()


class PreviewPanel(Vertical):
    def __init__(self, plan=None, **kwargs):
        super().__init__(**kwargs)
        self._plan = plan

    def set_plan(self, plan):
        self._plan = plan
        self._update()

    def on_mount(self) -> None:
        self._update()

    def _update(self) -> None:
        self.remove_children()
        if not self._plan:
            self.mount(Static("Select a file to preview", id="preview-empty"))
            return
        self.mount(Static(f"Old: {self._plan.old_path.name}", id="preview-old"))
        self.mount(Static(f"New: {self._plan.proposed_new_name}", id="preview-new"))
        self.mount(Static(f"Tags: {', '.join(self._plan.tags)}", id="preview-tags"))
        self.mount(Static(f"Confidence: {self._plan.confidence:.0%}", id="preview-conf"))
        self.mount(Static(f"Summary: {self._plan.metadata_summary}", id="preview-summary"))


class StatusBar(Static):
    status = reactive("initial")

    def on_mount(self) -> None:
        self._update()

    def watch_status(self, val: str) -> None:
        self._update()

    def _update(self) -> None:
        self.update(f"Status: {self.status}")


class SmartRenamerApp(App):
    TITLE = "SmartRenamer"
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 3fr 1fr;
    }
    #file-grid { border: solid $primary; }
    #preview { border: solid $secondary; padding: 1; }
    #controls { column-span: 2; height: 3; }
    DataTable { height: 100%; }
    Button { margin: 1; }
    StatusBar { column-span: 2; height: 1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_file", "Toggle"),
        Binding("a", "approve_all", "Approve All"),
        Binding("e", "execute", "Execute"),
    ]

    def __init__(self, target_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.target_dir = target_dir
        self.config = Config()
        self.planner = Planner(template=self.config.template)
        self.vision_router = VisionRouter() if self.config.gemini_enabled else None
        self.validator = Validator()
        self.executor = Executor()
        self.plans = []
        self.status_bar = StatusBar()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="file-grid"):
                yield FileTable(self.plans, id="file-table")
            with Vertical(id="preview"):
                yield PreviewPanel(id="preview-panel")
        with Horizontal(id="controls"):
            yield Button("Toggle (Space)", id="btn-toggle", variant="primary")
            yield Button("Approve All (A)", id="btn-approve")
            yield Button("Execute (E)", id="btn-execute", variant="success")
        yield self.status_bar
        yield Footer()

    def on_mount(self) -> None:
        self.status_bar.status = "Scanning files..."
        files = sorted(self.target_dir.iterdir())
        files = [f for f in files if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".flac"}]
        self.plans = self.planner.plan(files, self.vision_router)
        self.status_bar.status = f"Ready: {len(self.plans)} files loaded"

    def action_toggle_file(self) -> None:
        table = self.query_one(FileTable)
        if table.cursor_row is not None and table.cursor_row < len(self.plans):
            plan = self.plans[table.cursor_row]
            table.toggle_file(plan.file_id)

    def action_approve_all(self) -> None:
        table = self.query_one(FileTable)
        for plan in self.plans:
            table.approved[plan.file_id] = True
        table.clear()
        table.on_mount()

    def action_execute(self) -> None:
        table = self.query_one(FileTable)
        approved = [p for p in self.plans if table.approved.get(p.file_id, False)]
        if not approved:
            self.status_bar.status = "No files approved for rename"
            return
        report = self.validator.validate(approved, self.target_dir)
        if report.conflicts:
            self.status_bar.status = f"Conflicts: {len(report.conflicts)} \u2014 fix and retry"
            return
        self.status_bar.status = "Executing..."
        results = self.executor.execute(approved, self.target_dir)
        ok = sum(1 for r in results if r.success)
        self.status_bar.status = f"Done: {ok}/{len(results)} renamed"
        self.plans = [p for p in self.plans if p.file_id not in {r.file_id for r in results if r.success}]
        table.clear()
        table.on_mount()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-toggle":
            self.action_toggle_file()
        elif event.button.id == "btn-approve":
            self.action_approve_all()
        elif event.button.id == "btn-execute":
            self.action_execute()
