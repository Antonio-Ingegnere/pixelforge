from PySide6.QtCore import Qt
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
    """QGraphicsView with Ctrl+scroll zoom and drag-to-pan."""

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

    def set_pixmap(self, pixmap: QPixmap):
        self._item.setPixmap(pixmap)
        self._scene.setSceneRect(self._item.boundingRect())
        self.fitInView(self._item, Qt.KeepAspectRatio)

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


class ImageViewer(QWidget):
    """
    Shows an image with zoom/pan. Falls back to a placeholder label when empty.
    Label is shown above the view (optional, pass label_text to constructor).
    """

    def __init__(self, label_text: str = "", parent=None):
        super().__init__(parent)
        self._stack = QStackedWidget()

        self._placeholder = QLabel(label_text or "No image")
        self._placeholder.setObjectName("ViewerPlaceholder")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._view = _PixmapView()

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
        self._view.set_pixmap(pixmap)
        self._stack.setCurrentIndex(1)

    def clear(self):
        self._stack.setCurrentIndex(0)

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
