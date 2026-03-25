"""
Anime detail dialog.

Opens when the user clicks an anime card. Shows basic info immediately from
AnimeItem data, then fetches full AnimeDetail in the background to populate
the description, score, and episode list.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QThreadPool, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.api.client import BahamutAnimeClient
from src.api.models import AnimeItem, AnimeDetail, VOLUME_TYPE_NAMES
from src.ui.theme import Colors
from src.utils.cache import ImageCache
from src.workers.api_worker import ApiWorker
from src.workers.image_worker import ImageWorker


class AnimeDetailDialog(QDialog):
    """Modal dialog displaying full information about one anime."""

    detail_loaded = pyqtSignal(int, float)   # (anime_sn, score)

    def __init__(
        self,
        anime: AnimeItem,
        client: BahamutAnimeClient,
        cache: ImageCache,
        pool: QThreadPool,
        fav_store=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._anime = anime
        self._client = client
        self._cache = cache
        self._pool = pool
        self._fav_store = fav_store

        self.setWindowTitle(anime.title)
        self.setMinimumSize(760, 580)
        self.resize(860, 660)
        self.setModal(True)
        self._loaded_score: float = 0.0

        self._build_ui()
        QTimer.singleShot(0, self._start_loading)

    @property
    def loaded_score(self) -> float:
        """Score returned by AnimeDetail after async load; 0 if not yet loaded."""
        return self._loaded_score

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Scrollable content area ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll, stretch=1)

        content = QWidget()
        content.setStyleSheet(f"background-color: {Colors.BG_DIALOG};")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 24, 24, 16)
        self._content_layout.setSpacing(10)
        scroll.setWidget(content)

        # ── Top: cover + basic info ──────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(24)

        # Cover image
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(160, 225)
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setStyleSheet(
            f"background-color: {Colors.BG_CARD}; border-radius: 8px;"
            f" color: {Colors.TEXT_MUTED}; font-size: 18px;"
        )
        self._cover_label.setText("⋯")
        top.addWidget(self._cover_label, 0, Qt.AlignmentFlag.AlignTop)

        # Info panel (right of cover)
        info = QVBoxLayout()
        info.setSpacing(8)

        title_lbl = QLabel(self._anime.title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {Colors.TEXT_PRIMARY};"
        )
        info.addWidget(title_lbl)

        # Score row — stored as instance variable so we can update it later
        score_row = QHBoxLayout()
        score_row.setSpacing(6)
        score_val = self._anime.score_display
        score_color = Colors.STAR_COLOR if self._anime.score else Colors.TEXT_MUTED
        self._star_lbl = QLabel(f"★ {score_val}")
        self._star_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {score_color};"
        )
        score_row.addWidget(self._star_lbl)
        if self._anime.popular:
            pop_lbl = QLabel(f"  👁 {self._anime.popular_display}")
            pop_lbl.setStyleSheet(
                f"font-size: 13px; color: {Colors.TEXT_SECONDARY};"
            )
            score_row.addWidget(pop_lbl)
        score_row.addStretch()
        info.addLayout(score_row)

        # Highlight badges
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        if self._anime.highlight_tag.bilingual:
            badge_row.addWidget(self._badge("雙語", Colors.BADGE_BILINGUAL))
        if self._anime.highlight_tag.new_arrival:
            badge_row.addWidget(self._badge("新上架", Colors.BADGE_NEW))
        if self._anime.highlight_tag.edition:
            badge_row.addWidget(
                self._badge(self._anime.highlight_tag.edition, Colors.ACCENT_DARK)
            )
        badge_row.addStretch()
        if badge_row.count() > 1:
            info.addLayout(badge_row)

        # Placeholder for detail rows (inserted later)
        self._detail_rows_widget = QWidget()
        self._detail_rows_layout = QVBoxLayout(self._detail_rows_widget)
        self._detail_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_rows_layout.setSpacing(4)
        info.addWidget(self._detail_rows_widget)

        info.addStretch()

        # Favourite toggle button
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        if self._fav_store is not None:
            self._fav_btn = QPushButton()
            self._fav_btn.setFixedHeight(34)
            self._fav_btn.clicked.connect(self._toggle_favorite)
            self._update_fav_btn()
            action_row.addWidget(self._fav_btn)

        action_row.addStretch()
        info.addLayout(action_row)

        top.addLayout(info, stretch=1)
        self._content_layout.addLayout(top)

        # Divider
        div = QLabel()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {Colors.BORDER};")
        self._content_layout.addWidget(div)

        # ── Description ──────────────────────────────────────────────────────
        self._loading_lbl = QLabel("載入詳細資料中…")
        self._loading_lbl.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 12px; padding: 4px 0;"
        )
        self._content_layout.addWidget(self._loading_lbl)

        self._desc = QTextEdit()
        self._desc.setReadOnly(True)
        self._desc.setMinimumHeight(80)
        self._desc.setMaximumHeight(130)
        self._desc.hide()
        self._content_layout.addWidget(self._desc)

        # ── Episode area ─────────────────────────────────────────────────────
        self._episode_area = QWidget()
        self._episode_area.hide()
        ep_layout = QVBoxLayout(self._episode_area)
        ep_layout.setContentsMargins(0, 4, 0, 0)
        ep_layout.setSpacing(8)
        self._ep_inner_layout = ep_layout
        self._content_layout.addWidget(self._episode_area)

        self._content_layout.addStretch()

        # ── Bottom button bar ────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setContentsMargins(16, 8, 16, 12)

        open_btn = QPushButton("在動畫瘋觀看 ↗")
        open_btn.setProperty("accent", "true")
        open_btn.clicked.connect(self._open_bahamut)
        bar.addWidget(open_btn)

        bar.addStretch()

        close_btn = QPushButton("關閉")
        close_btn.clicked.connect(self.accept)
        bar.addWidget(close_btn)

        root.addLayout(bar)

    # ── Async loading ──────────────────────────────────────────────────────────

    def _start_loading(self) -> None:
        worker = ApiWorker(self._client.get_anime_detail, self._anime.anime_sn)
        worker.signals.result.connect(self._on_detail_loaded)
        worker.signals.error.connect(self._on_detail_error)
        self._pool.start(worker)

        img_worker = ImageWorker(
            self._anime.anime_sn, self._anime.cover_url, self._cache
        )
        img_worker.signals.loaded.connect(self._on_image_loaded)
        self._pool.start(img_worker)

    def _on_detail_loaded(self, detail: AnimeDetail) -> None:
        self._loading_lbl.hide()

        if detail.title:
            self.setWindowTitle(detail.title)

        # Update score from detail (detail.score is reliable; AnimeItem.score may be 0)
        if detail.score:
            self._loaded_score = detail.score
            self._star_lbl.setText(f"★ {detail.score_display}")
            self._star_lbl.setStyleSheet(
                f"font-size: 22px; font-weight: bold; color: {Colors.STAR_COLOR};"
            )
            self.detail_loaded.emit(self._anime.anime_sn, detail.score)

        rows: list[tuple[str, str]] = []
        if detail.rating_name:
            rows.append(("分級", detail.rating_name))
        if detail.season_start:
            period = detail.season_start
            if detail.season_end:
                period += f" ～ {detail.season_end}"
            rows.append(("播期", period))
        if detail.director:
            rows.append(("導演", detail.director))
        if detail.maker:
            rows.append(("製作", detail.maker))
        if detail.tags:
            rows.append(("標籤", "  ".join(f"#{t}" for t in detail.tags)))

        for key, val in rows:
            self._detail_rows_layout.addWidget(self._info_row(key, val))

        if detail.content:
            self._desc.setPlainText(detail.content)
            self._desc.show()

        self._populate_episodes(detail)

    def _populate_episodes(self, detail: AnimeDetail) -> None:
        if not detail.volumes:
            return

        for vtype_key, vol_items in detail.volumes.items():
            if not vol_items:
                continue
            type_name = VOLUME_TYPE_NAMES.get(vtype_key, f"類型 {vtype_key}")

            header = QLabel(type_name)
            header.setStyleSheet(
                f"font-size: 13px; font-weight: bold; color: {Colors.ACCENT};"
                " padding-top: 6px;"
            )
            self._ep_inner_layout.addWidget(header)

            # Flow layout using wrapped QHBoxLayouts
            ep_row = QHBoxLayout()
            ep_row.setSpacing(4)
            for i, vol in enumerate(vol_items[:50]):
                btn = QPushButton(str(vol.volume))
                btn.setFixedHeight(34)
                btn.setMinimumWidth(44)
                btn.setStyleSheet("font-size: 14px;")
                btn.setToolTip(f"第 {vol.volume} 集")
                url = f"https://ani.gamer.com.tw/animeVideo.php?sn={vol.video_sn}"
                btn.clicked.connect(
                    lambda checked, u=url: QDesktopServices.openUrl(QUrl(u))
                )
                ep_row.addWidget(btn)
                if (i + 1) % 8 == 0:
                    ep_row.addStretch()
                    self._ep_inner_layout.addLayout(ep_row)
                    ep_row = QHBoxLayout()
                    ep_row.setSpacing(4)

            if ep_row.count():
                ep_row.addStretch()
                self._ep_inner_layout.addLayout(ep_row)

        self._episode_area.show()

    def _on_detail_error(self, message: str) -> None:
        self._loading_lbl.setText(f"⚠  載入失敗：{message}")
        self._loading_lbl.setStyleSheet(
            f"color: {Colors.ACCENT}; font-size: 12px; padding: 4px 0;"
        )

    def _on_image_loaded(self, _sn: int, data: bytes) -> None:
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if pixmap.isNull():
            return
        scaled = pixmap.scaled(
            160, 225,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width() - 160) // 2
        y = (scaled.height() - 225) // 2
        cropped = scaled.copy(x, y, 160, 225)
        self._cover_label.setPixmap(cropped)
        self._cover_label.setText("")

    # ── Favourite toggle ───────────────────────────────────────────────────────

    def _toggle_favorite(self) -> None:
        if self._fav_store:
            self._fav_store.toggle(self._anime)
            self._update_fav_btn()

    def _update_fav_btn(self) -> None:
        is_fav = self._fav_store.contains(self._anime.anime_sn)
        if is_fav:
            self._fav_btn.setText("♥  從最愛移除")
            self._fav_btn.setStyleSheet(
                f"background-color: {Colors.HEART_COLOR}; color: white;"
                " border: none; border-radius: 5px; padding: 5px 14px;"
            )
        else:
            self._fav_btn.setText("♡  加入最愛")
            self._fav_btn.setStyleSheet("")

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _info_row(key: str, value: str) -> QLabel:
        lbl = QLabel(f"<span style='color:{Colors.TEXT_MUTED}'>{key}</span>"
                     f"<span style='color:{Colors.TEXT_SECONDARY}'>　{value}</span>")
        lbl.setWordWrap(True)
        return lbl

    @staticmethod
    def _badge(text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 11px; color: white; background-color: {color}; "
            "border-radius: 4px; padding: 2px 8px;"
        )
        lbl.setFixedHeight(22)
        return lbl

    def _open_bahamut(self) -> None:
        url = f"https://ani.gamer.com.tw/animeRef.php?sn={self._anime.anime_sn}"
        QDesktopServices.openUrl(QUrl(url))
