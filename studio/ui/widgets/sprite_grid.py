"""
SpriteGrid — icon-mode thumbnail grid for sprites in the selected group.

Drag source: drags sprite IDs as MIME application/x-pixelforge-sprite-ids.
Drop target: accepts PNG/image file drops to add new sprites to the project.

Emits:
  sprite_selected(str)          — single sprite selected (its id)
  sprites_selection_changed(list[str])  — multi-select changed
  files_dropped(list[Path])     — image files dropped onto grid
"""

import io
import json
from pathlib import Path
from typing import List

from PIL import Image
from PySide6.QtCore import QByteArray, QMimeData, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

MIME_SPRITE_IDS = "application/x-pixelforge-sprite-ids"
THUMB_SIZE = 96
STATUS_COLORS = {
    "imported":   "#666666",
    "normalized": "#55aaff",
    "scaled":     "#ffaa55",
    "canvas":     "#55ffaa",
    "remapped":   "#d4892a",
}


def _pil_to_pixmap(img: Image.Image, size: int) -> QPixmap:
    thumb = img.copy()
    thumb.thumbnail((size, size), Image.NEAREST)
    buf = io.BytesIO()
    thumb.save(buf, format="PNG")
    buf.seek(0)
    px = QPixmap()
    px.loadFromData(buf.read())
    return px


def _make_icon(active_path: Path) -> QPixmap:
    try:
        img = Image.open(active_path).convert("RGBA")
        return _pil_to_pixmap(img, THUMB_SIZE)
    except Exception:
        px = QPixmap(THUMB_SIZE, THUMB_SIZE)
        px.fill(QColor("#333"))
        return px


class SpriteGrid(QWidget):
    sprite_selected = Signal(str)
    sprites_selection_changed = Signal(list)
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._sprites: List[dict] = []
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("GridWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel()
        self._header.setObjectName("GridHeader")
        layout.addWidget(self._header)

        self._list = QListWidget()
        self._list.setObjectName("SpriteList")
        self._list.setViewMode(QListWidget.IconMode)
        self._list.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self._list.setGridSize(QSize(THUMB_SIZE + 24, THUMB_SIZE + 36))
        self._list.setResizeMode(QListWidget.Adjust)
        self._list.setWrapping(True)
        self._list.setSpacing(6)
        self._list.setMovement(QListWidget.Static)
        self._list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._list.setDragEnabled(True)
        self._list.setAcceptDrops(True)
        self._list.setDropIndicatorShown(False)
        self._list.setDragDropMode(QAbstractItemView.DragOnly)

        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        # Wire drag
        self._list.startDrag = self._start_drag  # type: ignore[method-assign]

        layout.addWidget(self._list)

        self.setAcceptDrops(True)

    # ── public API ────────────────────────────────────────────────────────────

    def set_sprites(self, project: dict, sprites: List[dict]):
        """Rebuild the grid with a new list of sprites."""
        from backends.project_backend import get_active_file, pipeline_status

        self._project = project
        self._sprites = sprites
        self._list.clear()

        for s in sprites:
            active = get_active_file(project, s)
            icon = _make_icon(active)
            status = pipeline_status(project, s)
            label = f"{s['id']}\n{_status_badge(status)}"

            item = QListWidgetItem(icon, label)
            item.setData(Qt.UserRole, s["id"])
            item.setSizeHint(QSize(THUMB_SIZE + 24, THUMB_SIZE + 36))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            item.setForeground(QColor(STATUS_COLORS.get(status, "#aaa")))
            self._list.addItem(item)

        self._header.setText(f"{len(sprites)} sprite(s)")

    def selected_ids(self) -> List[str]:
        return [item.data(Qt.UserRole) for item in self._list.selectedItems()]

    def refresh_item(self, project: dict, sprite: dict):
        """Refresh a single sprite's thumbnail and status badge without full rebuild."""
        from backends.project_backend import get_active_file, pipeline_status

        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.UserRole) == sprite["id"]:
                active = get_active_file(project, sprite)
                icon = _make_icon(active)
                status = pipeline_status(project, sprite)
                item.setIcon(icon)
                item.setText(f"{sprite['id']}\n{_status_badge(status)}")
                item.setForeground(QColor(STATUS_COLORS.get(status, "#aaa")))
                break

    # ── drag (source) ─────────────────────────────────────────────────────────

    def _start_drag(self, supported_actions):
        ids = self.selected_ids()
        if not ids:
            return
        mime = QMimeData()
        mime.setData(
            MIME_SPRITE_IDS,
            QByteArray(json.dumps(ids).encode()),
        )
        drag = __import__("PySide6.QtGui", fromlist=["QDrag"]).QDrag(self._list)
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)

    # ── drop (file import) ────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"):
                paths.append(p)
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_selection_changed(self):
        ids = self.selected_ids()
        self.sprites_selection_changed.emit(ids)
        if len(ids) == 1:
            self.sprite_selected.emit(ids[0])


def _status_badge(status: str) -> str:
    return {
        "imported":   "○ imported",
        "normalized": "◉ normalized",
        "scaled":     "◕ scaled",
        "canvas":     "● canvas",
        "remapped":   "◆ remapped",
    }.get(status, status)
