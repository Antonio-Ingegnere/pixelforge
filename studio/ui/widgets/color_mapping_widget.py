"""
ColorMappingWidget — shows source→palette colour pairs for a remapped sprite.

Each pair: [src swatch] → [tgt swatch]
  • hover over tgt swatch → cursor changes to pointer
  • click tgt swatch      → QMenu listing all palette colours as icon-actions
  • amber arrow           → this pair has a user override
  • "Reset to auto"       → clears the override for that source colour

Signals
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
    override_changed = Signal(str, str)   # (src_hex, tgt_hex | "")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pairs:   List[Pair] = []
        self._palette: List[RGBTuple] = []
        self._hover    = -1
        self.setMouseTracking(True)

    # ── public API ────────────────────────────────────────────────────────────

    def set_data(self, pairs: List[Pair], palette: List[RGBTuple]):
        self._pairs   = pairs
        self._palette = palette
        self._hover   = -1
        rows = (len(pairs) + 1) // 2
        h    = rows * RH + 4
        self.setMinimumHeight(h)
        self.setMaximumHeight(h)
        self.update()

    def clear(self):
        self._pairs   = []
        self._palette = []
        self._hover   = -1
        self.setMinimumHeight(0)
        self.setMaximumHeight(0)
        self.update()

    # ── geometry helpers ──────────────────────────────────────────────────────

    def _col_x(self, col: int) -> int:
        """Left edge of column `col` (0 or 1)."""
        pair_w = SW + AW + SW
        return 2 + col * (pair_w + GAP)

    def _tgt_rect(self, idx: int):
        """(x, y, w, h) of the target swatch for pair idx."""
        col = idx % 2
        row = idx // 2
        x   = self._col_x(col) + SW + AW
        y   = 2 + row * RH + (RH - SW) // 2
        return x, y, SW, SW

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
            p.setPen(QColor("#383838"))
            p.drawRect(x, cy, SW - 1, SW - 1)

            # arrow
            p.setPen(QColor("#d4892a") if is_ovr else QColor("#474747"))
            p.drawText(x + SW, y, AW, RH, Qt.AlignCenter, "→")

            # target swatch
            tx = x + SW + AW
            p.fillRect(tx, cy, SW, SW, QColor(*tgt))
            if i == self._hover:
                pen = QPen(QColor("#d4892a"), 1)
            else:
                pen = QPen(QColor("#383838"), 1)
            p.setPen(pen)
            p.drawRect(tx, cy, SW - 1, SW - 1)

    # ── interaction ───────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event):
        idx = self._hit_tgt(event.x(), event.y())
        if idx != self._hover:
            self._hover = idx
            self.update()
        self.setCursor(Qt.PointingHandCursor if idx >= 0 else Qt.ArrowCursor)

    def leaveEvent(self, _event):
        if self._hover >= 0:
            self._hover = -1
            self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        idx = self._hit_tgt(event.x(), event.y())
        if 0 <= idx < len(self._pairs):
            self._show_picker(idx, event.globalPosition().toPoint())

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
