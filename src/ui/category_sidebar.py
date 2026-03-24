"""
Left-side navigation sidebar.

Navigation IDs:
  -1  = 首頁          (hotAnime — recent hot titles)
  -2  = 我的最愛       (local favourites store)
  -10 = 本季新番       (newAnime sorted by weekly schedule)
  -11 = 新上架         (newAdded + load-more from newAnime)
  -12 = 所有動畫       (aggregated list + genre filter chips)
  -13 = 推薦主題       (editorial category panels)
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import Colors

HOME_ID        = -1
FAVORITES_ID   = -2
NEW_SEASON_ID  = -10
NEW_ADDED_ID   = -11
ALL_ANIME_ID   = -12
THEMES_ID      = -13


class CategorySidebar(QWidget):
    """Fixed-width sidebar with static navigation items."""

    category_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(195)
        self.setStyleSheet(f"background-color: {Colors.BG_SECONDARY};")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Branding strip
        brand = QLabel("🎬  動畫追蹤器")
        brand.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {Colors.ACCENT};"
            f" background-color: {Colors.BG_HEADER};"
            " padding: 15px 16px 13px 16px;"
        )
        layout.addWidget(brand)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {Colors.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        self._list = QListWidget()
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self._list)

        # ── 導覽 ──
        self._add_section("導覽")
        self._add_item("🏠  首頁",      HOME_ID)
        self._add_item("❤  我的最愛",   FAVORITES_ID)

        # ── 動畫列表 ──
        self._add_section("動畫列表")
        self._add_item("🗓  本季新番",  NEW_SEASON_ID)
        self._add_item("🆕  新上架",    NEW_ADDED_ID)
        self._add_item("🎬  所有動畫",  ALL_ANIME_ID)

        # ── 主題 ──
        self._add_section("主題")
        self._add_item("🌟  推薦主題",  THEMES_ID)

        # Select 首頁 (row 1, row 0 is section header)
        self._list.setCurrentRow(1)
        self._list.currentItemChanged.connect(self._on_changed)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _add_section(self, text: str) -> None:
        item = QListWidgetItem(text.upper())
        item.setData(Qt.ItemDataRole.UserRole, None)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        f = item.font()
        f.setPointSize(8)
        item.setFont(f)
        item.setForeground(Qt.GlobalColor.darkGray)
        self._list.addItem(item)

    def _add_item(self, label: str, cat_id: int) -> None:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, cat_id)
        self._list.addItem(item)

    # ── Slot ───────────────────────────────────────────────────────────────────

    def _on_changed(
        self, current: QListWidgetItem | None, _prev: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        cat_id = current.data(Qt.ItemDataRole.UserRole)
        if cat_id is None:
            return
        self.category_changed.emit(cat_id)
