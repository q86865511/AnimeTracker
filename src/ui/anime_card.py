"""
Clickable anime card widget displayed inside the anime grid.

Card dimensions: 185 × 310 px
  - Cover image: 185 × 248 px
  - Info section: 62 px  (title + score/popularity row)
  - Overlay buttons on cover (top-right): favorite ❤ and watchlist 🔖

Image loading is handled externally by AnimeGrid via set_image().
Favorite / watchlist stores are passed in optionally.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.api.models import AnimeItem
from src.ui.theme import Colors

CARD_W  = 185
CARD_H  = 310
COVER_W = 185
COVER_H = 248


# ── Overlay button ──────────────────────────────────────────────────────────────

class _OverlayBtn(QLabel):
    """
    Icon label that intercepts mouse-press without propagating to the parent card.

    Subclassing QLabel is required because PyQt6's C++ virtual dispatch
    does not honour instance-level method overrides.
    """
    pressed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(26, 26)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed.emit()
            event.accept()   # stop propagation to parent AnimeCard
        else:
            super().mousePressEvent(event)


# ── Main card ──────────────────────────────────────────────────────────────────

class AnimeCard(QFrame):
    """Single anime card. Emits clicked(AnimeItem) when the user clicks it."""

    clicked = pyqtSignal(object)

    def __init__(
        self,
        anime: AnimeItem,
        fav_store=None,
        watch_store=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.anime = anime
        self._fav_store   = fav_store
        self._watch_store = watch_store

        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("AnimeCard")
        self._apply_style(hovered=False)
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Cover image area
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
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(7, 5, 7, 5)
        info_layout.setSpacing(3)

        # Title (2 lines max)
        self._title = QLabel(self.anime.title)
        self._title.setWordWrap(True)
        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._title.setStyleSheet(
            f"font-size: 12px; color: {Colors.TEXT_PRIMARY};"
        )
        self._title.setMaximumHeight(38)
        info_layout.addWidget(self._title)

        # Score and popularity row (always visible)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(4)

        self._score_lbl = QLabel()
        self._refresh_score_label()
        bottom.addWidget(self._score_lbl)
        bottom.addStretch()

        if self.anime.popular:
            pop = QLabel(self.anime.popular_display)
            pop.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
            bottom.addWidget(pop)

        info_layout.addLayout(bottom)
        layout.addWidget(info)

        # ── Overlay badges and buttons ────────────────────────────────────────
        # (parented directly to card frame, above the layout)

        overlay_y = 4   # vertical start for top-row overlays

        # Bilingual badge (top-left)
        if self.anime.highlight_tag.bilingual:
            self._add_badge("雙語", Colors.BADGE_BILINGUAL, 4, overlay_y)
            overlay_y += 20

        # New-arrival badge (top-left, below bilingual)
        if self.anime.highlight_tag.new_arrival:
            self._add_badge("NEW", Colors.BADGE_NEW, 4, overlay_y)

        # Watchlist button (top-right)
        if self._watch_store is not None:
            self._watch_btn = _OverlayBtn(parent=self)
            self._watch_btn.move(COVER_W - 30, 4)
            self._refresh_watch_btn()
            self._watch_btn.pressed.connect(self._on_watch_pressed)
            self._watch_btn.show()

        # Favorite button (top-right, left of watchlist)
        if self._fav_store is not None:
            x_fav = (COVER_W - 58) if self._watch_store is not None else (COVER_W - 30)
            self._fav_btn = _OverlayBtn(parent=self)
            self._fav_btn.move(x_fav, 4)
            self._refresh_fav_btn()
            self._fav_btn.pressed.connect(self._on_fav_pressed)
            self._fav_btn.show()

    # ── Public interface ───────────────────────────────────────────────────────

    def set_image(self, data: bytes) -> None:
        """Called from the main thread after ImageWorker emits loaded()."""
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

    # ── Private helpers ────────────────────────────────────────────────────────

    def _add_badge(self, text: str, color: str, x: int, y: int) -> QLabel:
        badge = QLabel(text, parent=self)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"font-size: 9px; color: white; background-color: {color};"
            " border-radius: 3px; padding: 1px 5px;"
        )
        badge.move(x, y)
        badge.adjustSize()
        badge.show()
        return badge

    def _refresh_score_label(self) -> None:
        if self.anime.score:
            self._score_lbl.setText(f"★ {self.anime.score_display}")
            self._score_lbl.setStyleSheet(
                f"font-size: 11px; color: {Colors.STAR_COLOR};"
            )
        else:
            self._score_lbl.setText("★  --")
            self._score_lbl.setStyleSheet(
                f"font-size: 11px; color: {Colors.TEXT_MUTED};"
            )

    def _refresh_fav_btn(self) -> None:
        is_fav = self._fav_store.contains(self.anime.anime_sn)
        if is_fav:
            self._fav_btn.setText("❤")
            self._fav_btn.setStyleSheet(
                f"color: {Colors.HEART_COLOR}; font-size: 15px;"
                " background-color: rgba(0,0,0,150); border-radius: 13px;"
            )
            self._fav_btn.setToolTip("從最愛移除")
        else:
            self._fav_btn.setText("♡")
            self._fav_btn.setStyleSheet(
                f"color: {Colors.HEART_OUTLINE}; font-size: 15px;"
                " background-color: rgba(0,0,0,150); border-radius: 13px;"
            )
            self._fav_btn.setToolTip("加入最愛")

    def _refresh_watch_btn(self) -> None:
        is_watch = self._watch_store.contains(self.anime.anime_sn)
        if is_watch:
            self._watch_btn.setText("📖")
            self._watch_btn.setStyleSheet(
                f"color: {Colors.WATCH_COLOR}; font-size: 13px;"
                " background-color: rgba(0,0,0,150); border-radius: 13px;"
            )
            self._watch_btn.setToolTip("從觀看清單移除")
        else:
            self._watch_btn.setText("🔖")
            self._watch_btn.setStyleSheet(
                f"color: {Colors.WATCH_OUTLINE}; font-size: 13px;"
                " background-color: rgba(0,0,0,150); border-radius: 13px;"
            )
            self._watch_btn.setToolTip("加入觀看清單")

    def _on_fav_pressed(self) -> None:
        if self._fav_store:
            self._fav_store.toggle(self.anime)
            self._refresh_fav_btn()

    def _on_watch_pressed(self) -> None:
        if self._watch_store:
            self._watch_store.toggle(self.anime)
            self._refresh_watch_btn()

    # ── Hover / click ──────────────────────────────────────────────────────────

    def _apply_style(self, hovered: bool) -> None:
        border = Colors.ACCENT if hovered else Colors.BORDER
        bg     = Colors.BG_CARD_HOVER if hovered else Colors.BG_CARD
        self.setStyleSheet(
            f"#AnimeCard {{"
            f"  background-color: {bg};"
            f"  border: 1px solid {border};"
            f"  border-radius: 6px;"
            f"}}"
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
