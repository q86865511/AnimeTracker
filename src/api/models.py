"""
API response data models for Bahamut Anime Crazy.

All models are plain Python dataclasses with no PyQt6 dependencies.
Each provides a from_dict() classmethod to parse raw API JSON.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# Cover image URL template (fallback when API doesn't return cover field)
_COVER_URL_TEMPLATE = "https://img.bahamut.com.tw/anime/acg/{acg_sn}.jpg"

# Volume type names used in AnimeDetail.volumes dict keys
VOLUME_TYPE_NAMES: dict[str, str] = {
    "0": "本篇",
    "1": "電影",
    "2": "特別篇",
    "3": "中文配音",
}

RATING_NAMES: dict[int, str] = {
    1: "普遍級",
    2: "保護級",
    3: "輔12級",
    4: "輔15級",
    5: "限制級",
}

CATEGORIES: dict[int, str] = {
    0: "所有動畫",
    1: "戀愛",
    2: "溫馨",
    3: "奇幻冒險",
    4: "科幻未來",
    5: "幽默搞笑",
    6: "靈異神怪",
    7: "推理懸疑",
    8: "料理美食",
    9: "社會寫實",
    10: "運動競技",
    11: "歷史傳記",
    12: "其他",
    13: "青春校園",
}


@dataclass
class HighlightTag:
    bilingual: bool = False
    edition: str = ""
    vip_time: str = ""
    new_arrival: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> HighlightTag:
        return cls(
            bilingual=bool(data.get("bilingual", False)),
            edition=data.get("edition", "") or "",
            vip_time=data.get("vipTime", "") or "",
            new_arrival=bool(data.get("newArrival", False)),
        )


@dataclass
class AnimeItem:
    """Represents a single anime from list or search endpoints."""
    anime_sn: int
    acg_sn: int
    title: str
    _cover: str = field(default="", repr=False)
    score: float = 0.0
    popular: int = 0
    highlight_tag: HighlightTag = field(default_factory=HighlightTag)

    @property
    def cover_url(self) -> str:
        """Return cover URL from API or derive from acg_sn."""
        return self._cover if self._cover else _COVER_URL_TEMPLATE.format(acg_sn=self.acg_sn)

    @property
    def popular_display(self) -> str:
        """Format popularity number for display (e.g. 253.7萬)."""
        if self.popular >= 10_000:
            return f"{self.popular / 10_000:.1f}萬"
        return str(self.popular)

    @property
    def score_display(self) -> str:
        return f"{self.score:.1f}" if self.score else "--"

    @classmethod
    def from_dict(cls, data: dict) -> AnimeItem:
        tag_data = data.get("highlightTag", {}) or {}
        popular_raw = data.get("popular", 0)
        score_raw = data.get("score", 0)

        # Support both snake_case and camelCase from different endpoints
        anime_sn = data.get("anime_sn") or data.get("animeSn") or 0
        acg_sn = data.get("acg_sn") or data.get("acgSn") or 0

        return cls(
            anime_sn=int(anime_sn or 0),
            acg_sn=int(acg_sn or 0),
            title=data.get("title", "") or "",
            _cover=data.get("cover", "") or "",
            score=float(score_raw or 0),
            popular=int(popular_raw or 0),
            highlight_tag=HighlightTag.from_dict(tag_data),
        )


@dataclass
class VolumeItem:
    volume: int
    video_sn: int
    state: int
    cover: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> VolumeItem:
        return cls(
            volume=int(data.get("volume", 0) or 0),
            video_sn=int(data.get("video_sn", 0) or 0),
            state=int(data.get("state", 0) or 0),
            cover=data.get("cover", "") or "",
        )


@dataclass
class AnimeDetail:
    """Full anime detail from v3/video.php?anime_sn=..."""
    anime_sn: int
    acg_sn: int
    title: str
    _cover: str
    content: str
    total_volume: int
    upload_time: str
    season_start: str
    season_end: str
    popular: int
    score: float
    rating: int
    tags: list[str]
    category: int
    director: str
    publisher: str
    maker: str
    volumes: dict[str, list[VolumeItem]]
    favorite: bool = False

    @property
    def cover_url(self) -> str:
        return self._cover if self._cover else _COVER_URL_TEMPLATE.format(acg_sn=self.acg_sn)

    @property
    def rating_name(self) -> str:
        return RATING_NAMES.get(self.rating, "普遍級")

    @property
    def popular_display(self) -> str:
        if self.popular >= 10_000:
            return f"{self.popular / 10_000:.1f}萬"
        return str(self.popular)

    @property
    def score_display(self) -> str:
        return f"{self.score:.1f}" if self.score else "--"

    @classmethod
    def from_dict(cls, data: dict) -> AnimeDetail:
        volumes_raw = data.get("volumes", {}) or {}
        volumes: dict[str, list[VolumeItem]] = {}
        for vtype, items in volumes_raw.items():
            if isinstance(items, list):
                volumes[str(vtype)] = [VolumeItem.from_dict(item) for item in items]

        return cls(
            anime_sn=int(data.get("anime_sn", 0) or 0),
            acg_sn=int(data.get("acg_sn", 0) or 0),
            title=data.get("title", "") or "",
            _cover=data.get("cover", "") or "",
            content=data.get("content", "") or "",
            total_volume=int(data.get("total_volume", 0) or 0),
            upload_time=data.get("upload_time", "") or "",
            season_start=data.get("season_start", "") or "",
            season_end=data.get("season_end", "") or "",
            popular=int(data.get("popular", 0) or 0),
            score=float(data.get("score", 0) or 0),
            rating=int(data.get("rating", 1) or 1),
            tags=list(data.get("tags", []) or []),
            category=int(data.get("category", 0) or 0),
            director=data.get("director", "") or "",
            publisher=data.get("publisher", "") or "",
            maker=data.get("maker", "") or "",
            volumes=volumes,
            favorite=bool(data.get("favorite", False)),
        )
