"""
Global dark theme for AnimeTracker — Bahamut dark-mode inspired.

Import DARK_STYLESHEET and apply once with QApplication.setStyleSheet().
"""


class Colors:
    # ── Backgrounds ───────────────────────────────────────────────────────────
    BG_PRIMARY     = "#0e0e14"
    BG_SECONDARY   = "#13131c"
    BG_CARD        = "#1c1c28"
    BG_CARD_HOVER  = "#262636"
    BG_HEADER      = "#13131c"
    BG_DIALOG      = "#12121a"

    # ── Accent (Bahamut orange-red) ───────────────────────────────────────────
    ACCENT         = "#ff6b35"
    ACCENT_HOVER   = "#ff8a5b"
    ACCENT_DARK    = "#cc5522"

    # ── Text ──────────────────────────────────────────────────────────────────
    TEXT_PRIMARY   = "#f0f0f8"
    TEXT_SECONDARY = "#a8a8bc"
    TEXT_MUTED     = "#505065"

    # ── UI chrome ─────────────────────────────────────────────────────────────
    BORDER           = "#242434"
    SCROLLBAR_BG     = "#0a0a10"
    SCROLLBAR_HANDLE = "#2a2a40"

    # ── Indicators ────────────────────────────────────────────────────────────
    STAR_COLOR      = "#f4c542"
    HEART_COLOR     = "#ff4466"
    HEART_OUTLINE   = "#9090aa"
    BADGE_BILINGUAL = "#1a6b44"
    BADGE_NEW       = "#7722bb"

    # ── Filter chip ───────────────────────────────────────────────────────────
    CHIP_BG         = "#1c1c28"
    CHIP_ACTIVE     = "#ff6b35"
    CHIP_TEXT       = "#a8a8bc"


DARK_STYLESHEET = f"""
/* ── Base ──────────────────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {{
    background-color: {Colors.BG_PRIMARY};
    color: {Colors.TEXT_PRIMARY};
    font-family: "Microsoft JhengHei UI", "微軟正黑體", "Noto Sans TC", sans-serif;
    font-size: 15px;
}}

/* ── Buttons ─────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {Colors.BG_CARD};
    color: {Colors.TEXT_PRIMARY};
    border: 1px solid {Colors.BORDER};
    border-radius: 5px;
    padding: 6px 16px;
    font-size: 14px;
}}
QPushButton:hover {{
    background-color: {Colors.ACCENT};
    border-color: {Colors.ACCENT};
    color: white;
}}
QPushButton:pressed {{
    background-color: {Colors.ACCENT_DARK};
}}
QPushButton:disabled {{
    background-color: #1a1a28;
    color: {Colors.TEXT_MUTED};
    border-color: #1a1a28;
}}

/* ── Inputs ──────────────────────────────────────────────────────── */
QLineEdit {{
    background-color: {Colors.BG_SECONDARY};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    padding: 7px 12px;
    color: {Colors.TEXT_PRIMARY};
    font-size: 15px;
    selection-background-color: {Colors.ACCENT};
}}
QLineEdit:focus {{
    border-color: {Colors.ACCENT};
    background-color: #18182a;
}}

/* ── Lists ───────────────────────────────────────────────────────── */
QListWidget {{
    background-color: {Colors.BG_SECONDARY};
    border: none;
    outline: none;
}}
QListWidget::item {{
    padding: 10px 14px;
    color: {Colors.TEXT_SECONDARY};
    border-radius: 4px;
    margin: 1px 4px;
    font-size: 14px;
}}
QListWidget::item:selected {{
    background-color: {Colors.ACCENT};
    color: white;
}}
QListWidget::item:hover:!selected {{
    background-color: {Colors.BG_CARD};
    color: {Colors.TEXT_PRIMARY};
}}

/* ── Scroll bars ─────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {Colors.BG_PRIMARY};
    width: 6px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {Colors.SCROLLBAR_HANDLE};
    border-radius: 3px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {Colors.ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ height: 0; }}

/* ── Scroll areas ────────────────────────────────────────────────── */
QScrollArea {{ border: none; background-color: {Colors.BG_PRIMARY}; }}

/* ── Splitter ────────────────────────────────────────────────────── */
QSplitter::handle {{ background-color: {Colors.BORDER}; width: 1px; }}

/* ── Text edit ───────────────────────────────────────────────────── */
QTextEdit {{
    background-color: {Colors.BG_SECONDARY};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    padding: 10px;
    color: {Colors.TEXT_PRIMARY};
    font-size: 14px;
    line-height: 1.6;
}}

/* ── Status bar ──────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {Colors.BG_SECONDARY};
    color: {Colors.TEXT_MUTED};
    border-top: 1px solid {Colors.BORDER};
    font-size: 13px;
}}

/* ── Tool tips ───────────────────────────────────────────────────── */
QToolTip {{
    background-color: {Colors.BG_CARD};
    color: {Colors.TEXT_PRIMARY};
    border: 1px solid {Colors.ACCENT};
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 13px;
}}

/* ── Labels ──────────────────────────────────────────────────────── */
QLabel {{ color: {Colors.TEXT_PRIMARY}; background: transparent; }}
"""
