import os
from typing import Dict, Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from backends.normalizer_backend import (
    all_groups,
    cfg,
    entities_in,
    load_manifest,
    load_pal,
    make_manifest_context,
)
from ui.widgets.image_viewer import ImageViewer
from ui.widgets.log_panel import LogPanel
from ui.widgets.palette_swatch import PaletteSwatch
from workers.normalizer_worker import NormalizerWorker


class NormalizerTab(QWidget):
    def __init__(self, pool: QThreadPool, parent=None):
        super().__init__(parent)
        self._pool = pool
        self._manifest: Optional[dict] = None
        self._fit_scores: Dict[str, float] = {}
        self._active_workers = 0
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # ── project directory bar ─────────────────────────────────────────────
        root.addWidget(self._build_project_bar())

        # ── main content splitter ─────────────────────────────────────────────
        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.addWidget(self._build_entity_panel())
        h_splitter.addWidget(self._build_right_panel())
        h_splitter.setStretchFactor(0, 1)
        h_splitter.setStretchFactor(1, 2)

        # ── command buttons ───────────────────────────────────────────────────
        root.addWidget(h_splitter)
        root.addWidget(self._build_command_bar())

        # ── log ───────────────────────────────────────────────────────────────
        self._log = LogPanel()
        self._log.setFixedHeight(150)
        root.addWidget(self._log)

    def _build_project_bar(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Project:"))
        self._project_label = QLabel("<i>no project loaded</i>")
        self._project_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._project_label)

        browse_btn = QPushButton("Open Project…")
        browse_btn.clicked.connect(self._browse_project)
        layout.addWidget(browse_btn)
        return w

    def _build_entity_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("<b>Entities</b>"))
        self._entity_list = QListWidget()
        self._entity_list.currentItemChanged.connect(self._on_entity_selected)
        layout.addWidget(self._entity_list)

        self._detail_label = QLabel()
        self._detail_label.setWordWrap(True)
        self._detail_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self._detail_label)
        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── group selector + palette swatch ──────────────────────────────────
        group_row = QHBoxLayout()
        group_row.addWidget(QLabel("Group:"))
        self._group_combo = QComboBox()
        self._group_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._group_combo.currentTextChanged.connect(self._on_group_changed)
        group_row.addWidget(self._group_combo)
        layout.addLayout(group_row)

        self._swatch = PaletteSwatch()
        layout.addWidget(self._swatch)

        # ── fit score table (simple label for now) ────────────────────────────
        layout.addWidget(QLabel("<b>Fit Scores</b>"))
        self._fit_list = QListWidget()
        self._fit_list.setFixedHeight(120)
        layout.addWidget(self._fit_list)

        # ── sprite preview ────────────────────────────────────────────────────
        layout.addWidget(QLabel("<b>Sprite Preview</b>"))
        self._sprite_viewer = ImageViewer()
        layout.addWidget(self._sprite_viewer)
        return w

    def _build_command_bar(self) -> QWidget:
        w = QGroupBox("Commands")
        layout = QHBoxLayout(w)

        self._cmd_buttons = {}
        for label, cmd in [
            ("Scan", "scan"),
            ("Rebalance Group", "rebalance"),
            ("Rebalance All", "rebalance_all"),
            ("Build", "build"),
            ("Verify", "verify"),
            ("Export All", "export"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked=False, c=cmd: self._run_command(c))
            layout.addWidget(btn)
            self._cmd_buttons[cmd] = btn

        self._force_check = QCheckBox("Force rebalance locked groups")
        layout.addWidget(self._force_check)
        return w

    # ── project loading ───────────────────────────────────────────────────────

    def _browse_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Project Root")
        if not directory:
            return
        self._load_project(directory)

    def _load_project(self, directory: str):
        manifest_path = os.path.join(directory, "palettes.yaml")
        input_dir = os.path.join(directory, "sprites_src")
        output_dir = os.path.join(directory, "build")
        palettes_dir = os.path.join(directory, "palettes")

        try:
            m = make_manifest_context(manifest_path, input_dir, output_dir, palettes_dir)
        except Exception as exc:
            self._log.append_error(f"Failed to load project: {exc}")
            return

        self._manifest = m
        self._project_label.setText(directory)
        self._log.append(f"Loaded project: {directory}")
        self._refresh_ui()

    def _refresh_ui(self):
        if self._manifest is None:
            return
        m = self._manifest

        # entity list
        self._entity_list.clear()
        for ent in m.get("entities", []):
            item = QListWidgetItem(ent["id"])
            item.setData(Qt.UserRole, ent)
            if not ent.get("group"):
                item.setForeground(QColor("#ffaa00"))
            self._entity_list.addItem(item)

        # group combo
        self._group_combo.blockSignals(True)
        current = self._group_combo.currentText()
        self._group_combo.clear()
        for g in all_groups(m):
            self._group_combo.addItem(g)
        idx = self._group_combo.findText(current)
        if idx >= 0:
            self._group_combo.setCurrentIndex(idx)
        self._group_combo.blockSignals(False)
        self._on_group_changed(self._group_combo.currentText())

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_group_changed(self, group: str):
        if self._manifest is None or not group:
            self._swatch.set_palette([])
            return
        pal = load_pal(self._manifest, group)
        if pal is not None:
            self._swatch.set_palette([tuple(c) for c in pal])
        else:
            self._swatch.set_palette([])
        self._refresh_fit_list(group)

    def _refresh_fit_list(self, group: str):
        self._fit_list.clear()
        if self._manifest is None:
            return
        fit_warn = cfg(self._manifest, group, "fit_warn")
        for ent in entities_in(self._manifest, group):
            score = self._fit_scores.get(ent["id"])
            label = f"{ent['id']:28s}  fit={score:.4f}" if score is not None else f"{ent['id']}"
            item = QListWidgetItem(label)
            if score is not None and score > fit_warn:
                item.setForeground(QColor("#ff6b6b"))
            self._fit_list.addItem(item)

    def _on_entity_selected(self, current, _previous):
        if current is None:
            self._detail_label.clear()
            self._sprite_viewer.clear()
            return
        ent = current.data(Qt.UserRole)
        score = self._fit_scores.get(ent["id"])
        score_str = f"{score:.4f}" if score is not None else "n/a"
        self._detail_label.setText(
            f"<b>file:</b> {ent['file']}<br>"
            f"<b>group:</b> {ent.get('group') or '—'}<br>"
            f"<b>weight:</b> {ent.get('weight', 1.0)}<br>"
            f"<b>fit:</b> {score_str}"
        )
        if self._manifest:
            built_path = os.path.join(
                self._manifest["_output"], "sprites", ent["file"]
            )
            # PNG variant as fallback
            png_path = os.path.splitext(built_path)[0] + ".png"
            for candidate in [built_path, png_path]:
                if os.path.exists(candidate) and candidate.lower().endswith(".png"):
                    px = QPixmap(candidate)
                    if not px.isNull():
                        self._sprite_viewer.set_image(px)
                        return
        self._sprite_viewer.clear()

    def _run_command(self, cmd: str):
        if self._manifest is None:
            self._log.append_error("No project loaded. Open a project first.")
            return

        self._set_buttons_enabled(False)
        self._active_workers += 1

        if cmd == "rebalance":
            group = self._group_combo.currentText()
            worker = NormalizerWorker(
                "rebalance",
                self._manifest,
                group=group,
                all_groups=False,
                force=self._force_check.isChecked(),
            )
        elif cmd == "rebalance_all":
            worker = NormalizerWorker(
                "rebalance",
                self._manifest,
                group=None,
                all_groups=True,
                force=self._force_check.isChecked(),
            )
        elif cmd == "export":
            worker = NormalizerWorker(
                "export",
                self._manifest,
                group=None,
                all_groups=True,
            )
        else:
            worker = NormalizerWorker(cmd, self._manifest)

        worker.signals.log.connect(self._log.append)
        worker.signals.result.connect(self._on_result)
        worker.signals.error.connect(self._log.append_error)
        worker.signals.finished.connect(self._on_worker_done)
        self._pool.start(worker)

    def _on_result(self, payload: dict):
        rc = payload["rc"]
        cmd = payload["command"]
        self._fit_scores.update(payload.get("fit_scores", {}))
        m = payload.get("manifest")
        if m is not None:
            # adopt the post-command manifest (scan may have added entities)
            m_clean = {k: v for k, v in m.items() if not k.startswith("_")}
            # re-inject runtime keys from the current manifest
            if self._manifest:
                for key in ("_path", "_input", "_output", "_palettes"):
                    m[key] = self._manifest[key]
            self._manifest = m
            self._refresh_ui()

        status = "ok" if rc == 0 else f"exit {rc}"
        msg = f"{cmd} finished — {status}"
        (self._log.append_ok if rc == 0 else self._log.append)(msg)

    def _on_worker_done(self):
        self._active_workers -= 1
        if self._active_workers <= 0:
            self._active_workers = 0
            self._set_buttons_enabled(True)

    def _set_buttons_enabled(self, enabled: bool):
        for btn in self._cmd_buttons.values():
            btn.setEnabled(enabled)
