"""
GroupSidebar — left panel showing groups and the Inbox.

Emits:
  group_selected(str | None)   — user clicked a group (None = Inbox)
  sprites_dropped(list[str], str | None) — sprite IDs dropped onto a group
  group_add_requested()
  group_rename_requested(str)
  group_remove_requested(str)
"""

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

INBOX_KEY = "__inbox__"
MIME_SPRITE_IDS = "application/x-pixelforge-sprite-ids"


class GroupSidebar(QWidget):
    group_selected = Signal(object)               # str group name | None (inbox)
    sprites_dropped = Signal(list, object)        # (sprite_ids, group_name | None)
    group_add_requested = Signal()
    group_rename_requested = Signal(str)
    group_remove_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self):
        self.setObjectName("SidebarWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("LIBRARY")
        header.setObjectName("SidebarHeader")
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.setObjectName("SidebarList")
        self._list.setDragDropMode(QAbstractItemView.DropOnly)
        self._list.setAcceptDrops(True)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list)

        add_btn = QPushButton("+ New Group")
        add_btn.setObjectName("SidebarAddBtn")
        add_btn.clicked.connect(self.group_add_requested)
        layout.addWidget(add_btn)

    # ── public API ────────────────────────────────────────────────────────────

    def set_groups(self, group_names: list, sprite_counts: dict):
        """Rebuild the list. sprite_counts maps group_name → count."""
        current = self.current_group()
        self._list.blockSignals(True)
        self._list.clear()

        # Inbox entry
        inbox_count = sprite_counts.get(INBOX_KEY, 0)
        inbox_item = QListWidgetItem(f"Inbox  ({inbox_count})")
        inbox_item.setData(Qt.UserRole, None)
        inbox_item.setForeground(QColor("#d4892a") if inbox_count else QColor("#666666"))
        self._list.addItem(inbox_item)

        for name in group_names:
            count = sprite_counts.get(name, 0)
            item = QListWidgetItem(f"{name}  ({count})")
            item.setData(Qt.UserRole, name)
            self._list.addItem(item)

        # Restore selection
        self._list.blockSignals(False)
        self._restore_selection(current)

    def current_group(self):
        """Returns current group name (str) or None for Inbox."""
        item = self._list.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None

    def select_group(self, name):
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.UserRole) == name:
                self._list.setCurrentRow(i)
                return

    # ── drag & drop ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasFormat(MIME_SPRITE_IDS):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_SPRITE_IDS):
            item = self._list.itemAt(self._list.mapFromParent(event.position().toPoint()))
            if item:
                self._list.setCurrentItem(item)
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        data = event.mimeData().data(MIME_SPRITE_IDS).data()
        sprite_ids = json.loads(bytes(data).decode())
        item = self._list.itemAt(self._list.mapFromParent(event.position().toPoint()))
        group = item.data(Qt.UserRole) if item else None
        self.sprites_dropped.emit(sprite_ids, group)
        event.acceptProposedAction()

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_selection_changed(self, current, _prev):
        if current:
            self.group_selected.emit(current.data(Qt.UserRole))

    def _on_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        group = item.data(Qt.UserRole)
        if group is None:
            return  # No context menu for Inbox

        menu = QMenu(self)
        rename_action = QAction("Rename…", self)
        rename_action.triggered.connect(lambda: self.group_rename_requested.emit(group))
        remove_action = QAction("Remove Group", self)
        remove_action.triggered.connect(lambda: self.group_remove_requested.emit(group))
        menu.addAction(rename_action)
        menu.addSeparator()
        menu.addAction(remove_action)
        menu.exec(self._list.mapToGlobal(pos))

    def _restore_selection(self, name):
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.UserRole) == name:
                self._list.setCurrentRow(i)
                return
        if self._list.count():
            self._list.setCurrentRow(0)
