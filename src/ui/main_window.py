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
    HOME_ID, FAVORITES_ID, WATCHLIST_ID,
    NEW_ANIME_ID, NEW_ADDED_ID, HOT_ANIME_ID,
    EDITORIAL_BASE,
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
        self._watch_store = LocalStore("watchlist.json")

        # Cache of the last v3/index.php response
        self._index_data: dict = {}

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
            watch_store=self._watch_store,
        )
        self._grid.anime_selected.connect(self._on_anime_selected)
        splitter.addWidget(self._grid)
        splitter.setSizes([190, 1090])

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

    def _load_search(self, keyword: str) -> None:
        self._grid.show_loading()
        self._status.showMessage(f"搜尋「{keyword}」中…")
        worker = ApiWorker(self._client.search, keyword)
        worker.signals.result.connect(self._on_search_loaded)
        worker.signals.error.connect(self._on_api_error)
        self._pool.start(worker)

    # ── Index section helpers (no additional API call) ─────────────────────────

    def _show_section(self, key: str, title: str) -> None:
        """Display a top-level list from the cached index data."""
        raw = self._index_data.get(key, []) or []
        items = self._client._parse_items(raw)
        self._grid.display_anime_list(items, title=title)
        self._status.showMessage(f"{title}：{len(items)} 部動畫")

    def _show_editorial(self, cat_index: int) -> None:
        """Display an editorial category from the cached index data."""
        cats = self._index_data.get("category", []) or []
        if cat_index >= len(cats):
            self._grid.show_error("分類資料不存在")
            return
        cat = cats[cat_index]
        raw = cat.get("list", []) or []
        items = self._client._parse_items(raw)
        title = cat.get("title", f"推薦主題 {cat_index + 1}")
        self._grid.display_anime_list(items, title=title)
        self._status.showMessage(f"{title}：{len(items)} 部動畫")

    # ── Signal handlers ────────────────────────────────────────────────────────

    def _on_category_changed(self, cat_id: int) -> None:
        self._search_bar.clear()

        if cat_id == HOME_ID:
            if self._index_data:
                self._grid.display_home(self._index_data)
                self._status.showMessage("就緒")
            else:
                self._load_home()

        elif cat_id == FAVORITES_ID:
            items = self._fav_store.to_anime_items()
            self._grid.display_anime_list(items, title=f"❤  我的最愛（{len(items)} 部）")
            self._status.showMessage(f"最愛清單：{len(items)} 部動畫")

        elif cat_id == WATCHLIST_ID:
            items = self._watch_store.to_anime_items()
            self._grid.display_anime_list(items, title=f"📖  觀看清單（{len(items)} 部）")
            self._status.showMessage(f"觀看清單：{len(items)} 部動畫")

        elif cat_id == HOT_ANIME_ID:
            self._show_section("hotAnime", "🔥  熱門動畫")

        elif cat_id == NEW_ANIME_ID:
            # newAnime is {"date": [...], "popular": [...]}; show by date
            raw = self._index_data.get("newAnime", {}) or {}
            items = self._client._parse_items(raw.get("date") or raw.get("popular") or [])
            self._grid.display_anime_list(items, title="🗓  本季新番")
            self._status.showMessage(f"本季新番：{len(items)} 部動畫")

        elif cat_id == NEW_ADDED_ID:
            self._show_section("newAdded", "🆕  新上架")

        elif cat_id <= EDITORIAL_BASE:
            cat_index = EDITORIAL_BASE - cat_id   # -20 → 0, -21 → 1, …
            self._show_editorial(cat_index)

    def _on_searched(self, keyword: str) -> None:
        if not keyword:
            if self._index_data:
                self._grid.display_home(self._index_data)
                self._status.showMessage("就緒")
            else:
                self._load_home()
            return
        self._load_search(keyword)

    def _on_anime_selected(self, anime: AnimeItem) -> None:
        dialog = AnimeDetailDialog(
            anime, self._client, self._cache, self._pool,
            fav_store=self._fav_store,
            watch_store=self._watch_store,
            parent=self,
        )
        dialog.exec()

    def _on_home_loaded(self, data: dict) -> None:
        self._index_data = data
        self._grid.display_home(data)
        self._status.showMessage("就緒")

        # Populate sidebar with editorial categories
        cats = data.get("category", []) or []
        editorial = [
            (c.get("title", f"主題 {i+1}"), EDITORIAL_BASE - i)
            for i, c in enumerate(cats)
            if c.get("list")
        ]
        self._sidebar.set_editorial_categories(editorial)

    def _on_search_loaded(self, items: list[AnimeItem]) -> None:
        self._grid.display_search_results(items)
        self._status.showMessage(f"找到 {len(items)} 筆結果")

    def _on_api_error(self, message: str) -> None:
        self._grid.show_error(message)
        self._status.showMessage(f"錯誤：{message}")
        QMessageBox.warning(self, "載入失敗", f"無法取得資料：\n{message}")
