"""
Header search bar widget.

Emits searched(str) with a 400 ms debounce to avoid excessive API calls
while the user is still typing.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from src.ui.theme import Colors


class SearchBar(QWidget):
    """Top-level header widget containing the app logo and search input."""

    searched           = pyqtSignal(str)   # emits the trimmed keyword
    settings_requested = pyqtSignal()      # settings button clicked

    _DEBOUNCE_MS = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(self._DEBOUNCE_MS)
        self._debounce.timeout.connect(self._emit_search)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setAutoFillBackground(True)
        self.setStyleSheet(
            f"background-color: {Colors.BG_SECONDARY}; "
            f"border-bottom: 1px solid {Colors.BORDER};"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)

        logo = QLabel("🎬  AnimeTracker")
        logo.setStyleSheet(
            f"font-size: 16px; font-weight: bold; "
            f"color: {Colors.ACCENT}; margin-right: 24px;"
        )
        layout.addWidget(logo)
        layout.addStretch(1)

        self._input = QLineEdit()
        self._input.setPlaceholderText("搜尋動畫名稱...")
        self._input.setFixedWidth(360)
        self._input.setClearButtonEnabled(True)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._emit_search)
        layout.addWidget(self._input)

        btn = QPushButton("搜尋")
        btn.setFixedWidth(64)
        btn.clicked.connect(self._emit_search)
        layout.addWidget(btn)

        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(34, 34)
        settings_btn.setToolTip("設定")
        settings_btn.setStyleSheet(
            f"QPushButton {{ font-size: 16px; padding: 0;"
            f" background-color: {Colors.BG_CARD};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 5px; }}"
            f" QPushButton:hover {{ background-color: {Colors.ACCENT};"
            f" border-color: {Colors.ACCENT}; color: white; }}"
        )
        settings_btn.clicked.connect(self.settings_requested)
        layout.addWidget(settings_btn)

    def _on_text_changed(self, _: str) -> None:
        self._debounce.stop()
        self._debounce.start()

    def _emit_search(self) -> None:
        self.searched.emit(self._input.text().strip())

    def clear(self) -> None:
        self._input.blockSignals(True)
        self._input.clear()
        self._input.blockSignals(False)
