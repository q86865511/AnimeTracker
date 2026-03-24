"""
Left-side category filter sidebar.

Navigation IDs:
  -1  = 首頁          (hotAnime from index)
  -2  = 我的最愛       (local favorites store)
  -3  = 觀看清單       (local watchlist store)
  -10 = 本季新番       (newAnime.date from index)
  -11 = 新上架         (newAdded from index)
  -12 = 熱門動畫       (hotAnime from index, same as home)
  -20 .. -27 = 推薦主題 0-7 (editorial categories from index, added dynamically)
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
WATCHLIST_ID   = -3
NEW_ANIME_ID   = -10
NEW_ADDED_ID   = -11
HOT_ANIME_ID   = -12
EDITORIAL_BASE = -20   # -20, -21, ... for each editorial category


class CategorySidebar(QWidget):
    """Fixed-width sidebar with navigation and dynamically loaded editorial categories."""

    category_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(190)
        self.setStyleSheet(f"background-color: {Colors.BG_SECONDARY};")
        self._editorial_header_row: int = -1
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Branding strip
        brand = QLabel("🎬  動畫追蹤器")
        brand.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {Colors.ACCENT};"
            f" background-color: {Colors.BG_HEADER}; padding: 14px 16px 12px 16px;"
        )
        layout.addWidget(brand)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {Colors.BORDER}; max-height: 1px;")
        layout.addWidget(sep)

        self._list = QListWidget()
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setStyleSheet(
            f"QListWidget {{ background-color: {Colors.BG_SECONDARY}; border: none; }}"
            f"QListWidget::item {{ padding: 9px 14px; color: {Colors.TEXT_SECONDARY};"
            f"  border-radius: 4px; margin: 1px 4px; }}"
            f"QListWidget::item:selected {{ background-color: {Colors.ACCENT}; color: white; }}"
            f"QListWidget::item:hover:!selected {{ background-color: {Colors.BG_CARD};"
            f"  color: {Colors.TEXT_PRIMARY}; }}"
        )
        layout.addWidget(self._list)

        # ── 導覽 ──
        self._add_section_header("導覽")
        self._add_item("🏠  首頁",      HOME_ID)
        self._add_item("❤  我的最愛",   FAVORITES_ID)
        self._add_item("📖  觀看清單",  WATCHLIST_ID)

        # ── 動畫列表 ──
        self._add_section_header("動畫列表")
        self._add_item("🔥  熱門動畫",   HOT_ANIME_ID)
        self._add_item("🗓  本季新番",   NEW_ANIME_ID)
        self._add_item("🆕  新上架",     NEW_ADDED_ID)

        self._list.setCurrentRow(1)   # row 0 = section header, row 1 = 首頁
        self._list.currentItemChanged.connect(self._on_item_changed)

    # ── Public methods ─────────────────────────────────────────────────────────

    def set_editorial_categories(self, categories: list[tuple[str, int]]) -> None:
        """
        Dynamically add editorial category entries to the sidebar.

        categories: list of (title, id) where id = EDITORIAL_BASE - index.
        Called once after the index data is loaded.
        """
        if not categories:
            return
        if self._editorial_header_row >= 0:
            return  # already set

        self._add_section_header("推薦主題")
        self._editorial_header_row = self._list.count() - 1

        for title, cat_id in categories:
            self._add_item(f"  {title}", cat_id)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _add_section_header(self, text: str) -> None:
        item = QListWidgetItem(text.upper())
        item.setData(Qt.ItemDataRole.UserRole, None)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        f = item.font()
        f.setPointSize(8)
        item.setFont(f)
        item.setForeground(Qt.GlobalColor.darkGray)
        self._list.addItem(item)

    def _add_item(self, label: str, cat_id: int) -> QListWidgetItem:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, cat_id)
        self._list.addItem(item)
        return item

    # ── Slot ───────────────────────────────────────────────────────────────────

    def _on_item_changed(
        self, current: QListWidgetItem | None, _prev: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        cat_id = current.data(Qt.ItemDataRole.UserRole)
        if cat_id is None:
            return
        self.category_changed.emit(cat_id)
