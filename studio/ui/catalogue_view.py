"""
CatalogueView — the main project view.

Owns the project dict (single source of truth).
Wires GroupSidebar ↔ SpriteGrid ↔ SpriteInspector ↔ BottomBar.

Layout:
  ┌─ GroupSidebar ─┬─ SpriteGrid (top) ──────────┐
  │  (left panel)  ├─ SpriteInspector (bottom) ───┤
  │                │                              │
  └────────────────┴──────────────────────────────┘
  └─ BottomBar (palette + pipeline commands + log) ┘
"""

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from backends import project_backend as pb
from backends.normalizer_backend import (
    cmd_rebalance,
    cmd_build,
    cmd_verify,
    cmd_export,
)
from ui.widgets.group_sidebar import GroupSidebar
from ui.widgets.log_panel import LogPanel
from ui.widgets.palette_swatch import PaletteSwatch
from ui.widgets.sprite_grid import SpriteGrid
from ui.widgets.sprite_inspector import SpriteInspector
from workers.normalizer_worker import NormalizerWorker
from workers.pipeline_worker import PipelineWorker


class CatalogueView(QWidget):
    def __init__(self, pool: QThreadPool, parent=None):
        super().__init__(parent)
        self._pool = pool
        self._project: Optional[dict] = None
        self._current_group: Optional[str] = None  # None = Inbox
        self._active_workers = 0
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── top bar ───────────────────────────────────────────────────────────
        root.addWidget(self._build_top_bar())

        # ── main area ─────────────────────────────────────────────────────────
        h_split = QSplitter(Qt.Horizontal)

        self._sidebar = GroupSidebar()
        self._sidebar.setFixedWidth(180)
        self._sidebar.group_selected.connect(self._on_group_selected)
        self._sidebar.sprites_dropped.connect(self._on_sprites_dropped)
        self._sidebar.group_add_requested.connect(self._on_add_group)
        self._sidebar.group_rename_requested.connect(self._on_rename_group)
        self._sidebar.group_remove_requested.connect(self._on_remove_group)

        self._grid = SpriteGrid()
        self._grid.sprite_selected.connect(self._on_sprite_selected)
        self._grid.files_dropped.connect(self._on_files_dropped)

        self._inspector = SpriteInspector()
        self._inspector.pipeline_apply_requested.connect(self._on_pipeline_apply)
        self._inspector.group_changed.connect(self._on_group_changed_for_sprite)
        self._inspector.weight_changed.connect(self._on_weight_changed)

        right_split = QSplitter(Qt.Vertical)
        right_split.addWidget(self._grid)
        right_split.addWidget(self._inspector)
        right_split.setStretchFactor(0, 2)
        right_split.setStretchFactor(1, 3)

        h_split.addWidget(self._sidebar)
        h_split.addWidget(right_split)
        h_split.setStretchFactor(0, 0)
        h_split.setStretchFactor(1, 1)

        root.addWidget(h_split, stretch=1)

        # ── bottom bar ────────────────────────────────────────────────────────
        root.addWidget(self._build_bottom_bar())

        self._set_project_loaded(False)

    def _build_top_bar(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(40)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(8, 4, 8, 4)

        new_btn = QPushButton("New Project…")
        new_btn.clicked.connect(self._on_new_project)
        open_btn = QPushButton("Open Project…")
        open_btn.clicked.connect(self._on_open_project)
        add_btn = QPushButton("+ Add Sprites…")
        add_btn.clicked.connect(self._on_add_sprites_dialog)
        self._add_sprites_btn = add_btn

        self._project_label = QLabel("<i>No project open</i>")
        self._project_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout.addWidget(new_btn)
        layout.addWidget(open_btn)
        layout.addWidget(self._project_label)
        layout.addWidget(add_btn)
        return w

    def _build_bottom_bar(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # palette row
        palette_row = QHBoxLayout()
        self._group_label = QLabel()
        self._group_label.setStyleSheet("font-weight: bold;")
        self._swatch = PaletteSwatch()
        self._swatch.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        palette_row.addWidget(self._group_label)
        palette_row.addWidget(self._swatch, stretch=1)
        layout.addLayout(palette_row)

        # command buttons
        cmd_row = QHBoxLayout()
        self._cmd_btns = {}
        for label, cmd in [
            ("Rebalance", "rebalance"),
            ("Build", "build"),
            ("Verify", "verify"),
            ("Export", "export"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, c=cmd: self._on_palette_command(c))
            cmd_row.addWidget(btn)
            self._cmd_btns[cmd] = btn
        cmd_row.addStretch()
        layout.addLayout(cmd_row)

        # log
        self._log = LogPanel()
        self._log.setFixedHeight(120)
        layout.addWidget(self._log)
        return w

    # ── project loading ───────────────────────────────────────────────────────

    def _on_new_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Choose Project Folder")
        if not directory:
            return
        name, ok = QInputDialog.getText(self, "Project Name", "Name:", text=Path(directory).name)
        if not ok or not name.strip():
            return
        try:
            project = pb.new_project(directory, name.strip())
            self._load_project(project)
            self._log.append(f"Created project '{name}' at {directory}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _on_open_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Open Project Folder")
        if not directory:
            return
        if not pb.is_project_dir(directory):
            QMessageBox.warning(
                self, "Not a project",
                "No project.yaml found in that folder.\nCreate a new project there first."
            )
            return
        try:
            project = pb.load_project(directory)
            self._load_project(project)
            self._log.append(f"Opened project '{project['name']}' ({len(project['sprites'])} sprites)")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _load_project(self, project: dict):
        self._project = project
        self._project_label.setText(f"<b>{project['name']}</b>  —  {project['_dir']}")
        self._current_group = None
        self._set_project_loaded(True)
        self._refresh_sidebar()
        self._refresh_grid()

    def _set_project_loaded(self, loaded: bool):
        self._add_sprites_btn.setEnabled(loaded)
        for btn in self._cmd_btns.values():
            btn.setEnabled(loaded)
        if not loaded:
            self._sidebar.set_groups([], {})
            self._grid.set_sprites({}, [])
            self._inspector.clear()
            self._swatch.set_palette([])
            self._group_label.setText("")

    # ── sidebar refresh ───────────────────────────────────────────────────────

    def _refresh_sidebar(self):
        if not self._project:
            return
        groups = pb.all_groups(self._project)
        counts = {g: len(pb.sprites_in_group(self._project, g)) for g in groups}
        counts["__inbox__"] = len(pb.inbox_sprites(self._project))
        self._sidebar.set_groups(groups, counts)

    # ── grid refresh ──────────────────────────────────────────────────────────

    def _refresh_grid(self):
        if not self._project:
            return
        if self._current_group is None:
            sprites = pb.inbox_sprites(self._project)
        else:
            sprites = pb.sprites_in_group(self._project, self._current_group)
        self._grid.set_sprites(self._project, sprites)
        self._refresh_palette_bar()

    def _refresh_palette_bar(self):
        if self._current_group and self._project:
            self._group_label.setText(f"Group: {self._current_group}")
            colors = pb.load_palette(self._project, self._current_group) or []
            self._swatch.set_palette(colors)
        else:
            self._group_label.setText("Inbox")
            self._swatch.set_palette([])

    # ── sprite adding ─────────────────────────────────────────────────────────

    def _on_add_sprites_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Sprites", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif)"
        )
        if paths:
            self._import_sprites([Path(p) for p in paths])

    def _on_files_dropped(self, paths: List[Path]):
        self._import_sprites(paths)

    def _import_sprites(self, paths: List[Path]):
        if not self._project:
            return
        added = pb.add_sprites(self._project, paths)
        if self._current_group and added:
            for s in added:
                pb.assign_group(self._project, s["id"], self._current_group)
        pb.save_project(self._project)
        self._refresh_sidebar()
        self._refresh_grid()
        self._log.append(f"Added {len(added)} sprite(s)")

    # ── group sidebar signals ─────────────────────────────────────────────────

    def _on_group_selected(self, group_name):
        self._current_group = group_name
        self._inspector.clear()
        self._refresh_grid()

    def _on_sprites_dropped(self, sprite_ids: list, group_name):
        if not self._project:
            return
        for sid in sprite_ids:
            pb.assign_group(self._project, sid, group_name)
        pb.save_project(self._project)
        self._refresh_sidebar()
        self._refresh_grid()

    def _on_add_group(self):
        if not self._project:
            return
        name, ok = QInputDialog.getText(self, "New Group", "Group name:")
        if ok and name.strip():
            pb.add_group(self._project, name.strip())
            pb.save_project(self._project)
            self._refresh_sidebar()

    def _on_rename_group(self, old_name: str):
        if not self._project:
            return
        new_name, ok = QInputDialog.getText(self, "Rename Group", "New name:", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            pb.rename_group(self._project, old_name, new_name.strip())
            if self._current_group == old_name:
                self._current_group = new_name.strip()
            pb.save_project(self._project)
            self._refresh_sidebar()
            self._refresh_grid()

    def _on_remove_group(self, name: str):
        if not self._project:
            return
        reply = QMessageBox.question(
            self, "Remove Group",
            f"Remove group '{name}'? Sprites will move to Inbox.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            pb.remove_group(self._project, name)
            if self._current_group == name:
                self._current_group = None
            pb.save_project(self._project)
            self._refresh_sidebar()
            self._refresh_grid()

    # ── sprite inspector signals ──────────────────────────────────────────────

    def _on_sprite_selected(self, sprite_id: str):
        if not self._project:
            return
        s = pb.get_sprite(self._project, sprite_id)
        if s:
            self._inspector.set_sprite(
                self._project, s, pb.all_groups(self._project)
            )

    def _on_group_changed_for_sprite(self, sprite_id: str, group_name):
        if not self._project:
            return
        pb.assign_group(self._project, sprite_id, group_name)
        pb.save_project(self._project)
        self._refresh_sidebar()
        self._refresh_grid()

    def _on_weight_changed(self, sprite_id: str, weight: float):
        if not self._project:
            return
        s = pb.get_sprite(self._project, sprite_id)
        if s:
            s["weight"] = weight
            pb.save_project(self._project)

    def _on_pipeline_apply(self, sprite_id: str, pipeline_cfg: dict):
        if not self._project:
            return
        s = pb.get_sprite(self._project, sprite_id)
        if not s:
            return

        s["pipeline"] = pipeline_cfg
        pb.save_project(self._project)

        self._inspector.set_running(True)
        self._active_workers += 1

        worker = PipelineWorker(self._project, s)
        worker.signals.log.connect(self._log.append)
        worker.signals.result.connect(lambda r: self._on_pipeline_result(r, sprite_id))
        worker.signals.error.connect(self._log.append_error)
        worker.signals.finished.connect(self._on_pipeline_done)
        self._pool.start(worker)
        self._log.append(f"Pipeline running for {sprite_id}…")

    def _on_pipeline_result(self, result: dict, sprite_id: str):
        if not self._project:
            return
        s = pb.get_sprite(self._project, sprite_id)
        if s:
            self._grid.refresh_item(self._project, s)
            self._inspector.refresh_processed(self._project, s)

    def _on_pipeline_done(self):
        self._active_workers -= 1
        if self._active_workers <= 0:
            self._active_workers = 0
            self._inspector.set_running(False)
            self._log.append("Pipeline done.")

    # ── palette commands ──────────────────────────────────────────────────────

    def _on_palette_command(self, cmd: str):
        if not self._project or not self._current_group:
            if cmd in ("rebalance", "build", "verify", "export"):
                self._log.append("Select a group first.")
            return

        ctx = pb.make_normalizer_context(self._project)
        self._set_cmd_buttons_enabled(False)
        self._active_workers += 1

        if cmd == "rebalance":
            worker = NormalizerWorker(
                "rebalance", ctx,
                group=self._current_group,
                all_groups=False,
                force=False,
            )
        elif cmd == "build":
            worker = NormalizerWorker("build", ctx)
        elif cmd == "verify":
            worker = NormalizerWorker("verify", ctx)
        elif cmd == "export":
            worker = NormalizerWorker("export", ctx, group=None, all_groups=True)
        else:
            self._active_workers -= 1
            return

        worker.signals.log.connect(self._log.append)
        worker.signals.result.connect(self._on_palette_result)
        worker.signals.error.connect(self._log.append_error)
        worker.signals.finished.connect(self._on_palette_done)
        self._pool.start(worker)

    def _on_palette_result(self, payload: dict):
        rc = payload.get("rc", 0)
        cmd = payload.get("command", "")
        msg = f"{cmd} finished — {'ok' if rc == 0 else f'exit {rc}'}"
        (self._log.append_ok if rc == 0 else self._log.append)(msg)
        # Refresh palette swatch
        if self._project and self._current_group:
            colors = pb.load_palette(self._project, self._current_group) or []
            self._swatch.set_palette(colors)

    def _on_palette_done(self):
        self._active_workers -= 1
        if self._active_workers <= 0:
            self._active_workers = 0
            self._set_cmd_buttons_enabled(True)

    def _set_cmd_buttons_enabled(self, enabled: bool):
        for btn in self._cmd_btns.values():
            btn.setEnabled(enabled)
