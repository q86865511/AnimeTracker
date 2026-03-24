"""Unit tests for src/api/models.py — no network calls needed."""
import pytest
from src.api.models import AnimeItem, AnimeDetail, HighlightTag, VolumeItem


# ── Fixtures ───────────────────────────────────────────────────────────────────

ANIME_ITEM_DICT = {
    "anime_sn": "37943",
    "acg_sn": "141647",
    "title": "葬送的芙莉蓮",
    "cover": "https://p2.bahamut.com.tw/B/ACG/c/47/0000141647.JPG",
    "score": 9.1,
    "popular": "2537360",
    "highlightTag": {
        "bilingual": True,
        "edition": "HD",
        "vipTime": "",
        "newArrival": False,
    },
}

ANIME_DETAIL_DICT = {
    "anime_sn": 37943,
    "acg_sn": 141647,
    "title": "葬送的芙莉蓮",
    "cover": "https://p2.bahamut.com.tw/B/ACG/c/47/0000141647.JPG",
    "content": "勇者欣梅爾打倒魔王後…",
    "total_volume": 28,
    "upload_time": "2023/9/29",
    "season_start": "2023/9/29",
    "season_end": "2024/3/22",
    "popular": 2537360,
    "score": 9.1,
    "rating": 1,
    "tags": ["奇幻冒險", "溫馨"],
    "category": 3,
    "director": "齋藤圭一郎",
    "publisher": "Aniplex",
    "maker": "Madhouse",
    "volumes": {
        "0": [
            {"volume": 1, "video_sn": 1000001, "state": 2, "cover": ""},
            {"volume": 2, "video_sn": 1000002, "state": 2, "cover": ""},
        ],
        "2": [
            {"volume": 1, "video_sn": 1000099, "state": 2, "cover": ""},
        ],
    },
    "favorite": False,
}


# ── AnimeItem tests ────────────────────────────────────────────────────────────

class TestAnimeItem:
    def test_basic_parsing(self):
        item = AnimeItem.from_dict(ANIME_ITEM_DICT)
        assert item.anime_sn == 37943
        assert item.acg_sn == 141647
        assert item.title == "葬送的芙莉蓮"
        assert item.score == 9.1
        assert item.popular == 2537360

    def test_cover_url_from_api(self):
        """When cover is present in dict, use it directly."""
        item = AnimeItem.from_dict(ANIME_ITEM_DICT)
        assert item.cover_url == "https://p2.bahamut.com.tw/B/ACG/c/47/0000141647.JPG"

    def test_cover_url_derived_from_acg_sn(self):
        """When cover is absent, derive URL from acg_sn."""
        data = {**ANIME_ITEM_DICT, "cover": ""}
        item = AnimeItem.from_dict(data)
        assert item.cover_url == "https://img.bahamut.com.tw/anime/acg/141647.jpg"

    def test_highlight_tag_bilingual(self):
        item = AnimeItem.from_dict(ANIME_ITEM_DICT)
        assert item.highlight_tag.bilingual is True
        assert item.highlight_tag.edition == "HD"

    def test_popular_display_over_10k(self):
        item = AnimeItem.from_dict(ANIME_ITEM_DICT)
        assert item.popular_display == "253.7萬"

    def test_popular_display_under_10k(self):
        data = {**ANIME_ITEM_DICT, "popular": "9999"}
        item = AnimeItem.from_dict(data)
        assert item.popular_display == "9999"

    def test_score_display(self):
        item = AnimeItem.from_dict(ANIME_ITEM_DICT)
        assert item.score_display == "9.1"

    def test_score_display_zero(self):
        data = {**ANIME_ITEM_DICT, "score": 0}
        item = AnimeItem.from_dict(data)
        assert item.score_display == "--"

    def test_none_values_handled(self):
        """Fields with None should not raise."""
        data = {
            "anime_sn": 1,
            "acg_sn": 2,
            "title": "Test",
            "cover": None,
            "score": None,
            "popular": None,
            "highlightTag": {},
        }
        item = AnimeItem.from_dict(data)
        assert item.score == 0.0
        assert item.popular == 0

    def test_camel_case_keys(self):
        """Endpoints like newAnimeSchedule use camelCase keys."""
        data = {
            "animeSn": "999",
            "acgSn": "888",
            "title": "CamelCase Test",
        }
        item = AnimeItem.from_dict(data)
        assert item.anime_sn == 999
        assert item.acg_sn == 888


# ── AnimeDetail tests ──────────────────────────────────────────────────────────

class TestAnimeDetail:
    def test_basic_parsing(self):
        detail = AnimeDetail.from_dict(ANIME_DETAIL_DICT)
        assert detail.anime_sn == 37943
        assert detail.title == "葬送的芙莉蓮"
        assert detail.score == 9.1
        assert detail.total_volume == 28
        assert detail.director == "齋藤圭一郎"

    def test_tags(self):
        detail = AnimeDetail.from_dict(ANIME_DETAIL_DICT)
        assert "奇幻冒險" in detail.tags
        assert "溫馨" in detail.tags

    def test_rating_name(self):
        detail = AnimeDetail.from_dict(ANIME_DETAIL_DICT)
        assert detail.rating_name == "普遍級"   # rating=1

    def test_volumes_parsed(self):
        detail = AnimeDetail.from_dict(ANIME_DETAIL_DICT)
        assert "0" in detail.volumes
        assert len(detail.volumes["0"]) == 2
        assert detail.volumes["0"][0].video_sn == 1000001

    def test_volume_type_special(self):
        detail = AnimeDetail.from_dict(ANIME_DETAIL_DICT)
        assert "2" in detail.volumes
        assert detail.volumes["2"][0].volume == 1

    def test_none_values_handled(self):
        data = {
            "anime_sn": 1,
            "acg_sn": 2,
            "title": "",
            "cover": None,
            "content": None,
            "total_volume": None,
            "upload_time": None,
            "season_start": None,
            "season_end": None,
            "popular": None,
            "score": None,
            "rating": None,
            "tags": None,
            "category": None,
            "director": None,
            "publisher": None,
            "maker": None,
            "volumes": {},
        }
        detail = AnimeDetail.from_dict(data)
        assert detail.total_volume == 0
        assert detail.popular == 0
        assert detail.score == 0.0
        assert detail.rating == 1
        assert detail.tags == []


# ── HighlightTag tests ─────────────────────────────────────────────────────────

class TestHighlightTag:
    def test_empty_dict(self):
        tag = HighlightTag.from_dict({})
        assert tag.bilingual is False
        assert tag.edition == ""

    def test_full_dict(self):
        tag = HighlightTag.from_dict(
            {"bilingual": True, "edition": "4K", "vipTime": "2025-01", "newArrival": True}
        )
        assert tag.bilingual is True
        assert tag.edition == "4K"
        assert tag.vip_time == "2025-01"
        assert tag.new_arrival is True
