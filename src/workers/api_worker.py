"""
Thread-safe API worker using the QRunnable / WorkerSignals pattern.

QRunnable does not inherit QObject, so signals must live on a separate
QObject companion class (WorkerSignals). Emit signals from run(); Qt's
event loop will queue the call on the main thread automatically.
"""
from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal


class WorkerSignals(QObject):
    """Signals for ApiWorker. Must be a QObject subclass."""
    result = pyqtSignal(object)   # emits the return value of fn()
    error = pyqtSignal(str)       # emits str(exception) on failure
    finished = pyqtSignal()       # always emitted last


class ApiWorker(QRunnable):
    """
    Runs any callable in QThreadPool and reports the result via signals.

    Usage::

        worker = ApiWorker(client.get_anime_list, category, page)
        worker.signals.result.connect(self._on_list_loaded)
        worker.signals.error.connect(self._on_error)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()
