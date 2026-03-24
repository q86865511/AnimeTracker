"""
Local JSON storage for favorites and watchlist.

Data is persisted at %APPDATA%/AnimeTracker/data/{filename}.json.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.models import AnimeItem

_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "AnimeTracker" / "data"


@dataclass
class StoredAnime:
    anime_sn: int
    acg_sn: int
    title: str
    score: float = 0.0
    popular: int = 0

    def to_anime_item(self) -> "AnimeItem":
        from src.api.models import AnimeItem  # avoid circular import
        return AnimeItem(
            anime_sn=self.anime_sn,
            acg_sn=self.acg_sn,
            title=self.title,
            score=self.score,
            popular=self.popular,
        )

    @classmethod
    def from_anime_item(cls, anime: "AnimeItem") -> "StoredAnime":
        return cls(
            anime_sn=anime.anime_sn,
            acg_sn=anime.acg_sn,
            title=anime.title,
            score=anime.score,
            popular=anime.popular,
        )


class LocalStore:
    """Generic JSON-persisted store for anime items."""

    def __init__(self, filename: str) -> None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._path = _DATA_DIR / filename
        self._data: dict[int, StoredAnime] = {}
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw: list[dict] = json.load(f)
            self._data = {
                item["anime_sn"]: StoredAnime(**item)
                for item in raw
                if isinstance(item, dict) and "anime_sn" in item
            }
        except Exception:
            self._data = {}

    def _save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(
                    [asdict(v) for v in self._data.values()],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            pass

    # ── Public interface ───────────────────────────────────────────────────────

    def add(self, anime: "AnimeItem") -> None:
        self._data[anime.anime_sn] = StoredAnime.from_anime_item(anime)
        self._save()

    def remove(self, anime_sn: int) -> None:
        self._data.pop(anime_sn, None)
        self._save()

    def contains(self, anime_sn: int) -> bool:
        return anime_sn in self._data

    def toggle(self, anime: "AnimeItem") -> bool:
        """Toggle item. Returns True if now added, False if now removed."""
        if self.contains(anime.anime_sn):
            self.remove(anime.anime_sn)
            return False
        self.add(anime)
        return True

    def all_items(self) -> list[StoredAnime]:
        return list(self._data.values())

    def to_anime_items(self) -> list["AnimeItem"]:
        return [s.to_anime_item() for s in self._data.values()]

    def __len__(self) -> int:
        return len(self._data)
