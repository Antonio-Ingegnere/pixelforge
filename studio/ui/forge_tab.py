from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.image_viewer import ImageViewer
from ui.widgets.log_panel import LogPanel
from workers.forge_worker import ForgeWorker


class ForgeTab(QWidget):
    def __init__(self, pool: QThreadPool, parent=None):
        super().__init__(parent)
        self._pool = pool
        self._active_workers = 0
        self._build_ui()
        self.setAcceptDrops(True)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # ── top: file list + options side-by-side ────────────────────────────
        top_splitter = QSplitter(Qt.Horizontal)

        top_splitter.addWidget(self._build_file_panel())
        top_splitter.addWidget(self._build_options_panel())
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)

        # ── middle: before / after previews ──────────────────────────────────
        preview_splitter = QSplitter(Qt.Horizontal)
        self._before_viewer = ImageViewer("Before (source)")
        self._after_viewer = ImageViewer("After (pixel art)")
        preview_splitter.addWidget(self._before_viewer)
        preview_splitter.addWidget(self._after_viewer)

        # ── bottom: log ───────────────────────────────────────────────────────
        self._log = LogPanel()
        self._log.setFixedHeight(140)

        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(preview_splitter)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)

        root.addWidget(main_splitter)
        root.addWidget(self._log)

    def _build_file_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("<b>Input Files</b>")
        self._file_list = QListWidget()
        self._file_list.setSelectionMode(QListWidget.ExtendedSelection)
        self._file_list.currentItemChanged.connect(self._on_file_selected)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Files…")
        add_btn.clicked.connect(self._browse_files)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._file_list.clear)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addWidget(clear_btn)

        layout.addWidget(label)
        layout.addWidget(self._file_list)
        layout.addLayout(btn_row)
        return w

    def _build_options_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("<b>Options</b>"))

        # ── mode toggle ───────────────────────────────────────────────────────
        self._auto_check = QCheckBox("Auto-detect pixel grid")
        self._auto_check.setChecked(True)
        self._auto_check.toggled.connect(self._on_mode_toggle)
        layout.addWidget(self._auto_check)

        # ── stacked: auto options / manual options ────────────────────────────
        self._mode_stack = QStackedWidget()
        self._mode_stack.addWidget(self._build_auto_options())   # 0
        self._mode_stack.addWidget(self._build_manual_options()) # 1
        layout.addWidget(self._mode_stack)

        # ── shared options ────────────────────────────────────────────────────
        shared = QGroupBox("Common")
        sh_layout = QVBoxLayout(shared)

        colors_row = QHBoxLayout()
        colors_row.addWidget(QLabel("Colors (0 = off):"))
        self._colors_spin = QSpinBox()
        self._colors_spin.setRange(0, 256)
        self._colors_spin.setValue(0)
        self._colors_spin.setSpecialValueText("off")
        colors_row.addWidget(self._colors_spin)
        colors_row.addStretch()

        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("Preview scale:"))
        self._preview_spin = QSpinBox()
        self._preview_spin.setRange(1, 16)
        self._preview_spin.setValue(1)
        preview_row.addWidget(self._preview_spin)
        preview_row.addStretch()

        sh_layout.addLayout(colors_row)
        sh_layout.addLayout(preview_row)
        layout.addWidget(shared)

        # ── output ────────────────────────────────────────────────────────────
        out_group = QGroupBox("Output")
        out_layout = QHBoxLayout(out_group)
        self._same_dir_check = QCheckBox("Same directory as input")
        self._same_dir_check.setChecked(True)
        self._same_dir_check.toggled.connect(self._on_output_toggle)
        out_layout.addWidget(self._same_dir_check)
        layout.addWidget(out_group)

        # ── convert button ────────────────────────────────────────────────────
        self._convert_btn = QPushButton("Convert")
        self._convert_btn.setFixedHeight(36)
        self._convert_btn.clicked.connect(self._run_convert)
        layout.addWidget(self._convert_btn)

        layout.addStretch()
        return w

    def _build_auto_options(self) -> QWidget:
        w = QGroupBox("Auto mode")
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Upscale result to (optional):"))
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("W:"))
        self._auto_w = QSpinBox()
        self._auto_w.setRange(0, 4096)
        self._auto_w.setSpecialValueText("auto")
        size_row.addWidget(self._auto_w)
        size_row.addWidget(QLabel("H:"))
        self._auto_h = QSpinBox()
        self._auto_h.setRange(0, 4096)
        self._auto_h.setSpecialValueText("auto")
        size_row.addWidget(self._auto_h)
        size_row.addStretch()
        layout.addLayout(size_row)
        return w

    def _build_manual_options(self) -> QWidget:
        w = QGroupBox("Manual mode")
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Target size:"))
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("W:"))
        self._manual_w = QSpinBox()
        self._manual_w.setRange(0, 4096)
        self._manual_w.setSpecialValueText("—")
        size_row.addWidget(self._manual_w)
        size_row.addWidget(QLabel("H:"))
        self._manual_h = QSpinBox()
        self._manual_h.setRange(0, 4096)
        self._manual_h.setSpecialValueText("—")
        size_row.addWidget(self._manual_h)
        size_row.addStretch()
        layout.addLayout(size_row)
        layout.addWidget(QLabel("Set W, H, or both. 0 = compute proportionally."))
        return w

    # ── drag & drop ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".png"):
                self._add_file(Path(path))
        event.acceptProposedAction()

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_mode_toggle(self, checked: bool):
        self._mode_stack.setCurrentIndex(0 if checked else 1)

    def _on_output_toggle(self, checked: bool):
        pass  # reserved for custom output path input if needed

    def _browse_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select images", "", "PNG Images (*.png)"
        )
        for p in paths:
            self._add_file(Path(p))

    def _add_file(self, path: Path):
        if not path.exists():
            return
        for i in range(self._file_list.count()):
            if self._file_list.item(i).data(Qt.UserRole) == path:
                return
        item = QListWidgetItem(path.name)
        item.setData(Qt.UserRole, path)
        item.setToolTip(str(path))
        self._file_list.addItem(item)

    def _remove_selected(self):
        for item in self._file_list.selectedItems():
            self._file_list.takeItem(self._file_list.row(item))

    def _on_file_selected(self, current, _previous):
        if current is None:
            self._before_viewer.clear()
            self._after_viewer.clear()
            return
        path: Path = current.data(Qt.UserRole)
        px = QPixmap(str(path))
        if not px.isNull():
            self._before_viewer.set_image(px)
        self._after_viewer.clear()

    def _run_convert(self):
        files = [
            self._file_list.item(i).data(Qt.UserRole)
            for i in range(self._file_list.count())
        ]
        if not files:
            self._log.append("No files to convert.")
            return

        auto = self._auto_check.isChecked()
        colors_val = self._colors_spin.value()
        colors = colors_val if colors_val >= 2 else None
        preview = self._preview_spin.value()

        if auto:
            aw = self._auto_w.value() or None
            ah = self._auto_h.value() or None
            target_w, target_h = aw, ah
        else:
            mw = self._manual_w.value() or None
            mh = self._manual_h.value() or None
            target_w, target_h = mw, mh
            if not target_w and not target_h:
                self._log.append_error("Manual mode: set at least one of W or H.")
                return

        self._convert_btn.setEnabled(False)
        self._active_workers = len(files)
        self._log.append(f"Converting {len(files)} file(s)…")

        for path in files:
            worker = ForgeWorker(
                input_path=path,
                target_w=target_w,
                target_h=target_h,
                auto=auto,
                colors=colors,
                output_path=None,
                preview_scale=preview,
            )
            worker.signals.log.connect(self._log.append)
            worker.signals.result.connect(self._on_result)
            worker.signals.error.connect(self._log.append_error)
            worker.signals.finished.connect(self._on_worker_done)
            self._pool.start(worker)

    def _on_result(self, payload):
        output_path, source_img, result_img = payload
        self._log.append_ok(f"→ {output_path}")
        # Update the after-viewer with the result of the currently selected file
        px = ImageViewer.pixmap_from_pil(result_img)
        self._after_viewer.set_image(px)
        # Also show the source in before-viewer at art resolution
        self._before_viewer.set_image(ImageViewer.pixmap_from_pil(source_img))

    def _on_worker_done(self):
        self._active_workers -= 1
        if self._active_workers <= 0:
            self._convert_btn.setEnabled(True)
            self._log.append("Done.")
