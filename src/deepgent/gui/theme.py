"""Blender-style dark theme: dense, compact, small controls, flat chrome.

A single QSS string plus a palette. Colors follow Blender's dark theme
family: near-black editors, mid-gray widgets, a desaturated blue accent,
tight padding and small (~20px) control heights.
"""

# Palette (Blender-ish dark).
BG_WINDOW = "#2b2b2b"
BG_EDITOR = "#1d1d1d"
BG_PANEL = "#252525"
BG_WIDGET = "#3a3a3a"
BG_WIDGET_HOVER = "#464646"
BG_WIDGET_PRESSED = "#5680c2"
BORDER = "#151515"
BORDER_LIGHT = "#3a3a3a"
TEXT = "#d6d6d6"
TEXT_DIM = "#9a9a9a"
ACCENT = "#5680c2"
ACCENT_HOVER = "#6a90cc"
OK = "#6ab04c"
FAIL = "#e05a4d"
WARN = "#d8a657"
MONO = "Consolas, 'DejaVu Sans Mono', 'Liberation Mono', monospace"

QSS = f"""
* {{
    outline: 0;
    font-size: 11px;
}}
QWidget {{
    background-color: {BG_WINDOW};
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QMainWindow, QDockWidget {{
    background-color: {BG_EDITOR};
}}
QDockWidget {{
    titlebar-close-icon: none;
    font-weight: 600;
    color: {TEXT_DIM};
}}
QDockWidget::title {{
    background-color: {BG_PANEL};
    padding: 3px 6px;
    border-bottom: 1px solid {BORDER};
}}
QLabel {{
    background: transparent;
}}
QLabel[role="h1"] {{
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
}}
QLabel[role="dim"] {{
    color: {TEXT_DIM};
}}
QLabel[role="mono"] {{
    font-family: {MONO};
    color: {TEXT_DIM};
}}
QLabel[role="ok"] {{ color: {OK}; font-weight: 600; }}
QLabel[role="fail"] {{ color: {FAIL}; font-weight: 600; }}
QLabel[role="warn"] {{ color: {WARN}; font-weight: 600; }}

QPushButton {{
    background-color: {BG_WIDGET};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 3px 10px;
    min-height: 18px;
    color: {TEXT};
}}
QPushButton:hover {{ background-color: {BG_WIDGET_HOVER}; }}
QPushButton:pressed {{ background-color: {ACCENT}; }}
QPushButton:disabled {{ color: #6a6a6a; background-color: #313131; }}
QPushButton[role="accent"] {{
    background-color: {ACCENT};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton[role="accent"]:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton[role="danger"] {{ background-color: #7a3630; color: #ffdad5; }}
QPushButton[role="danger"]:hover {{ background-color: #8f3e37; }}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {BG_EDITOR};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 2px 5px;
    min-height: 18px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QPlainTextEdit[role="log"] {{
    font-family: {MONO};
    font-size: 11px;
    background-color: #161616;
    color: #c8c8c8;
    border: 1px solid {BORDER};
}}
QTextBrowser[role="response"] {{
    font-size: 13px;
    background-color: {BG_EDITOR};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 8px 12px;
}}
QComboBox::drop-down {{ border: 0; width: 16px; }}
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
}}

QListWidget, QTreeWidget, QTableWidget, QTableView {{
    background-color: {BG_EDITOR};
    border: 1px solid {BORDER};
    alternate-background-color: #212121;
    gridline-color: {BORDER};
}}
QListWidget::item, QTreeWidget::item {{ padding: 2px 4px; }}
QListWidget::item:selected, QTreeWidget::item:selected,
QTableView::item:selected {{
    background-color: {ACCENT};
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: {BG_PANEL};
    color: {TEXT_DIM};
    padding: 2px 6px;
    border: 0;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
}}

QToolBar {{
    background-color: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
    spacing: 2px;
    padding: 2px;
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px 6px;
    color: {TEXT};
}}
QToolButton:hover {{ background-color: {BG_WIDGET_HOVER}; }}
QToolButton:checked {{ background-color: {ACCENT}; color: #ffffff; }}

QStatusBar {{
    background-color: {BG_PANEL};
    border-top: 1px solid {BORDER};
    color: {TEXT_DIM};
}}
QStatusBar::item {{ border: 0; }}

QGroupBox {{
    border: 1px solid {BORDER_LIGHT};
    border-radius: 4px;
    margin-top: 14px;
    padding: 6px;
    font-weight: 600;
    color: {TEXT_DIM};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}
QFrame[role="card"] {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}

QProgressBar {{
    background-color: {BG_EDITOR};
    border: 1px solid {BORDER};
    border-radius: 3px;
    text-align: center;
    height: 14px;
    color: {TEXT};
}}
QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 2px; }}

QScrollBar:vertical {{ background: {BG_EDITOR}; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: #4a4a4a; min-height: 24px; border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{ background: #5a5a5a; }}
QScrollBar:horizontal {{ background: {BG_EDITOR}; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: #4a4a4a; min-width: 24px; border-radius: 5px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

QTabBar::tab {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    padding: 4px 12px;
    border: 1px solid {BORDER};
    border-bottom: 0;
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
}}
QTabBar::tab:selected {{ background: {BG_WIDGET}; color: {TEXT}; }}
QSplitter::handle {{ background: {BORDER}; }}
QToolTip {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {ACCENT};
    padding: 2px 5px;
}}
"""
