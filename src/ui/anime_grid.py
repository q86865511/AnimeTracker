"""
Scrollable grid of AnimeCard widgets.

Layout: QScrollArea → QWidget → QGridLayout (COLUMNS per row).
Image loading: dispatches one ImageWorker per card into QThreadPool.
Generation counter: prevents stale image callbacks from updating the wrong card.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.api.models import AnimeItem
from src.ui.anime_card import AnimeCard
from src.ui.theme import Colors
from src.utils.cache import ImageCache
from src.workers.image_worker import ImageWorker

COLUMNS      = 5
CARD_SPACING = 14


class AnimeGrid(QWidget):
    """Main content area — a scrollable grid of clickable anime cards."""

    anime_selected = pyqtSignal(object)

    def __init__(
        self,
        image_cache: ImageCache,
        pool: QThreadPool,
        fav_store=None,
        watch_store=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cache       = image_cache
        self._pool        = pool
        self._fav_store   = fav_store
        self._watch_store = watch_store
        self._cards: dict[int, AnimeCard] = {}
        self._generation  = 0
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Breadcrumb / section title
        self._section_label = QLabel("首頁")
        self._section_label.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {Colors.ACCENT};"
            " padding: 12px 20px 8px 20px;"
            f" background-color: {Colors.BG_PRIMARY};"
            f" border-bottom: 1px solid {Colors.BORDER};"
        )
        outer.addWidget(self._section_label)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self._scroll, stretch=1)

        self._container = QWidget()
        self._container.setStyleSheet(f"background-color: {Colors.BG_PRIMARY};")
        self._grid_layout = QGridLayout(self._container)
        self._grid_layout.setContentsMargins(16, 14, 16, 16)
        self._grid_layout.setSpacing(CARD_SPACING)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._container)

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            f"font-size: 15px; color: {Colors.TEXT_MUTED}; padding: 80px;"
        )
        self._status_label.hide()

    # ── Public interface ───────────────────────────────────────────────────────

    def show_loading(self) -> None:
        self._clear()
        self._grid_layout.addWidget(self._status_label, 0, 0, 1, COLUMNS)
        self._status_label.setText("載入中…")
        self._status_label.show()

    def show_error(self, message: str) -> None:
        self._clear()
        self._grid_layout.addWidget(self._status_label, 0, 0, 1, COLUMNS)
        self._status_label.setText(f"⚠  {message}")
        self._status_label.show()

    def display_anime_list(self, anime_list: list[AnimeItem], title: str = "") -> None:
        """Replace current cards with a new list and start image loading."""
        self._generation += 1
        generation = self._generation
        self._clear()

        if title:
            self._section_label.setText(title)

        if not anime_list:
            self._grid_layout.addWidget(self._status_label, 0, 0, 1, COLUMNS)
            self._status_label.setText("沒有找到任何動畫")
            self._status_label.show()
            return

        for idx, anime in enumerate(anime_list):
            row, col = divmod(idx, COLUMNS)
            card = AnimeCard(anime, self._fav_store, self._watch_store)
            card.clicked.connect(self.anime_selected)
            self._grid_layout.addWidget(card, row, col)
            # Use index as fallback key if anime_sn == 0
            key = anime.anime_sn if anime.anime_sn else -(idx + 1)
            self._cards[key] = card

        self._load_images(anime_list, generation)

    def display_home(self, index_data: dict) -> None:
        """Display hotAnime from the v3/index.php response."""
        items: list[AnimeItem] = []
        for raw in index_data.get("hotAnime", []) or []:
            if not isinstance(raw, dict):
                continue
            try:
                items.append(AnimeItem.from_dict(raw))
            except Exception:
                pass

        if not items:
            for raw in index_data.get("newAdded", []) or []:
                if not isinstance(raw, dict):
                    continue
                try:
                    items.append(AnimeItem.from_dict(raw))
                except Exception:
                    pass

        self.display_anime_list(items, title="🔥  熱門動畫")

    def display_search_results(self, anime_list: list[AnimeItem]) -> None:
        self.display_anime_list(
            anime_list, title=f"🔍  搜尋結果（{len(anime_list)} 筆）"
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _clear(self) -> None:
        self._cards.clear()
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w and w is not self._status_label:
                w.deleteLater()
        self._status_label.hide()

    def _load_images(self, anime_list: list[AnimeItem], generation: int) -> None:
        for anime in anime_list:
            if not anime.cover_url:
                continue
            worker = ImageWorker(anime.anime_sn, anime.cover_url, self._cache)
            worker.signals.loaded.connect(
                lambda sn, data, gen=generation: self._on_image_loaded(sn, data, gen)
            )
            self._pool.start(worker)

    def _on_image_loaded(self, anime_sn: int, data: bytes, generation: int) -> None:
        if generation != self._generation:
            return
        card = self._cards.get(anime_sn)
        if card is not None:
            card.set_image(data)
