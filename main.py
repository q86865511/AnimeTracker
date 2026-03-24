"""
AnimeTracker — 巴哈姆特動畫瘋桌面追番工具
Entry point: python main.py
"""
import sys

from PyQt6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui.theme import DARK_STYLESHEET


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("AnimeTracker")
    app.setOrganizationName("AnimeTracker")
    app.setStyleSheet(DARK_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
