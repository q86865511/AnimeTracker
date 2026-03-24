"""
Unit tests for BahamutAnimeClient.

Uses the `responses` library to intercept HTTP calls — no real network required.
Install dev dependencies first: pip install -r requirements-dev.txt
"""
import time

import pytest
import responses as responses_lib

from src.api.client import BahamutAnimeClient, BahamutApiError, MOBILE_API_BASE
from src.api.models import AnimeItem, AnimeDetail


# ── Mock response payloads ─────────────────────────────────────────────────────

MOCK_LIST_RESPONSE = {
    "data": {
        "animeList": [
            {
                "anime_sn": "37943",
                "acg_sn": "141647",
                "title": "葬送的芙莉蓮",
                "highlightTag": {"bilingual": True, "edition": "", "vipTime": ""},
            },
            {
                "anime_sn": "38000",
                "acg_sn": "141700",
                "title": "另一部動畫",
                "highlightTag": {"bilingual": False, "edition": "", "vipTime": ""},
            },
        ]
    }
}

MOCK_SEARCH_RESPONSE = {
    "anime": [
        {
            "anime_sn": "37943",
            "acg_sn": "141647",
            "title": "葬送的芙莉蓮",
            "cover": "https://example.com/cover.jpg",
            "score": 9.1,
            "popular": "2537360",
            "highlightTag": {"bilingual": True, "edition": "", "vipTime": ""},
        }
    ]
}

MOCK_DETAIL_RESPONSE = {
    "data": {
        "anime": {
            "anime_sn": 37943,
            "acg_sn": 141647,
            "title": "葬送的芙莉蓮",
            "cover": "https://example.com/cover.jpg",
            "content": "勇者欣梅爾打倒魔王後…",
            "total_volume": 28,
            "upload_time": "2023/9/29",
            "season_start": "2023/9/29",
            "season_end": "2024/3/22",
            "popular": 2537360,
            "score": 9.1,
            "rating": 1,
            "tags": ["奇幻冒險"],
            "category": 3,
            "director": "齋藤圭一郎",
            "publisher": "Aniplex",
            "maker": "Madhouse",
            "volumes": {
                "0": [{"volume": 1, "video_sn": 1000001, "state": 2, "cover": ""}]
            },
            "favorite": False,
        }
    }
}

MOCK_INDEX_RESPONSE = {
    "data": {
        "hotAnime": [
            {
                "anime_sn": "37943",
                "acg_sn": "141647",
                "title": "葬送的芙莉蓮",
            }
        ],
        "newAdded": [],
    }
}


@pytest.fixture
def client():
    """Client with zero cooldown so tests run fast."""
    return BahamutAnimeClient(cooldown=0, max_retries=3, timeout=5)


# ── get_anime_list ─────────────────────────────────────────────────────────────

@responses_lib.activate
def test_get_anime_list_success(client):
    responses_lib.add(
        responses_lib.GET,
        f"{MOBILE_API_BASE}/v2/list.php",
        json=MOCK_LIST_RESPONSE,
        status=200,
    )
    result = client.get_anime_list(category=0, page=1)
    assert len(result) == 2
    assert all(isinstance(item, AnimeItem) for item in result)
    assert result[0].title == "葬送的芙莉蓮"
    assert result[0].anime_sn == 37943


@responses_lib.activate
def test_get_anime_list_empty(client):
    responses_lib.add(
        responses_lib.GET,
        f"{MOBILE_API_BASE}/v2/list.php",
        json={"data": {"animeList": []}},
        status=200,
    )
    result = client.get_anime_list(category=0, page=999)
    assert result == []


@responses_lib.activate
def test_get_anime_list_retry_then_success(client):
    """First two calls return 500, third returns 200 — retry logic should succeed."""
    responses_lib.add(
        responses_lib.GET, f"{MOBILE_API_BASE}/v2/list.php", status=500
    )
    responses_lib.add(
        responses_lib.GET, f"{MOBILE_API_BASE}/v2/list.php", status=500
    )
    responses_lib.add(
        responses_lib.GET,
        f"{MOBILE_API_BASE}/v2/list.php",
        json=MOCK_LIST_RESPONSE,
        status=200,
    )
    result = client.get_anime_list()
    assert len(result) == 2


@responses_lib.activate
def test_get_anime_list_fails_after_max_retries(client):
    """All 3 attempts return 500 — should raise BahamutApiError."""
    for _ in range(3):
        responses_lib.add(
            responses_lib.GET, f"{MOBILE_API_BASE}/v2/list.php", status=500
        )
    with pytest.raises(BahamutApiError):
        client.get_anime_list()


# ── search ─────────────────────────────────────────────────────────────────────

@responses_lib.activate
def test_search_success(client):
    responses_lib.add(
        responses_lib.GET,
        f"{MOBILE_API_BASE}/v1/search.php",
        json=MOCK_SEARCH_RESPONSE,
        status=200,
    )
    result = client.search("芙莉蓮")
    assert len(result) == 1
    assert result[0].score == 9.1
    assert result[0].cover_url == "https://example.com/cover.jpg"


@responses_lib.activate
def test_search_empty_results(client):
    responses_lib.add(
        responses_lib.GET,
        f"{MOBILE_API_BASE}/v1/search.php",
        json={"anime": []},
        status=200,
    )
    result = client.search("不存在的動畫xyz")
    assert result == []


# ── get_anime_detail ───────────────────────────────────────────────────────────

@responses_lib.activate
def test_get_anime_detail_success(client):
    responses_lib.add(
        responses_lib.GET,
        f"{MOBILE_API_BASE}/v3/video.php",
        json=MOCK_DETAIL_RESPONSE,
        status=200,
    )
    detail = client.get_anime_detail(37943)
    assert isinstance(detail, AnimeDetail)
    assert detail.title == "葬送的芙莉蓮"
    assert detail.director == "齋藤圭一郎"
    assert len(detail.volumes["0"]) == 1


@responses_lib.activate
def test_get_anime_detail_no_anime_data_raises(client):
    responses_lib.add(
        responses_lib.GET,
        f"{MOBILE_API_BASE}/v3/video.php",
        json={"data": {"anime": {}}},
        status=200,
    )
    with pytest.raises(BahamutApiError):
        client.get_anime_detail(99999)


# ── get_index ──────────────────────────────────────────────────────────────────

@responses_lib.activate
def test_get_index_success(client):
    responses_lib.add(
        responses_lib.GET,
        f"{MOBILE_API_BASE}/v3/index.php",
        json=MOCK_INDEX_RESPONSE,
        status=200,
    )
    data = client.get_index()
    assert "hotAnime" in data
    assert len(data["hotAnime"]) == 1


# ── Request headers ────────────────────────────────────────────────────────────

@responses_lib.activate
def test_mobile_headers_sent(client):
    """Verify the Animad User-Agent is included in every request."""
    responses_lib.add(
        responses_lib.GET,
        f"{MOBILE_API_BASE}/v3/index.php",
        json=MOCK_INDEX_RESPONSE,
        status=200,
    )
    client.get_index()
    sent_headers = responses_lib.calls[0].request.headers
    assert "Animad" in sent_headers.get("User-Agent", "")
    assert sent_headers.get("X-Bahamut-App-Android") == "tw.com.gamer.android.animad"
