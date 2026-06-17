from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget


class PaletteSwatch(QWidget):
    """
    Displays a row of colored squares from a list of (R, G, B) tuples.
    Click a swatch to copy its hex code to the clipboard.
    """

    SWATCH_H = 36

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors: List[Tuple[int, int, int]] = []
        self.setFixedHeight(self.SWATCH_H)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip("Click a color to copy its hex code")

    def set_palette(self, colors: List[Tuple[int, int, int]]):
        self._colors = colors
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        n = len(self._colors)
        if n == 0:
            painter.setPen(QColor("#666"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No palette — run Rebalance")
            return
        cell_w = max(1, self.width() // n)
        for i, (r, g, b) in enumerate(self._colors):
            painter.fillRect(i * cell_w, 0, cell_w, self.height(), QColor(r, g, b))

    def mousePressEvent(self, event):
        n = len(self._colors)
        if n == 0:
            return
        cell_w = max(1, self.width() // n)
        idx = min(event.x() // cell_w, n - 1)
        r, g, b = self._colors[idx]
        hex_code = f"#{r:02X}{g:02X}{b:02X}"
        QApplication.clipboard().setText(hex_code)
        self.setToolTip(f"Copied {hex_code}")
