"""
Settings dialog — build / packaging and basic app info.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import Colors

# Project root is three levels up: settings_dialog.py → ui → src → project
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_SPEC_FILE    = _PROJECT_ROOT / "AnimeTracker.spec"


class SettingsDialog(QDialog):
    """Application settings dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setMinimumSize(620, 460)
        self.resize(740, 540)
        self.setModal(True)
        self._process: QProcess | None = None
        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)

        # Header
        header = QLabel("設定")
        header.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {Colors.ACCENT};"
        )
        root.addWidget(header)

        div = QLabel()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {Colors.BORDER};")
        root.addWidget(div)

        # ── Build section ────────────────────────────────────────────────────
        section = QLabel("打包 .exe")
        section.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {Colors.TEXT_PRIMARY};"
            " padding-top: 4px;"
        )
        root.addWidget(section)

        desc = QLabel(
            "使用 PyInstaller 將程式打包為獨立執行的 .exe。\n"
            f"Spec 檔案：{_SPEC_FILE}\n"
            f"輸出位置：{_PROJECT_ROOT / 'dist' / 'AnimeTracker' / 'AnimeTracker.exe'}"
        )
        desc.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_SECONDARY};")
        root.addWidget(desc)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._build_btn = QPushButton("▶  開始打包")
        self._build_btn.setFixedHeight(36)
        self._build_btn.setMinimumWidth(130)
        self._build_btn.clicked.connect(self._start_build)
        if not _SPEC_FILE.exists():
            self._build_btn.setEnabled(False)
            self._build_btn.setToolTip(f"找不到 {_SPEC_FILE}")
        btn_row.addWidget(self._build_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")
        btn_row.addWidget(self._status_lbl)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # Output area
        out_lbl = QLabel("輸出訊息：")
        out_lbl.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED};")
        root.addWidget(out_lbl)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setStyleSheet(
            f"background-color: {Colors.BG_SECONDARY};"
            f" color: {Colors.TEXT_SECONDARY};"
            " font-family: Consolas, 'Courier New', monospace;"
            " font-size: 12px;"
            f" border: 1px solid {Colors.BORDER}; border-radius: 4px;"
        )
        root.addWidget(self._output, stretch=1)

        # Close button bar
        bar = QHBoxLayout()
        bar.addStretch()
        close_btn = QPushButton("關閉")
        close_btn.clicked.connect(self.accept)
        bar.addWidget(close_btn)
        root.addLayout(bar)

    # ── Build logic ────────────────────────────────────────────────────────────

    def _start_build(self) -> None:
        if (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        ):
            return

        self._output.clear()
        self._append("正在啟動 PyInstaller…\n\n")
        self._build_btn.setEnabled(False)
        self._build_btn.setText("⏳  打包中…")
        self._status_lbl.setText("打包中…")
        self._status_lbl.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(_PROJECT_ROOT))
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.start(
            sys.executable,
            ["-m", "PyInstaller", "AnimeTracker.spec", "--clean", "--noconfirm"],
        )

    def _append(self, text: str) -> None:
        self._output.moveCursor(QTextCursor.MoveOperation.End)
        self._output.insertPlainText(text)
        self._output.moveCursor(QTextCursor.MoveOperation.End)

    def _on_stdout(self) -> None:
        data = (
            self._process.readAllStandardOutput()
            .data()
            .decode("utf-8", errors="replace")
        )
        self._append(data)

    def _on_stderr(self) -> None:
        data = (
            self._process.readAllStandardError()
            .data()
            .decode("utf-8", errors="replace")
        )
        self._append(data)

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        if exit_code == 0:
            self._append(
                "\n✔  打包成功！\n"
                f"執行檔位置：{_PROJECT_ROOT / 'dist' / 'AnimeTracker' / 'AnimeTracker.exe'}\n"
            )
            self._build_btn.setText("✔  打包完成")
            self._status_lbl.setText("打包成功")
            self._status_lbl.setStyleSheet("font-size: 13px; color: #4caf50;")
        else:
            self._append(f"\n✘  打包失敗（exit code: {exit_code}）\n")
            self._build_btn.setEnabled(True)
            self._build_btn.setText("▶  重新打包")
            self._status_lbl.setText("打包失敗")
            self._status_lbl.setStyleSheet(
                f"font-size: 13px; color: {Colors.ACCENT};"
            )

    def closeEvent(self, event) -> None:
        # Kill any running build process when dialog is closed
        if (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        ):
            self._process.kill()
        super().closeEvent(event)
