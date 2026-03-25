"""
Main application window.

All anime content is sourced from v3/index.php (cached as _index_data)
since v2/list.php is no longer functional (API version restriction).

Navigation IDs — see category_sidebar.py for full map.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.api.client import BahamutAnimeClient
from src.api.models import AnimeItem
from src.ui.anime_detail_dialog import AnimeDetailDialog
from src.ui.anime_grid import AnimeGrid
from src.ui.category_sidebar import (
    CategorySidebar,
    HOME_ID, FAVORITES_ID,
    NEW_SEASON_ID, NEW_ADDED_ID, ALL_ANIME_ID, THEMES_ID,
)
from src.ui.search_bar import SearchBar
from src.utils.cache import ImageCache
from src.utils.store import LocalStore
from src.workers.api_worker import ApiWorker


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self._client = BahamutAnimeClient()
        self._cache = ImageCache()
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(6)

        self._fav_store = LocalStore("favorites.json")

        # Cache of the last v3/index.php response
        self._index_data: dict = {}

        # Score cache: anime_sn → score, populated when detail dialogs load
        self._score_cache: dict[int, float] = {}

        # Current tag selection for 所有動畫 view
        self._current_all_anime_tag: str = "全部"

        self._build_ui()
        self._load_home()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("AnimeTracker — 巴哈姆特動畫瘋")
        self.setMinimumSize(1024, 680)
        self.resize(1280, 800)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._search_bar = SearchBar()
        self._search_bar.searched.connect(self._on_searched)
        root.addWidget(self._search_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, stretch=1)

        self._sidebar = CategorySidebar()
        self._sidebar.category_changed.connect(self._on_category_changed)
        splitter.addWidget(self._sidebar)

        self._grid = AnimeGrid(
            self._cache, self._pool,
            fav_store=self._fav_store,
        )
        self._grid.anime_selected.connect(self._on_anime_selected)
        self._grid.theme_selected.connect(self._on_theme_selected)
        self._grid.tag_filter_changed.connect(self._on_tag_filter_changed)
        splitter.addWidget(self._grid)
        splitter.setSizes([195, 1085])

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("就緒")

    # ── Loading helpers ────────────────────────────────────────────────────────

    def _load_home(self) -> None:
        self._grid.show_loading()
        self._status.showMessage("載入首頁中…")
        worker = ApiWorker(self._client.get_index)
        worker.signals.result.connect(self._on_home_loaded)
        worker.signals.error.connect(self._on_api_error)
        self._pool.start(worker)

    def _load_all_anime(self, tags: str = "全部") -> None:
        self._current_all_anime_tag = tags
        self._grid.show_loading()
        msg = f"載入「{tags}」動畫中…" if tags != "全部" else "載入所有動畫中…"
        self._status.showMessage(msg)
        worker = ApiWorker(self._client.get_web_anime_list, tags, 1)
        worker.signals.result.connect(self._on_all_anime_loaded)
        worker.signals.error.connect(self._on_all_anime_error)
        self._pool.start(worker)

    def _load_search(self, keyword: str) -> None:
        self._grid.show_loading()
        self._status.showMessage(f"搜尋「{keyword}」中…")
        worker = ApiWorker(self._client.search, keyword)
        worker.signals.result.connect(self._on_search_loaded)
        worker.signals.error.connect(self._on_api_error)
        self._pool.start(worker)

    # ── Index data helpers ─────────────────────────────────────────────────────

    def _get_new_added(self) -> list[AnimeItem]:
        raw = self._index_data.get("newAdded", []) or []
        return self._client._parse_items(raw)

    def _get_new_anime_items(self) -> list[AnimeItem]:
        raw_new = self._index_data.get("newAnime", {}) or {}
        if isinstance(raw_new, dict):
            items_raw = raw_new.get("date") or raw_new.get("popular") or []
        else:
            items_raw = []
        return self._client._parse_items(items_raw)

    def _get_editorial_cats(self) -> list[tuple[str, list[AnimeItem]]]:
        cats = self._index_data.get("category", []) or []
        result: list[tuple[str, list[AnimeItem]]] = []
        for i, cat in enumerate(cats):
            raw_list = cat.get("list") or []
            items = self._client._parse_items(raw_list)
            if items:
                title = cat.get("title", f"主題 {i + 1}")
                result.append((title, items))
        return result

    def _get_all_items_aggregated(self) -> list[AnimeItem]:
        """Deduplicated union of hotAnime + newAdded + newAnime (fallback for web API failure)."""
        hot = self._client._parse_items(self._index_data.get("hotAnime", []) or [])
        new_added = self._get_new_added()
        new_anime = self._get_new_anime_items()
        seen: set[int] = set()
        result: list[AnimeItem] = []
        for item in hot + new_added + new_anime:
            if item.anime_sn and item.anime_sn not in seen:
                seen.add(item.anime_sn)
                result.append(item)
        return result

    # ── Signal handlers ────────────────────────────────────────────────────────

    def _on_category_changed(self, cat_id: int) -> None:
        self._search_bar.clear()

        if not self._index_data:
            self._grid.show_loading()
            worker = ApiWorker(self._client.get_index)
            worker.signals.result.connect(
                lambda data, cid=cat_id: self._on_deferred_index(data, cid)
            )
            worker.signals.error.connect(self._on_api_error)
            self._pool.start(worker)
            return

        self._route_category(cat_id)

    def _on_deferred_index(self, data: dict, cat_id: int) -> None:
        self._index_data = data
        self._route_category(cat_id)

    def _route_category(self, cat_id: int) -> None:
        if cat_id == HOME_ID:
            self._grid.display_home(self._index_data)
            self._grid.apply_score_cache(self._score_cache)
            self._status.showMessage("就緒")

        elif cat_id == FAVORITES_ID:
            items = self._fav_store.to_anime_items()
            self._grid.display_anime_list(items, title=f"❤  我的最愛（{len(items)} 部）")
            self._grid.apply_score_cache(self._score_cache)
            self._status.showMessage(f"最愛清單：{len(items)} 部動畫")

        elif cat_id == NEW_SEASON_ID:
            self._grid.display_weekly_schedule(self._index_data)
            self._grid.apply_score_cache(self._score_cache)
            items = self._get_new_anime_items()
            self._status.showMessage(f"本季新番：{len(items)} 部動畫")

        elif cat_id == NEW_ADDED_ID:
            new_added = self._get_new_added()
            new_anime = self._get_new_anime_items()
            self._grid.display_new_added(new_added, new_anime)
            self._grid.apply_score_cache(self._score_cache)
            self._status.showMessage(f"新上架：{len(new_added)} 部動畫")

        elif cat_id == ALL_ANIME_ID:
            self._current_all_anime_tag = "全部"
            self._load_all_anime("全部")

        elif cat_id == THEMES_ID:
            editorial_cats = self._get_editorial_cats()
            self._grid.display_editorial_themes(editorial_cats)
            self._status.showMessage(f"推薦主題：{len(editorial_cats)} 個")

    def _on_searched(self, keyword: str) -> None:
        if not keyword:
            if self._index_data:
                self._grid.display_home(self._index_data)
                self._grid.apply_score_cache(self._score_cache)
                self._status.showMessage("就緒")
            else:
                self._load_home()
            return
        self._load_search(keyword)

    def _on_anime_selected(self, anime: AnimeItem) -> None:
        dialog = AnimeDetailDialog(
            anime, self._client, self._cache, self._pool,
            fav_store=self._fav_store,
            parent=self,
        )
        # Capture score as soon as detail loads (before dialog closes)
        dialog.detail_loaded.connect(
            lambda sn, score: self._score_cache.update({sn: score})
        )
        dialog.exec()
        # Update current page card with the loaded score
        if dialog.loaded_score > 0:
            self._grid.update_card_score(anime.anime_sn, dialog.loaded_score)

    def _on_theme_selected(self, index: int, title: str) -> None:
        cats = self._index_data.get("category", []) or []
        if index >= len(cats):
            return
        raw_list = cats[index].get("list") or []
        items = self._client._parse_items(raw_list)
        self._grid.display_anime_list(items, title=f"🌟  {title}")
        self._grid.apply_score_cache(self._score_cache)
        self._status.showMessage(f"{title}：{len(items)} 部動畫")

    def _on_tag_filter_changed(self, tag: str) -> None:
        """Tag chip clicked in 所有動畫 — re-fetch from web API with selected tag."""
        self._load_all_anime(tag)

    def _on_all_anime_loaded(self, items: list[AnimeItem]) -> None:
        # Web API items carry scores — store them so other pages can use them
        for item in items:
            if item.score > 0:
                self._score_cache[item.anime_sn] = item.score
        self._grid.display_all_with_filter(items, active_tag=self._current_all_anime_tag)
        self._grid.apply_score_cache(self._score_cache)
        label = self._current_all_anime_tag if self._current_all_anime_tag != "全部" else "所有動畫"
        self._status.showMessage(f"{label}：{len(items)} 部")

    def _on_all_anime_error(self, message: str) -> None:
        # Fallback: use aggregated index data (no tags, chips shown but no filter effect)
        all_items = self._get_all_items_aggregated()
        self._grid.display_all_with_filter(all_items, active_tag="全部")
        self._grid.apply_score_cache(self._score_cache)
        self._status.showMessage(f"所有動畫（離線）：{len(all_items)} 部")

    def _prefetch_scores(self) -> None:
        """Silently fetch web anime list on startup to pre-populate score cache."""
        worker = ApiWorker(self._client.get_web_anime_list, "全部", 1)
        worker.signals.result.connect(self._on_scores_prefetched)
        # No error slot — silent failure is acceptable for prefetch
        self._pool.start(worker)

    def _on_scores_prefetched(self, items: list[AnimeItem]) -> None:
        for item in items:
            if item.score > 0:
                self._score_cache[item.anime_sn] = item.score
        # Apply to whatever page is currently shown
        self._grid.apply_score_cache(self._score_cache)

    def _on_home_loaded(self, data: dict) -> None:
        self._index_data = data
        self._grid.display_home(data)
        self._grid.apply_score_cache(self._score_cache)
        self._status.showMessage("就緒")
        # Pre-populate score cache in background so all pages show scores
        self._prefetch_scores()

    def _on_search_loaded(self, items: list[AnimeItem]) -> None:
        self._grid.display_search_results(items)
        self._grid.apply_score_cache(self._score_cache)
        self._status.showMessage(f"找到 {len(items)} 筆結果")

    def _on_api_error(self, message: str) -> None:
        self._grid.show_error(message)
        self._status.showMessage(f"錯誤：{message}")
        QMessageBox.warning(self, "載入失敗", f"無法取得資料：\n{message}")
