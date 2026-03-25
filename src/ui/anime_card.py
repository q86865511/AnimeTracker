"""
Clickable anime card widget.

Card: 185 × 310 px  |  Cover: 185 × 248 px  |  Info: 62 px

Overlay:  ❤ favourite QPushButton on cover top-right.
          QPushButton is used (not QLabel subclass) because PyQt6's C++ virtual
          dispatch reliably intercepts clicks on QPushButton, whereas instance-level
          mousePressEvent overrides on QLabel are not guaranteed to work.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.api.models import AnimeItem
from src.ui.theme import Colors

CARD_W  = 185
CARD_H  = 310
COVER_W = 185
COVER_H = 248

_FAV_BTN_SIZE = 28          # px, square
_FAV_BTN_FONT = 16          # pt for heart icon


class AnimeCard(QFrame):
    """Single anime card. Emits clicked(AnimeItem) when the user clicks it."""

    clicked     = pyqtSignal(object)
    fav_changed = pyqtSignal(int, bool)   # (anime_sn, is_added)

    def __init__(
        self,
        anime: AnimeItem,
        fav_store=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.anime      = anime
        self._fav_store = fav_store

        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("AnimeCard")
        self._apply_style(hovered=False)
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Cover image
        self._cover = QLabel()
        self._cover.setFixedSize(COVER_W, COVER_H)
        self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover.setStyleSheet(
            f"background-color: {Colors.BG_CARD}; border-radius: 6px 6px 0 0;"
            f" color: {Colors.TEXT_MUTED}; font-size: 22px;"
        )
        self._cover.setText("⋯")
        layout.addWidget(self._cover)

        # Info section
        info = QWidget()
        info.setFixedHeight(CARD_H - COVER_H)
        info.setStyleSheet("background: transparent;")
        il = QVBoxLayout(info)
        il.setContentsMargins(7, 5, 7, 5)
        il.setSpacing(3)

        self._title_lbl = QLabel(self.anime.title)
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._title_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 500; color: {Colors.TEXT_PRIMARY};"
        )
        self._title_lbl.setMaximumHeight(40)
        il.addWidget(self._title_lbl)

        # Score + popularity row
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._score_lbl = QLabel()
        self._refresh_score()
        row.addWidget(self._score_lbl)
        row.addStretch()

        if self.anime.popular:
            pop = QLabel(self.anime.popular_display)
            pop.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED};")
            row.addWidget(pop)

        il.addLayout(row)
        layout.addWidget(info)

        # ── Overlay badges ────────────────────────────────────────────────────
        y = 4
        if self.anime.highlight_tag.bilingual:
            self._add_badge("雙語", Colors.BADGE_BILINGUAL, 4, y)
            y += 20
        if self.anime.highlight_tag.new_arrival:
            self._add_badge("NEW", Colors.BADGE_NEW, 4, y)

        # ── Favourite button (child of _cover so it's always above the pixmap) ──
        # Must be a child of self._cover, NOT a sibling.
        # A sibling QPushButton positioned via move() + raise_() can still lose
        # mouse events to the layout-managed QLabel in PyQt6's C++ dispatch.
        # As a child of _cover, Qt routes clicks to the button first, then
        # propagates up to _cover and AnimeCard only if not consumed.
        if self._fav_store is not None:
            self._fav_btn = QPushButton(parent=self._cover)
            self._fav_btn.setFixedSize(_FAV_BTN_SIZE, _FAV_BTN_SIZE)
            self._fav_btn.setFlat(True)
            self._fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._fav_btn.move(COVER_W - _FAV_BTN_SIZE - 4, 4)
            self._fav_btn.clicked.connect(self._on_fav_clicked)
            self._fav_btn.raise_()
            self._refresh_fav_btn()
            self._fav_btn.show()

    # ── Public ────────────────────────────────────────────────────────────────

    def set_image(self, data: bytes) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            COVER_W, COVER_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width()  - COVER_W) // 2
        y = (scaled.height() - COVER_H) // 2
        self._cover.setPixmap(scaled.copy(x, y, COVER_W, COVER_H))
        self._cover.setText("")
        # Re-raise and show the fav button so it stays on top after image is set
        if self._fav_store is not None and hasattr(self, "_fav_btn"):
            self._fav_btn.raise_()
            self._fav_btn.show()

    # ── Private ───────────────────────────────────────────────────────────────

    def _add_badge(self, text: str, color: str, x: int, y: int) -> None:
        badge = QLabel(text, parent=self)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"font-size: 9px; color: white; background-color: {color};"
            " border-radius: 3px; padding: 1px 5px;"
        )
        badge.move(x, y)
        badge.adjustSize()
        badge.show()

    def _refresh_score(self) -> None:
        if self.anime.score:
            self._score_lbl.setText(f"★ {self.anime.score_display}")
            self._score_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.STAR_COLOR};"
            )
        else:
            self._score_lbl.setText("★  --")
            self._score_lbl.setStyleSheet(
                f"font-size: 12px; color: {Colors.TEXT_MUTED};"
            )

    def _refresh_fav_btn(self) -> None:
        is_fav = self._fav_store.contains(self.anime.anime_sn)
        c = Colors
        size = _FAV_BTN_FONT
        if is_fav:
            self._fav_btn.setText("❤")
            self._fav_btn.setStyleSheet(
                f"QPushButton {{ color: {c.HEART_COLOR}; font-size: {size}px;"
                f" background-color: rgba(0,0,0,160); border: none; border-radius: 14px; }}"
                f" QPushButton:hover {{ background-color: rgba(0,0,0,200); }}"
            )
            self._fav_btn.setToolTip("從最愛移除")
        else:
            self._fav_btn.setText("♡")
            self._fav_btn.setStyleSheet(
                f"QPushButton {{ color: {c.HEART_OUTLINE}; font-size: {size}px;"
                f" background-color: rgba(0,0,0,140); border: none; border-radius: 14px; }}"
                f" QPushButton:hover {{ color: {c.HEART_COLOR}; background-color: rgba(0,0,0,200); }}"
            )
            self._fav_btn.setToolTip("加入最愛")

    def _on_fav_clicked(self) -> None:
        """QPushButton.clicked — does not propagate to parent card's mousePressEvent."""
        if self._fav_store:
            is_added = self._fav_store.toggle(self.anime)
            self._refresh_fav_btn()
            self.fav_changed.emit(self.anime.anime_sn, is_added)

    # ── Hover / click ──────────────────────────────────────────────────────────

    def _apply_style(self, hovered: bool) -> None:
        border = Colors.ACCENT if hovered else Colors.BORDER
        bg     = Colors.BG_CARD_HOVER if hovered else Colors.BG_CARD
        self.setStyleSheet(
            f"#AnimeCard {{ background-color: {bg};"
            f"  border: 1px solid {border}; border-radius: 6px; }}"
        )

    def enterEvent(self, event) -> None:
        self._apply_style(hovered=True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_style(hovered=False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.anime)
        super().mousePressEvent(event)
