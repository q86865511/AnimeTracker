"""
Image download worker.

Downloads and caches a cover image in a background thread, then emits
raw bytes via signal. The receiver MUST convert bytes → QPixmap on the
main thread (QPixmap is not thread-safe).
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from src.utils.cache import ImageCache


class ImageWorkerSignals(QObject):
    """Signals for ImageWorker."""
    loaded = pyqtSignal(int, bytes)   # (anime_sn, raw_image_bytes)
    failed = pyqtSignal(int)          # (anime_sn) — image could not be fetched


class ImageWorker(QRunnable):
    """
    Fetches the cover image for one anime and emits the raw bytes.

    The bytes-based signal keeps QPixmap creation on the main thread,
    which is required because QPixmap is not thread-safe.

    Usage::

        worker = ImageWorker(anime_sn, cover_url, image_cache)
        worker.signals.loaded.connect(self._on_image_loaded)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(self, anime_sn: int, cover_url: str, cache: ImageCache) -> None:
        super().__init__()
        self.anime_sn = anime_sn
        self.cover_url = cover_url
        self.cache = cache
        self.signals = ImageWorkerSignals()
        self.setAutoDelete(True)

    def run(self) -> None:
        data = self.cache.fetch(self.anime_sn, self.cover_url)
        if data:
            self.signals.loaded.emit(self.anime_sn, data)
        else:
            self.signals.failed.emit(self.anime_sn)
