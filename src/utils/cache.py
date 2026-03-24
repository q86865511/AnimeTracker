"""
Disk-based image cache.

Images are stored at %APPDATA%/AnimeTracker/cache/images/{anime_sn}.jpg
and re-used for 7 days before being refreshed.

ImageCache.fetch() is safe to call from worker threads — it never touches
any Qt object. Callers must convert raw bytes to QPixmap on the main thread.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

_IMAGE_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Animad/1.16.16 (tw.com.gamer.android.animad; build:328; Android 9) okHttp/4.4.0"
    ),
    "Referer": "https://ani.gamer.com.tw/",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}

_CACHE_MAX_AGE = timedelta(days=7)
_TIMEOUT = 15


def _get_cache_dir() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    cache_dir = Path(appdata) / "AnimeTracker" / "cache" / "images"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class ImageCache:
    """
    Disk-based cover image cache keyed by anime_sn.

    All methods are thread-safe (independent files per anime_sn).
    """

    def __init__(self) -> None:
        self._dir = _get_cache_dir()
        self._session = requests.Session()
        self._session.headers.update(_IMAGE_HEADERS)

    def _path(self, anime_sn: int) -> Path:
        return self._dir / f"{anime_sn}.jpg"

    def _is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        return age < _CACHE_MAX_AGE

    def fetch(self, anime_sn: int, cover_url: str) -> Optional[bytes]:
        """
        Return raw image bytes for the given anime_sn.

        Returns cached data if fresh; downloads and caches otherwise.
        Returns None if the download fails.
        """
        path = self._path(anime_sn)
        if self._is_fresh(path):
            return path.read_bytes()

        try:
            resp = self._session.get(cover_url, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.content
            path.write_bytes(data)
            return data
        except Exception:
            # Return stale cache if available rather than nothing
            if path.exists():
                return path.read_bytes()
            return None

    def clear(self) -> None:
        """Remove all cached images."""
        for f in self._dir.glob("*.jpg"):
            f.unlink(missing_ok=True)
