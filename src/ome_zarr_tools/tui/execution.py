"""Run work in a Textual worker thread, off the UI event loop.

``run_in_background`` takes an arbitrary no-argument callable -- generalized in
T016 so ``fix_metadata``/``migrate``'s Run action (tui/screens/metadata_screen.py)
can call their extracted write functions directly instead of going through
``click.Command.main()`` (which would hang on stdin for those two commands'
internal prompts/confirms -- see research.md). ``run_command`` remains the
convenience wrapper every other command's generic form (tui/app.py) uses.

T020 (US5) adds live progress and log capture, both optional and both pushed to
the UI thread via ``App.call_from_thread``:

- Progress: a ``dask.callbacks.Callback`` registered around ``work()`` observes
  any dask task graph the command happens to execute -- ``start_state`` reports
  the total task count, ``posttask`` fires once per completed task (research.md,
  verified: exact task-count match on a real computation). Commands with no
  dask work simply never report a total.
- Log: ``sys.stdout`` is redirected during ``work()`` to forward each chunk to
  the log callback -- the same text a plain-CLI run would print via
  ``click.echo`` (verified: ``click.echo`` respects ``contextlib.redirect_stdout``).
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import click
from dask.callbacks import Callback as DaskCallback
from textual.app import App


@dataclass
class ExecutionResult:
    succeeded: bool
    error: str | None = None


OnDone = Callable[[ExecutionResult], None | Awaitable[None]]


class _DaskProgressCallback(DaskCallback):
    """Reports dask task-graph progress to the UI thread as it happens."""

    def __init__(self, app: App, on_progress: Callable[[int, int], None]) -> None:
        super().__init__()
        self._app = app
        self._on_progress = on_progress

    def _start_state(self, dsk, state) -> None:  # noqa: ANN001
        total = len(dsk)
        self._app.call_from_thread(self._on_progress, 0, total)

    def _posttask(self, key, result, dsk, state, worker_id) -> None:  # noqa: ANN001
        done = len(state["finished"])
        self._app.call_from_thread(self._on_progress, done, len(dsk))


class _LogStream:
    """A write-only stream that forwards chunks to the UI thread as log lines.

    Deliberately *not* an ``io.TextIOBase`` subclass: click's
    ``_default_text_stdout()`` wraps ``sys.stdout`` in its own
    ``TextIOWrapper``-based compat shim, which requires a binary buffer
    underneath and calls ``.write(bytes)`` on it -- verified directly. Plain
    duck-typing (accepting either ``str`` or ``bytes``) sidesteps that.
    """

    encoding = "utf-8"

    def __init__(self, app: App, on_log: Callable[[str], None]) -> None:
        self._app = app
        self._on_log = on_log

    def write(self, s: str | bytes) -> int:
        if isinstance(s, (bytes, bytearray)):
            s = s.decode(self.encoding, errors="replace")
        if s and s != "\n":
            self._app.call_from_thread(self._on_log, s.rstrip("\n"))
        return len(s)

    def flush(self) -> None:  # pragma: no cover - no buffering to flush
        pass

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


def run_in_background(
    app: App,
    work: Callable[[], None],
    on_done: OnDone,
    on_progress: Callable[[int, int], None] | None = None,
    on_log: Callable[[str], None] | None = None,
) -> None:
    """Run ``work`` in a worker thread; call ``on_done`` on the UI thread when finished.

    ``on_progress(done, total)`` and ``on_log(line)``, if given, are called on the
    UI thread as the dask task graph / stdout produce them during ``work()``.
    """

    def _work() -> None:
        with contextlib.ExitStack() as stack:
            if on_progress is not None:
                stack.enter_context(_DaskProgressCallback(app, on_progress))
            if on_log is not None:
                stack.enter_context(contextlib.redirect_stdout(_LogStream(app, on_log)))
            try:
                work()
            except Exception as exc:
                app.call_from_thread(on_done, ExecutionResult(succeeded=False, error=str(exc)))
                return
        app.call_from_thread(on_done, ExecutionResult(succeeded=True))

    app.run_worker(_work, thread=True, exclusive=True)


def run_command(
    app: App,
    command: click.Command,
    tokens: list[str],
    on_done: OnDone,
    on_progress: Callable[[int, int], None] | None = None,
    on_log: Callable[[str], None] | None = None,
) -> None:
    """Run ``command`` with ``tokens`` in a worker thread; call ``on_done`` on the UI thread."""
    run_in_background(
        app,
        lambda: command.main(
            args=tokens, prog_name=f"ome-zarr-tools {command.name}", standalone_mode=False
        ),
        on_done,
        on_progress=on_progress,
        on_log=on_log,
    )
