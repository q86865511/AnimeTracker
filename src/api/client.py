"""
Bahamut Anime Crazy mobile API client.

Designed to run inside QRunnable worker threads.
Implements thread-safe rate limiting (1 s cooldown) and exponential backoff retry.

API Status Notes (2026-03):
  v2/list.php  — returns "APP版本過舊" for all known versions; DO NOT USE.
  v3/index.php — fully functional; supplies hotAnime, newAdded, newAnime, category.
  v1/search.php — functional; returns items WITH score field.
  v3/video.php  — functional; returns full anime detail.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

import requests

from .models import AnimeItem, AnimeDetail

# ── API configuration ──────────────────────────────────────────────────────────

MOBILE_API_BASE = "https://api.gamer.com.tw/mobile_app/anime"
WEB_API_BASE    = "https://api.gamer.com.tw/anime/v1"

MOBILE_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Animad/1.16.16 (tw.com.gamer.android.animad; build:328; Android 9) okHttp/4.4.0"
    ),
    "X-Bahamut-App-Android": "tw.com.gamer.android.animad",
    "X-Bahamut-App-Version": "328",
    "Accept-Encoding": "gzip",
    "Connection": "Keep-Alive",
}

WEB_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://ani.gamer.com.tw/",
}

DEFAULT_COOLDOWN = 1.0
DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT = 15


class BahamutApiError(Exception):
    """Raised when the API returns an unexpected error after all retries."""


class BahamutAnimeClient:
    """
    Synchronous HTTP client for the Bahamut Anime Crazy mobile API.

    Thread-safe: multiple QRunnable workers can share a single instance.
    A threading.Lock serialises requests and enforces the cooldown period.
    """

    def __init__(
        self,
        cooldown: float = DEFAULT_COOLDOWN,
        max_retries: int = DEFAULT_RETRIES,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._session = requests.Session()
        self._session.headers.update(MOBILE_HEADERS)
        self._cooldown = cooldown
        self._max_retries = max_retries
        self._timeout = timeout
        self._lock = threading.Lock()
        self._last_request_time: float = 0.0

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{MOBILE_API_BASE}/{endpoint}"
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._cooldown:
                time.sleep(self._cooldown - elapsed)

            last_exc: Optional[Exception] = None
            for attempt in range(self._max_retries):
                try:
                    resp = self._session.get(url, params=params, timeout=self._timeout)
                    resp.raise_for_status()
                    self._last_request_time = time.time()
                    data = resp.json()
                    # Detect application-level errors
                    if "error" in data and not data.get("data"):
                        err = data["error"]
                        msg = err.get("message", "API error")
                        raise BahamutApiError(msg)
                    return data
                except BahamutApiError:
                    raise
                except requests.exceptions.RequestException as exc:
                    last_exc = exc
                    if attempt < self._max_retries - 1:
                        time.sleep(2 ** attempt)

            raise BahamutApiError(
                f"Request to {url} failed after {self._max_retries} attempts"
            ) from last_exc

    @staticmethod
    def _parse_items(raw: object) -> list[AnimeItem]:
        """Convert a raw list/dict-of-lists into AnimeItem objects, skipping bad rows."""
        if isinstance(raw, dict):
            # newAnime format: {"date": [...], "popular": [...]}
            raw = raw.get("date") or raw.get("popular") or []
        if not isinstance(raw, list):
            return []
        result = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                result.append(AnimeItem.from_dict(item))
            except Exception:
                pass
        return result

    # ── Public API methods ─────────────────────────────────────────────────────

    def get_index(self) -> dict:
        """
        Fetch homepage data (hot anime, new added, new anime, editorial categories).

        Returns the raw ``data`` dict from v3/index.php.
        """
        data = self._get("v3/index.php")
        return data.get("data", {})

    def search(self, keyword: str) -> list[AnimeItem]:
        """Search anime by keyword. Returns items WITH score field."""
        data = self._get("v1/search.php", {"kw": keyword})
        raw_items = data.get("anime", []) or []
        return self._parse_items(raw_items)

    def get_anime_list(
        self, category: int = 0, page: int = 1, sort: int = 0
    ) -> list[AnimeItem]:
        """
        Fetch paginated anime list by category via v2/list.php.

        NOTE: This endpoint returns "APP版本過舊" in production as of 2026-03.
        The method is retained for unit-test compatibility (tests mock the HTTP layer).
        For live browsing use get_index() sections instead.
        """
        data = self._get("v2/list.php", {"c": category, "page": page, "sort": sort})
        data_section = data.get("data", {})
        raw_items = (
            data_section.get("animeList")
            or data_section.get("anime_list")
            or data_section.get("list")
            or []
        )
        return self._parse_items(raw_items)

    def get_web_anime_list(self, tags: str = "全部", page: int = 1) -> list[AnimeItem]:
        """
        Fetch paginated anime list from web API.

        Unlike the mobile API, this endpoint returns items with ``tags`` field,
        enabling tag-based filtering in the 所有動畫 view.
        URL: https://api.gamer.com.tw/anime/v1/anime_list.php
        ``tags`` can be "全部" for all anime, or a specific tag like "校園".
        """
        url = f"{WEB_API_BASE}/anime_list.php"
        params = {
            "tags": tags,
            "category": "全部",
            "target": "全部",
            "sort": 1,
            "page": page,
        }
        try:
            resp = requests.get(
                url, params=params, headers=WEB_HEADERS, timeout=self._timeout
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise BahamutApiError(f"Web anime list request failed: {exc}") from exc

        data_section = data.get("data", {}) or {}
        raw_items = (
            data_section.get("anime")
            or data_section.get("animeList")
            or data_section.get("list")
            or []
        )
        return self._parse_items(raw_items)

    def get_anime_detail(self, anime_sn: int) -> AnimeDetail:
        """Fetch full detail for an anime by its anime_sn."""
        data = self._get("v3/video.php", {"anime_sn": anime_sn})
        anime_data = data.get("data", {}).get("anime", {})
        if not anime_data:
            raise BahamutApiError(f"No anime data returned for anime_sn={anime_sn}")
        return AnimeDetail.from_dict(anime_data)
