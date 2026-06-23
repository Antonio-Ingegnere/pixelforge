"""
ColorMappingWidget — shows source→palette colour pairs for a remapped sprite.

Each pair: [src swatch] → [tgt swatch]
  • hover over src or tgt swatch → pointer cursor
  • click src swatch             → select/deselect that source colour
                                   emits source_selected (for viewer highlight)
  • click tgt swatch             → QMenu listing all palette colours as icon-actions
  • amber arrow                  → this pair has a user override
  • "Reset to auto"              → clears the override for that source colour

Signals
  source_selected(src_rgb: tuple | None)
    emitted when user clicks a source swatch; None means deselected
  override_changed(src_hex: str, tgt_hex: str)
    emitted when the user picks a new target; tgt_hex == "" means "clear override"
"""

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

RGBTuple = Tuple[int, int, int]
Pair     = Tuple[RGBTuple, RGBTuple, bool]   # (src, tgt, is_override)

SW = 14   # swatch side
RH = 22   # row height
AW = 18   # arrow column width
GAP = 10  # gap between the two columns


class ColorMappingWidget(QWidget):
    source_selected  = Signal(object)   # (r, g, b) tuple, or None when deselected
    override_changed = Signal(str, str)  # (src_hex, tgt_hex | "")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pairs:           List[Pair]          = []
        self._palette:         List[RGBTuple]      = []
        self._hover_tgt:       int                 = -1
        self._hover_src:       int                 = -1
        self._highlighted_src: Optional[RGBTuple]  = None
        self._highlighted_tgt: Optional[RGBTuple]  = None
        self.setMouseTracking(True)

    # ── public API ────────────────────────────────────────────────────────────

    def set_data(self, pairs: List[Pair], palette: List[RGBTuple]):
        self._pairs   = pairs
        self._palette = palette
        self._hover_tgt = -1
        self._hover_src = -1
        rows = (len(pairs) + 1) // 2
        h    = rows * RH + 4
        self.setMinimumHeight(h)
        self.setMaximumHeight(h)
        self.update()

    def clear(self):
        self._pairs           = []
        self._palette         = []
        self._hover_tgt       = -1
        self._hover_src       = -1
        self._highlighted_src = None
        self._highlighted_tgt = None
        self.setMinimumHeight(0)
        self.setMaximumHeight(0)
        self.update()

    def highlight_source_color(self, rgb: Optional[RGBTuple]):
        """Highlight rows whose source colour matches rgb. Clears target highlight."""
        if rgb is not None and any(src == rgb for src, _, _ in self._pairs):
            self._highlighted_src = rgb
        else:
            self._highlighted_src = None
        self._highlighted_tgt = None
        self.update()

    def highlight_target_color(self, rgb: Optional[RGBTuple]):
        """Highlight rows whose target colour matches rgb. Clears source highlight."""
        if rgb is not None and any(tgt == rgb for _, tgt, _ in self._pairs):
            self._highlighted_tgt = rgb
        else:
            self._highlighted_tgt = None
        self._highlighted_src = None
        self.update()

    # ── geometry helpers ──────────────────────────────────────────────────────

    def _col_x(self, col: int) -> int:
        pair_w = SW + AW + SW
        return 2 + col * (pair_w + GAP)

    def _src_rect(self, idx: int):
        col = idx % 2
        row = idx // 2
        x   = self._col_x(col)
        y   = 2 + row * RH + (RH - SW) // 2
        return x, y, SW, SW

    def _tgt_rect(self, idx: int):
        col = idx % 2
        row = idx // 2
        x   = self._col_x(col) + SW + AW
        y   = 2 + row * RH + (RH - SW) // 2
        return x, y, SW, SW

    def _hit_src(self, mx: int, my: int) -> int:
        for i in range(len(self._pairs)):
            x, y, w, h = self._src_rect(i)
            if x <= mx <= x + w and y <= my <= y + h:
                return i
        return -1

    def _hit_tgt(self, mx: int, my: int) -> int:
        for i in range(len(self._pairs)):
            x, y, w, h = self._tgt_rect(i)
            if x <= mx <= x + w and y <= my <= y + h:
                return i
        return -1

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        if not self._pairs:
            return
        p = QPainter(self)

        for i, (src, tgt, is_ovr) in enumerate(self._pairs):
            col = i % 2
            row = i // 2
            x   = self._col_x(col)
            y   = 2 + row * RH
            cy  = y + (RH - SW) // 2

            # source swatch
            p.fillRect(x, cy, SW, SW, QColor(*src))
            if src == self._highlighted_src:
                pen = QPen(QColor("#d4892a"), 1)
            elif i == self._hover_src:
                pen = QPen(QColor("#888888"), 1)
            else:
                pen = QPen(QColor("#383838"), 1)
            p.setPen(pen)
            p.drawRect(x, cy, SW - 1, SW - 1)

            # arrow
            p.setPen(QColor("#d4892a") if is_ovr else QColor("#474747"))
            p.drawText(x + SW, y, AW, RH, Qt.AlignCenter, "→")

            # target swatch
            tx = x + SW + AW
            p.fillRect(tx, cy, SW, SW, QColor(*tgt))
            if tgt == self._highlighted_tgt or i == self._hover_tgt:
                pen = QPen(QColor("#d4892a"), 1)
            else:
                pen = QPen(QColor("#383838"), 1)
            p.setPen(pen)
            p.drawRect(tx, cy, SW - 1, SW - 1)

    # ── interaction ───────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event):
        tgt_idx = self._hit_tgt(event.x(), event.y())
        src_idx = self._hit_src(event.x(), event.y())
        if tgt_idx != self._hover_tgt or src_idx != self._hover_src:
            self._hover_tgt = tgt_idx
            self._hover_src = src_idx
            self.update()
        self.setCursor(
            Qt.PointingHandCursor if (tgt_idx >= 0 or src_idx >= 0) else Qt.ArrowCursor
        )

    def leaveEvent(self, _event):
        if self._hover_tgt >= 0 or self._hover_src >= 0:
            self._hover_tgt = -1
            self._hover_src = -1
            self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        src_idx = self._hit_src(event.x(), event.y())
        if src_idx >= 0:
            src, _, _ = self._pairs[src_idx]
            if self._highlighted_src == src:
                self._highlighted_src = None
                self.source_selected.emit(None)
            else:
                self._highlighted_src = src
                self.source_selected.emit(src)
            self._highlighted_tgt = None
            self.update()
            return

        tgt_idx = self._hit_tgt(event.x(), event.y())
        if 0 <= tgt_idx < len(self._pairs):
            self._show_picker(tgt_idx, event.globalPosition().toPoint())

    def _show_picker(self, idx: int, gpos):
        src, tgt, is_ovr = self._pairs[idx]
        src_hex = f"{src[0]:02x}{src[1]:02x}{src[2]:02x}"

        menu = QMenu(self)

        for r, g, b in self._palette:
            px = QPixmap(12, 12)
            px.fill(QColor(r, g, b))
            h   = f"{r:02x}{g:02x}{b:02x}"
            act = QAction(QIcon(px), f"  #{h.upper()}", menu)
            act.triggered.connect(
                lambda _checked=False, hx=h: self.override_changed.emit(src_hex, hx)
            )
            menu.addAction(act)

        if is_ovr:
            menu.addSeparator()
            rst = QAction("↺  Reset to auto", menu)
            rst.triggered.connect(
                lambda: self.override_changed.emit(src_hex, "")
            )
            menu.addAction(rst)

        menu.exec(gpos)
