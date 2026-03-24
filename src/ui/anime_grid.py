"""
Main content area — handles multiple display modes:

  display_anime_list()          Plain card grid (generic)
  display_home()                hotAnime grid
  display_search_results()      Search card grid
  display_weekly_schedule()     本季新番 — cards grouped by weekday
  display_all_with_filter()     所有動畫 — genre filter chips + grid
  display_editorial_themes()    推薦主題 — clickable theme panels
  display_new_added()           新上架  — grid with "載入更多" button

Generation counter prevents stale image callbacks from landing on the wrong cards.
"""
from __future__ import annotations

from collections import defaultdict

from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.api.models import AnimeItem
from src.ui.anime_card import AnimeCard
from src.ui.theme import Colors
from src.utils.cache import ImageCache
from src.workers.image_worker import ImageWorker

COLUMNS      = 10
CARD_SPACING = 14

# Tag chips for 所有動畫 filter bar (matching ani.gamer.com.tw tag taxonomy)
ANIME_TAGS = [
    "動作", "冒險", "奇幻", "異世界", "魔法", "超能力", "科幻", "機甲",
    "校園", "喜劇", "戀愛", "青春", "勵志", "溫馨", "悠閒", "料理",
    "親情", "感人", "運動", "競技", "偶像", "音樂", "職場", "推理",
    "懸疑", "時間穿越", "歷史", "戰爭", "血腥暴力", "靈異神怪", "黑暗",
    "特攝", "BL", "GL",
]

# Weekday names (index 0-6 = 日 Mon…Sat, 7 = irregular)
_WEEKDAY_LABELS = {
    0: "日曜日",
    1: "週一",
    2: "週二",
    3: "週三",
    4: "週四",
    5: "週五",
    6: "週六",
    7: "不定期",
}


class AnimeGrid(QWidget):
    """Main content area supporting multiple display modes."""

    anime_selected    = pyqtSignal(object)          # AnimeItem
    theme_selected    = pyqtSignal(int, str)         # (index, title) for editorial category
    tag_filter_changed = pyqtSignal(str)             # tag name; "全部" = reset

    def __init__(
        self,
        image_cache: ImageCache,
        pool: QThreadPool,
        fav_store=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._cache      = image_cache
        self._pool       = pool
        self._fav_store  = fav_store
        self._cards: dict[int, AnimeCard] = {}
        self._generation = 0
        self._build_ui()

    # ── UI skeleton ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Section breadcrumb
        self._section_label = QLabel("首頁")
        self._section_label.setStyleSheet(
            f"font-size: 17px; font-weight: bold; color: {Colors.ACCENT};"
            " padding: 12px 20px 8px 20px;"
            f" background-color: {Colors.BG_PRIMARY};"
            f" border-bottom: 1px solid {Colors.BORDER};"
        )
        outer.addWidget(self._section_label)

        # Optional filter bar (hidden unless display_all_with_filter is called)
        self._filter_bar = QWidget()
        self._filter_bar.setStyleSheet(
            f"background-color: {Colors.BG_PRIMARY};"
            f" border-bottom: 1px solid {Colors.BORDER};"
        )
        self._filter_bar_layout = QHBoxLayout(self._filter_bar)
        self._filter_bar_layout.setContentsMargins(16, 8, 16, 8)
        self._filter_bar_layout.setSpacing(6)
        self._filter_bar.hide()
        outer.addWidget(self._filter_bar)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self._scroll, stretch=1)

        # Container with a single VBox; the VBox holds the grid widget + extras
        self._container = QWidget()
        self._container.setStyleSheet(f"background-color: {Colors.BG_PRIMARY};")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 16)
        self._container_layout.setSpacing(0)
        self._scroll.setWidget(self._container)

        # Inner grid widget (rebuilt on each display_*)
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet(f"background-color: {Colors.BG_PRIMARY};")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(16, 12, 16, 4)
        self._grid.setSpacing(CARD_SPACING)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._container_layout.addWidget(self._grid_widget)

        # "Load more" button (added to container bottom when needed)
        self._load_more_btn = QPushButton("🔽  載入更多")
        self._load_more_btn.setFixedHeight(42)
        self._load_more_btn.setStyleSheet(
            f"font-size: 14px; background-color: {Colors.BG_CARD};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 6px;"
            f" color: {Colors.TEXT_SECONDARY}; margin: 0 16px;"
        )
        self._load_more_btn.hide()
        self._container_layout.addWidget(self._load_more_btn)

        self._container_layout.addStretch()

        # Status / empty / error label (centred)
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            f"font-size: 16px; color: {Colors.TEXT_MUTED}; padding: 80px;"
        )
        self._status_label.hide()

    # ── Public: generic states ──────────────────────────────────────────────────

    def update_card_score(self, anime_sn: int, score: float) -> None:
        """Update the score display on a specific card (called after detail loads)."""
        card = self._cards.get(anime_sn)
        if card is not None and score:
            card.anime.score = score
            card._refresh_score()

    def apply_score_cache(self, cache: dict[int, float]) -> None:
        """Apply a score cache to all currently visible cards."""
        for anime_sn, score in cache.items():
            card = self._cards.get(anime_sn)
            if card is not None and score > 0:
                card.anime.score = score
                card._refresh_score()

    def show_loading(self) -> None:
        self._clear()
        self._grid.addWidget(self._status_label, 0, 0, 1, COLUMNS)
        self._status_label.setText("載入中…")
        self._status_label.show()

    def show_error(self, message: str) -> None:
        self._clear()
        self._grid.addWidget(self._status_label, 0, 0, 1, COLUMNS)
        self._status_label.setText(f"⚠  {message}")
        self._status_label.show()

    # ── Public: display modes ──────────────────────────────────────────────────

    def display_anime_list(self, anime_list: list[AnimeItem], title: str = "") -> None:
        """Generic flat grid — used for favourites, search results, etc."""
        self._generation += 1
        gen = self._generation
        self._clear()
        if title:
            self._section_label.setText(title)
        if not anime_list:
            self._show_empty()
            return
        self._populate_grid(anime_list)
        self._load_images(anime_list, gen)

    def display_home(self, index_data: dict) -> None:
        items = self._parse_list(index_data.get("hotAnime") or [])
        if not items:
            items = self._parse_list(index_data.get("newAdded") or [])
        self.display_anime_list(items, title="🔥  近期熱播")

    def display_search_results(self, anime_list: list[AnimeItem]) -> None:
        self.display_anime_list(
            anime_list, title=f"🔍  搜尋結果（{len(anime_list)} 筆）"
        )

    def display_weekly_schedule(self, index_data: dict) -> None:
        """
        本季新番 — group newAnime.date items by weekday, show day headers.
        Covers are the anime's own cover (episode thumbnails already filtered
        out by AnimeItem.from_dict via the /2KU/ check).
        """
        self._generation += 1
        gen = self._generation
        self._clear()
        self._section_label.setText("🗓  本季新番")

        raw_new = index_data.get("newAnime", {}) or {}
        if isinstance(raw_new, dict):
            items_raw = raw_new.get("date") or raw_new.get("popular") or []
        else:
            items_raw = []

        items = self._parse_list(items_raw)
        if not items:
            self._show_empty()
            return

        # Deduplicate by anime_sn, keep first occurrence per week
        seen: set[int] = set()
        unique: list[AnimeItem] = []
        for a in items:
            if a.anime_sn not in seen:
                seen.add(a.anime_sn)
                unique.append(a)

        # Group by week field (stored in raw data)
        week_map: dict[int, list[AnimeItem]] = defaultdict(list)
        # We need to re-access the week field — attach it to items via a custom dict pass
        anime_week: dict[int, int] = {}
        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            sn_raw = raw.get("anime_sn") or raw.get("animeSn") or 0
            try:
                sn = int(sn_raw or 0)
            except (ValueError, TypeError):
                sn = 0
            week = int(raw.get("week", 7) or 7)
            if sn:
                anime_week[sn] = week

        for a in unique:
            w = anime_week.get(a.anime_sn, 7)
            week_map[w].append(a)

        # Render in weekday order (0=日, 1=月…6=土, 7=不定期)
        all_shown: list[AnimeItem] = []
        grid_row = 0
        for week_idx in sorted(week_map.keys()):
            group = week_map[week_idx]
            label_text = _WEEKDAY_LABELS.get(week_idx, f"週{week_idx}")

            # Day header spanning all columns
            day_lbl = QLabel(f"  {label_text}")
            day_lbl.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {Colors.TEXT_SECONDARY};"
                f" background-color: {Colors.BG_SECONDARY};"
                " padding: 6px 16px; border-radius: 4px;"
            )
            self._grid.addWidget(day_lbl, grid_row, 0, 1, COLUMNS)
            grid_row += 1

            for col_idx, anime in enumerate(group):
                row_offset, col = divmod(col_idx, COLUMNS)
                card = self._make_card(anime)
                self._grid.addWidget(card, grid_row + row_offset, col)
                self._cards[anime.anime_sn] = card
                all_shown.append(anime)

            grid_row += (len(group) - 1) // COLUMNS + 1

        self._load_images(all_shown, gen)

    def display_new_added(
        self,
        new_added: list[AnimeItem],
        extra_items: list[AnimeItem],
    ) -> None:
        """
        新上架 — show newAdded initially; "載入更多" appends extra_items.
        extra_items: newAnime.date filtered to exclude what's already shown.
        """
        self._generation += 1
        gen = self._generation
        self._clear()
        self._section_label.setText("🆕  新上架")

        if not new_added:
            self._show_empty()
            return

        self._populate_grid(new_added)
        self._load_images(new_added, gen)

        # Load-more button appends extra_items when clicked
        remaining = [a for a in extra_items if a.anime_sn not in {a2.anime_sn for a2 in new_added}]
        if remaining:
            self._setup_load_more(remaining, gen)
        else:
            self._load_more_btn.setText("已顯示全部內容")
            self._load_more_btn.setEnabled(False)
            self._load_more_btn.show()

    def display_all_with_filter(
        self, all_items: list[AnimeItem], active_tag: str = "全部"
    ) -> None:
        """
        所有動畫 — show all_items in a grid with ANIME_TAGS filter chips.
        Clicking a chip emits tag_filter_changed(tag); MainWindow handles the fetch.
        """
        self._generation += 1
        gen = self._generation
        self._clear()
        self._section_label.setText("🎬  所有動畫")

        self._rebuild_filter_bar(active_tag)

        if not all_items:
            self._show_empty()
            return

        self._populate_grid(all_items)
        self._load_images(all_items, gen)

    def display_editorial_themes(
        self,
        categories: list[tuple[str, list[AnimeItem]]],
    ) -> None:
        """
        推薦主題 — show each editorial category as a clickable panel.
        Clicking a panel emits theme_selected(index, title).
        """
        self._generation += 1
        self._clear()
        self._section_label.setText("🌟  推薦主題")

        if not categories:
            self._show_empty()
            return

        for idx, (title, items) in enumerate(categories):
            panel = self._make_theme_panel(idx, title, items[:3])
            row, col = divmod(idx, 2)
            self._grid.addWidget(panel, row, col, 1, 1)

    # ── Private helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_list(raw: object) -> list[AnimeItem]:
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

    def _make_card(self, anime: AnimeItem) -> AnimeCard:
        card = AnimeCard(anime, self._fav_store)
        card.clicked.connect(self.anime_selected)
        return card

    def _populate_grid(self, anime_list: list[AnimeItem]) -> None:
        for idx, anime in enumerate(anime_list):
            row, col = divmod(idx, COLUMNS)
            card = self._make_card(anime)
            self._grid.addWidget(card, row, col)
            key = anime.anime_sn if anime.anime_sn else -(idx + 1)
            self._cards[key] = card

    def _show_empty(self) -> None:
        self._grid.addWidget(self._status_label, 0, 0, 1, COLUMNS)
        self._status_label.setText("沒有找到任何動畫")
        self._status_label.show()

    def _clear(self) -> None:
        self._cards.clear()
        self._filter_bar.hide()
        self._load_more_btn.hide()
        self._load_more_btn.setEnabled(True)
        self._load_more_btn.setText("🔽  載入更多")
        # Disconnect any old load-more connections safely
        try:
            self._load_more_btn.clicked.disconnect()
        except TypeError:
            pass

        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w and w is not self._status_label:
                w.deleteLater()
        self._status_label.hide()

    def _setup_load_more(self, extra: list[AnimeItem], gen: int) -> None:
        self._load_more_btn.show()

        def _on_load_more() -> None:
            if gen != self._generation:
                return
            start_idx = len(self._cards)
            for i, anime in enumerate(extra):
                idx = start_idx + i
                row, col = divmod(idx, COLUMNS)
                card = self._make_card(anime)
                self._grid.addWidget(card, row, col)
                key = anime.anime_sn if anime.anime_sn else -(idx + 1)
                self._cards[key] = card
            self._load_images(extra, gen)
            self._load_more_btn.setText("已顯示全部內容")
            self._load_more_btn.setEnabled(False)

        self._load_more_btn.clicked.connect(_on_load_more)

    def _rebuild_filter_bar(self, active_tag: str = "全部") -> None:
        """Build tag filter chips. Chip clicks emit tag_filter_changed — no in-memory filter."""
        while self._filter_bar_layout.count():
            item = self._filter_bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        label = QLabel("篩選：")
        label.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")
        self._filter_bar_layout.addWidget(label)

        chip_style = (
            f"QPushButton {{ font-size: 12px; color: {Colors.CHIP_TEXT};"
            f" background-color: {Colors.CHIP_BG}; border: 1px solid {Colors.BORDER};"
            f" border-radius: 14px; padding: 0 12px; }}"
            f" QPushButton:checked {{ background-color: {Colors.CHIP_ACTIVE};"
            f" color: white; border-color: transparent; }}"
            f" QPushButton:hover:!checked {{ color: {Colors.TEXT_PRIMARY}; }}"
        )

        def _make_chip(text: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setChecked(text == active_tag)
            btn.setFixedHeight(28)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(chip_style)

            def _on_clicked(checked: bool, _btn: QPushButton = btn, t: str = text) -> None:
                if not checked:
                    # Prevent deselecting — always keep one chip active
                    _btn.setChecked(True)
                    return
                # Uncheck all siblings
                for i in range(self._filter_bar_layout.count()):
                    w = self._filter_bar_layout.itemAt(i).widget()
                    if isinstance(w, QPushButton) and w is not _btn:
                        w.setChecked(False)
                self.tag_filter_changed.emit(t)

            btn.clicked.connect(_on_clicked)
            return btn

        # "全部" always first, then all ANIME_TAGS
        self._filter_bar_layout.addWidget(_make_chip("全部"))
        for tag in ANIME_TAGS:
            self._filter_bar_layout.addWidget(_make_chip(tag))

        self._filter_bar_layout.addStretch()
        self._filter_bar.show()

    def _make_theme_panel(
        self,
        idx: int,
        title: str,
        preview_items: list[AnimeItem],
    ) -> QFrame:
        """A clickable panel representing one editorial category."""
        panel = QFrame()
        panel.setObjectName("ThemePanel")
        panel.setFixedHeight(130)
        panel.setCursor(Qt.CursorShape.PointingHandCursor)
        panel.setStyleSheet(
            "#ThemePanel { background-color: %s; border: 1px solid %s;"
            " border-radius: 8px; }"
            "#ThemePanel:hover { border-color: %s; background-color: %s; }"
            % (Colors.BG_CARD, Colors.BORDER, Colors.ACCENT, Colors.BG_CARD_HOVER)
        )

        h = QHBoxLayout(panel)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(12)

        # Title
        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {Colors.TEXT_PRIMARY};"
        )
        title_lbl.setFixedWidth(160)
        h.addWidget(title_lbl)

        # Mini covers
        for anime in preview_items:
            thumb = QLabel()
            thumb.setFixedSize(72, 100)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet(
                f"background-color: {Colors.BG_SECONDARY}; border-radius: 4px;"
                f" color: {Colors.TEXT_MUTED}; font-size: 14px;"
            )
            thumb.setText("⋯")
            h.addWidget(thumb)
            # Load cover asynchronously
            worker = ImageWorker(anime.anime_sn, anime.cover_url, self._cache)
            worker.signals.loaded.connect(
                lambda sn, data, lbl=thumb: self._set_thumb(lbl, data)
            )
            self._pool.start(worker)

        h.addStretch()

        arr = QLabel("›")
        arr.setStyleSheet(f"font-size: 24px; color: {Colors.TEXT_MUTED};")
        h.addWidget(arr)

        # Click handler
        panel.mousePressEvent = lambda ev, i=idx, t=title: (  # type: ignore[method-assign]
            self.theme_selected.emit(i, t)
            if ev.button() == Qt.MouseButton.LeftButton else None
        )
        return panel

    @staticmethod
    def _set_thumb(label: QLabel, data: bytes) -> None:
        from PyQt6.QtGui import QPixmap
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            scaled = px.scaled(72, 100, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
            x = (scaled.width()  - 72) // 2
            y = (scaled.height() - 100) // 2
            label.setPixmap(scaled.copy(x, y, 72, 100))
            label.setText("")

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
