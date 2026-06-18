"""
PixelForge Studio — global QSS stylesheet.

Color tokens
  BG_0  #0e0e0e  image viewer canvas
  BG_1  #111111  grid area
  BG_2  #161616  sidebar / bottom bar
  BG_3  #1c1c1c  inspector / main panels
  BG_4  #202020  input fields
  BG_5  #262626  buttons (resting)
  BG_6  #2a2a2a  border / separator
  BG_7  #333333  hover for inputs
  BG_8  #3c3c3c  scrollbar handles

  TEXT_0 #eeeeee  active titles
  TEXT_1 #cccccc  primary text
  TEXT_2 #aaaaaa  secondary / checkboxes
  TEXT_3 #777777  muted labels
  TEXT_4 #505050  section headers / hints
  TEXT_5 #3a3a3a  disabled / very muted

  ACCENT        #d4892a  amber highlight
  ACCENT_BG     #8a5a14  amber button background
  ACCENT_TEXT   #f0c060  amber button text
  ACCENT_BORDER #a06a1c  amber button border
"""

STYLESHEET = """

/* ── RESET / GLOBAL ──────────────────────────────────────────────────────── */

* {
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
    outline: none;
}

QWidget {
    background-color: #1c1c1c;
    color: #cccccc;
    border: none;
}

QMainWindow, QMainWindow > QWidget {
    background-color: #111111;
}

QLabel {
    background-color: transparent;
    color: #cccccc;
    border: none;
}

/* ── TOP BAR ──────────────────────────────────────────────────────────────── */

#TopBar {
    background-color: #141414;
    border-bottom: 1px solid #252525;
}

#AppTitle {
    color: #d4892a;
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 1px;
    background-color: transparent;
    border: none;
}

#ProjectLabel {
    color: #555555;
    font-size: 11px;
    background-color: transparent;
    border: none;
}

/* ── BUTTONS ─────────────────────────────────────────────────────────────── */

QPushButton {
    background-color: #262626;
    color: #aaaaaa;
    border: 1px solid #333333;
    border-radius: 0px;
    padding: 0px 10px;
    min-height: 24px;
    max-height: 24px;
    text-align: center;
}

QPushButton:hover {
    background-color: #2e2e2e;
    border-color: #444444;
    color: #cccccc;
}

QPushButton:pressed {
    background-color: #1e1e1e;
    color: #888888;
}

QPushButton:disabled {
    color: #3a3a3a;
    background-color: #1e1e1e;
    border-color: #252525;
}

/* Amber accent — Apply Pipeline */
QPushButton#PrimaryBtn {
    background-color: #8a5a14;
    color: #f0c060;
    border: 1px solid #a06a1c;
    border-radius: 0px;
    font-weight: bold;
    min-height: 26px;
    max-height: 26px;
    text-align: center;
}

QPushButton#PrimaryBtn:hover {
    background-color: #a06a1c;
    color: #f8d070;
    border-color: #ba7c24;
}

QPushButton#PrimaryBtn:pressed {
    background-color: #6a440e;
    color: #d4a840;
}

QPushButton#PrimaryBtn:disabled {
    background-color: #252015;
    color: #4a3a20;
    border-color: #2a2218;
}

/* Sidebar "New Group" ghost button */
QPushButton#SidebarAddBtn {
    background-color: transparent;
    border: none;
    border-top: 1px solid #222222;
    color: #505050;
    text-align: left;
    padding: 0px 14px;
    border-radius: 0px;
    min-height: 32px;
    max-height: 32px;
}

QPushButton#SidebarAddBtn:hover {
    background-color: #1c1c1c;
    color: #d4892a;
}

QPushButton#SidebarAddBtn:pressed {
    background-color: #161616;
}

/* ── SIDEBAR ─────────────────────────────────────────────────────────────── */

#SidebarWidget {
    background-color: #161616;
    border-right: 1px solid #232323;
}

#SidebarHeader {
    color: #3d3d3d;
    font-size: 10px;
    background-color: transparent;
    border: none;
    padding: 10px 14px 6px 14px;
}

QListWidget#SidebarList {
    background-color: #161616;
    border: none;
    padding: 0px;
}

QListWidget#SidebarList::item {
    height: 28px;
    padding-left: 14px;
    color: #888888;
    border-left: 2px solid transparent;
    border-radius: 0px;
}

QListWidget#SidebarList::item:selected {
    background-color: #1e1e1e;
    border-left: 2px solid #d4892a;
    color: #e0e0e0;
}

QListWidget#SidebarList::item:hover:!selected {
    background-color: #1a1a1a;
    color: #aaaaaa;
}

/* ── SPRITE GRID ─────────────────────────────────────────────────────────── */

#GridWidget {
    background-color: #111111;
}

#GridHeader {
    color: #3d3d3d;
    font-size: 10px;
    background-color: #111111;
    border: none;
    border-bottom: 1px solid #1a1a1a;
    padding: 5px 10px 4px 10px;
    min-height: 22px;
    max-height: 22px;
}

QListWidget#SpriteList {
    background-color: #111111;
    border: none;
}

QListWidget#SpriteList::item {
    background-color: #191919;
    border: 1px solid #252525;
    border-radius: 2px;
    color: #555555;
    font-size: 10px;
}

QListWidget#SpriteList::item:selected {
    background-color: #1e1e1e;
    border: 1px solid #d4892a;
    color: #cccccc;
}

QListWidget#SpriteList::item:hover:!selected {
    background-color: #1c1c1c;
    border-color: #343434;
    color: #777777;
}

/* ── INSPECTOR ───────────────────────────────────────────────────────────── */

#InspectorPanel {
    background-color: #1c1c1c;
    border-left: 1px solid #232323;
}

#InspectorTitle {
    color: #444444;
    font-size: 11px;
    font-weight: normal;
    background-color: transparent;
    border: none;
    padding: 0px;
}

#InspectorTitleActive {
    color: #dddddd;
    font-size: 12px;
    font-weight: bold;
    background-color: transparent;
    border: none;
    padding: 0px;
}

/* ── IMAGE VIEWER ────────────────────────────────────────────────────────── */

#ViewerTitle {
    color: #444444;
    font-size: 10px;
    background-color: transparent;
    border: none;
    padding: 0px;
}

#ViewerPlaceholder {
    color: #333333;
    font-size: 10px;
    background-color: #0f0f0f;
    border: 1px solid #1e1e1e;
}

QGraphicsView {
    background-color: #0e0e0e;
    border: 1px solid #222222;
    border-radius: 0px;
}

/* ── SECTION HEADERS (QGroupBox) ─────────────────────────────────────────── */

QGroupBox {
    color: #505050;
    font-size: 10px;
    background-color: transparent;
    border: none;
    border-top: 1px solid #272727;
    margin-top: 20px;
    padding-top: 10px;
    padding-bottom: 0px;
    padding-left: 0px;
    padding-right: 0px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 0px;
    top: 4px;
    padding: 0px 6px 0px 0px;
    background-color: #1c1c1c;
    color: #505050;
}

/* ── FORM CONTROLS ───────────────────────────────────────────────────────── */

QSpinBox, QDoubleSpinBox {
    background-color: #1e1e1e;
    border: 1px solid #303030;
    border-radius: 0px;
    color: #cccccc;
    padding: 1px 4px;
    min-height: 22px;
    max-height: 22px;
    selection-background-color: #d4892a;
    selection-color: #000000;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #d4892a;
}

QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: #3a3a3a;
    border-color: #242424;
}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #282828;
    border: none;
    width: 14px;
    border-radius: 0px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #353535;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 6px;
    height: 6px;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 6px;
    height: 6px;
}

QComboBox {
    background-color: #1e1e1e;
    border: 1px solid #303030;
    border-radius: 0px;
    color: #cccccc;
    padding: 1px 8px;
    min-height: 22px;
    max-height: 22px;
}

QComboBox:focus {
    border-color: #d4892a;
}

QComboBox:disabled {
    color: #3a3a3a;
    border-color: #242424;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
    border-left: 1px solid #2a2a2a;
}

QComboBox::down-arrow {
    width: 8px;
    height: 8px;
}

QComboBox QAbstractItemView {
    background-color: #1e1e1e;
    border: 1px solid #3a3a3a;
    border-radius: 0px;
    selection-background-color: #2a2a2a;
    selection-color: #d4892a;
    padding: 2px;
}

/* ── CHECKBOXES ──────────────────────────────────────────────────────────── */

QCheckBox {
    color: #999999;
    spacing: 8px;
    background-color: transparent;
    border: none;
}

QCheckBox:disabled {
    color: #3a3a3a;
}

QCheckBox::indicator {
    width: 13px;
    height: 13px;
    background-color: #1e1e1e;
    border: 1px solid #424242;
    border-radius: 0px;
}

QCheckBox::indicator:checked {
    background-color: #d4892a;
    border-color: #d4892a;
}

QCheckBox::indicator:disabled {
    background-color: #181818;
    border-color: #2a2a2a;
}

QCheckBox::indicator:unchecked:hover {
    border-color: #777777;
}

/* ── SECONDARY TEXT ──────────────────────────────────────────────────────── */

#HintLabel {
    color: #424242;
    font-size: 10px;
    background-color: transparent;
    border: none;
}

#FormLabel {
    color: #666666;
    font-size: 11px;
    background-color: transparent;
    border: none;
}

/* ── BOTTOM BAR ──────────────────────────────────────────────────────────── */

#BottomBar {
    background-color: #161616;
    border-top: 1px solid #232323;
}

#GroupLabel {
    color: #555555;
    font-size: 10px;
    font-weight: bold;
    background-color: transparent;
    border: none;
}

/* ── LOG ─────────────────────────────────────────────────────────────────── */

QPlainTextEdit {
    background-color: #0e0e0e;
    border: none;
    color: #555555;
    font-family: "Menlo", "Monaco", "Consolas", monospace;
    font-size: 10px;
    selection-background-color: #2a2a2a;
    padding: 4px 6px;
}

/* ── SCROLLBARS ──────────────────────────────────────────────────────────── */

QScrollBar:vertical {
    background: transparent;
    width: 5px;
    margin: 0;
    border: none;
}

QScrollBar::handle:vertical {
    background: #333333;
    border-radius: 2px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #484848;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
    width: 0;
}

QScrollBar:horizontal {
    background: transparent;
    height: 5px;
    border: none;
}

QScrollBar::handle:horizontal {
    background: #333333;
    border-radius: 2px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background: #484848;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
    height: 0;
    width: 0;
}

/* ── SPLITTER ────────────────────────────────────────────────────────────── */

QSplitter::handle {
    background-color: #232323;
}

QSplitter::handle:horizontal {
    width: 1px;
}

QSplitter::handle:vertical {
    height: 1px;
}

/* ── TOOLTIPS ────────────────────────────────────────────────────────────── */

QToolTip {
    background-color: #1e1e1e;
    color: #cccccc;
    border: 1px solid #363636;
    padding: 4px 6px;
    border-radius: 0px;
}

/* ── DIALOGS / INPUT ─────────────────────────────────────────────────────── */

QDialog {
    background-color: #1e1e1e;
}

QLineEdit {
    background-color: #1e1e1e;
    border: 1px solid #383838;
    border-radius: 0px;
    color: #cccccc;
    padding: 4px 6px;
    min-height: 22px;
    max-height: 22px;
    selection-background-color: #d4892a;
    selection-color: #000000;
}

QLineEdit:focus {
    border-color: #d4892a;
}

/* ── MENU ────────────────────────────────────────────────────────────────── */

QMenu {
    background-color: #1e1e1e;
    border: 1px solid #333333;
    padding: 4px 0px;
}

QMenu::item {
    padding: 5px 20px;
    color: #cccccc;
    background-color: transparent;
}

QMenu::item:selected {
    background-color: #2a2a2a;
    color: #d4892a;
}

QMenu::separator {
    height: 1px;
    background-color: #2a2a2a;
    margin: 3px 0px;
}

"""
