from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class _PixmapView(QGraphicsView):
    """QGraphicsView with Ctrl+scroll zoom, drag-to-pan, and pixel-click detection."""

    pixel_clicked = Signal(object)  # emits (r, g, b) tuple, or None for transparent/outside

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)
        self.setScene(self._scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRenderHint(self.renderHints())
        self.setBackgroundBrush(Qt.black)
        self._qimage = None      # original image data for pixel reading
        self._press_pos = None   # tracks mouse-press position to distinguish click from drag

    def set_pixmap(self, pixmap: QPixmap):
        self._item.setPixmap(pixmap)
        self._qimage = pixmap.toImage()
        self._scene.setSceneRect(self._item.boundingRect())
        self.fitInView(self._item, Qt.KeepAspectRatio)

    def update_display_pixmap(self, pixmap: QPixmap):
        """Swap the displayed pixmap (e.g. for highlight overlay) without resetting zoom/pan."""
        self._item.setPixmap(pixmap)
        self._scene.setSceneRect(self._item.boundingRect())

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._item.pixmap().isNull():
            self.fitInView(self._item, Qt.KeepAspectRatio)

    def mousePressEvent(self, event):
        self._press_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton and self._press_pos is not None:
            if (event.pos() - self._press_pos).manhattanLength() < 4:
                self._emit_pixel_at(event.pos())
        self._press_pos = None

    def _emit_pixel_at(self, viewport_pos):
        if self._qimage is None or self._item.pixmap().isNull():
            return
        scene_pos = self.mapToScene(viewport_pos)
        item_pos  = self._item.mapFromScene(scene_pos)
        x, y = int(item_pos.x()), int(item_pos.y())
        if 0 <= x < self._qimage.width() and 0 <= y < self._qimage.height():
            c = self._qimage.pixelColor(x, y)
            if c.alpha() > 0:
                self.pixel_clicked.emit((c.red(), c.green(), c.blue()))
            else:
                self.pixel_clicked.emit(None)
        else:
            self.pixel_clicked.emit(None)


class ImageViewer(QWidget):
    """
    Shows an image with zoom/pan. Falls back to a placeholder label when empty.
    Supports pixel-click detection and color-based highlight dimming when loaded
    via set_pil_image().
    """

    pixel_clicked = Signal(object)  # (r, g, b) tuple or None

    def __init__(self, label_text: str = "", parent=None):
        super().__init__(parent)
        self._pil_image = None
        self._stack = QStackedWidget()

        self._placeholder = QLabel(label_text or "No image")
        self._placeholder.setObjectName("ViewerPlaceholder")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._view = _PixmapView()
        self._view.pixel_clicked.connect(self.pixel_clicked)

        self._stack.addWidget(self._placeholder)  # index 0 — empty
        self._stack.addWidget(self._view)          # index 1 — image

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if label_text:
            title = QLabel(label_text)
            title.setObjectName("ViewerTitle")
            title.setAlignment(Qt.AlignCenter)
            layout.addWidget(title)
        layout.addWidget(self._stack)

    def set_image(self, pixmap: QPixmap):
        self._pil_image = None
        self._view.set_pixmap(pixmap)
        self._stack.setCurrentIndex(1)

    def set_pil_image(self, pil_image):
        """Load from a PIL Image; enables set_highlight_color."""
        self._pil_image = pil_image
        self._view.set_pixmap(ImageViewer.pixmap_from_pil(pil_image))
        self._stack.setCurrentIndex(1)

    def set_highlight_color(self, rgb):
        """
        Dim all pixels that don't match rgb so matching pixels stand out.
        Pass None to restore the original image.
        Only works when the image was loaded via set_pil_image().
        """
        if self._pil_image is None:
            return
        if rgb is None:
            px = ImageViewer.pixmap_from_pil(self._pil_image)
        else:
            px = ImageViewer.pixmap_from_pil(self._make_dimmed(rgb))
        self._view.update_display_pixmap(px)

    def clear(self):
        self._pil_image = None
        self._stack.setCurrentIndex(0)

    def _make_dimmed(self, rgb):
        import numpy as np
        from PIL import Image as PILImage
        arr = np.array(self._pil_image)   # RGBA uint8
        r, g, b = rgb
        opaque = arr[:, :, 3] > 0
        match  = opaque & (arr[:, :, 0] == r) & (arr[:, :, 1] == g) & (arr[:, :, 2] == b)
        result = arr.copy()
        dim    = opaque & ~match
        result[dim, :3] = (result[dim, :3] * 0.15).astype(np.uint8)
        return PILImage.fromarray(result)

    @staticmethod
    def pixmap_from_pil(pil_image) -> QPixmap:
        """Convert a PIL/Pillow Image to QPixmap."""
        import io
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        buf.seek(0)
        px = QPixmap()
        px.loadFromData(buf.read())
        return px
