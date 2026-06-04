from rich.console import Console
from rich.progress import Progress, TaskID

from dubber.application.ports.progress import ProgressReporter


class RichProgressTracker(ProgressReporter):
    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()
        self._progress: Progress | None = None
        self._task_id: TaskID | None = None

    def start(self, total: int, description: str = "Processing") -> None:
        self._progress = Progress(console=self._console)
        self._task_id = self._progress.add_task(description, total=total)
        self._progress.start()

    def advance(self, amount: int = 1) -> None:
        if self._progress and self._task_id is not None:
            self._progress.advance(self._task_id, amount)

    def log(self, message: str) -> None:
        self._console.print(message)

    def stop(self) -> None:
        if self._progress:
            self._progress.stop()
