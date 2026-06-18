"""
SpriteInspector — per-sprite detail panel.

Shows:
  - Original vs. active (processed) image side-by-side
  - Pipeline controls: Normalize and Resize checkboxes + params
  - Group assignment dropdown + weight
  - [Apply Pipeline] button

Emits:
  pipeline_apply_requested(sprite_id, pipeline_config)
  group_changed(sprite_id, group_name | None)
  weight_changed(sprite_id, float)
"""

import io
from pathlib import Path
from typing import List, Optional

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

ANCHORS = {
    "center":        (0.5, 0.5),
    "top-left":      (0.0, 0.0),
    "top-center":    (0.5, 0.0),
    "top-right":     (1.0, 0.0),
    "middle-left":   (0.0, 0.5),
    "middle-right":  (1.0, 0.5),
    "bottom-left":   (0.0, 1.0),
    "bottom-center": (0.5, 1.0),
    "bottom-right":  (1.0, 1.0),
}

from ui.widgets.image_viewer import ImageViewer


def _pil_to_pixmap(path: Path) -> Optional[QPixmap]:
    try:
        img = Image.open(path).convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        px = QPixmap()
        px.loadFromData(buf.read())
        return px
    except Exception:
        return None


class SpriteInspector(QWidget):
    pipeline_apply_requested = Signal(str, dict)   # (sprite_id, pipeline_cfg)
    group_changed = Signal(str, object)             # (sprite_id, group | None)
    weight_changed = Signal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sprite: Optional[dict] = None
        self._project: Optional[dict] = None
        self._build_ui()
        self.clear()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.setObjectName("InspectorPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(0)

        self._title = QLabel("Select a sprite")
        self._title.setObjectName("InspectorTitle")
        root.addWidget(self._title)

        # ── previews ──────────────────────────────────────────────────────────
        preview_splitter = QSplitter(Qt.Horizontal)
        preview_splitter.setHandleWidth(1)
        preview_splitter.setFixedHeight(130)
        self._original_view = ImageViewer("Original")
        self._processed_view = ImageViewer("Processed")
        preview_splitter.addWidget(self._original_view)
        preview_splitter.addWidget(self._processed_view)
        root.addWidget(preview_splitter)

        # ── pipeline ──────────────────────────────────────────────────────────
        pipeline_box = QGroupBox("PIPELINE")
        pipeline_layout = QVBoxLayout(pipeline_box)
        pipeline_layout.setSpacing(6)
        pipeline_layout.setContentsMargins(0, 8, 0, 4)

        # Step 1 — Normalize
        self._norm_check = QCheckBox("1 · Normalize")
        pipeline_layout.addWidget(self._norm_check)

        # Step 2 — Resize sprite
        self._scale_check = QCheckBox("2 · Resize sprite")
        pipeline_layout.addWidget(self._scale_check)

        scale_dims = QHBoxLayout()
        scale_dims.setContentsMargins(20, 0, 0, 0)
        scale_dims.setSpacing(4)
        scale_dims.addWidget(QLabel("W"))
        self._scale_w = QSpinBox()
        self._scale_w.setRange(0, 4096)
        self._scale_w.setValue(64)
        self._scale_w.setFixedWidth(58)
        self._scale_w.setSpecialValueText("auto")
        scale_dims.addWidget(self._scale_w)
        scale_dims.addWidget(QLabel("H"))
        self._scale_h = QSpinBox()
        self._scale_h.setRange(0, 4096)
        self._scale_h.setValue(0)
        self._scale_h.setFixedWidth(58)
        self._scale_h.setSpecialValueText("auto")
        scale_dims.addWidget(self._scale_h)
        scale_dims.addStretch()
        pipeline_layout.addLayout(scale_dims)

        hint = QLabel("0 = auto (preserves ratio)")
        hint.setObjectName("HintLabel")
        hint.setContentsMargins(20, 0, 0, 0)
        pipeline_layout.addWidget(hint)

        # Step 3 — Resize canvas
        self._canvas_check = QCheckBox("3 · Resize canvas")
        pipeline_layout.addWidget(self._canvas_check)

        canvas_dims = QHBoxLayout()
        canvas_dims.setContentsMargins(20, 0, 0, 0)
        canvas_dims.setSpacing(4)
        canvas_dims.addWidget(QLabel("W"))
        self._canvas_w = QSpinBox()
        self._canvas_w.setRange(1, 4096)
        self._canvas_w.setValue(64)
        self._canvas_w.setFixedWidth(58)
        canvas_dims.addWidget(self._canvas_w)
        canvas_dims.addWidget(QLabel("H"))
        self._canvas_h = QSpinBox()
        self._canvas_h.setRange(1, 4096)
        self._canvas_h.setValue(64)
        self._canvas_h.setFixedWidth(58)
        canvas_dims.addWidget(self._canvas_h)
        canvas_dims.addStretch()
        pipeline_layout.addLayout(canvas_dims)

        anchor_row = QHBoxLayout()
        anchor_row.setContentsMargins(20, 0, 0, 0)
        anchor_row.setSpacing(4)
        anchor_row.addWidget(QLabel("Anchor"))
        self._anchor_combo = QComboBox()
        self._anchor_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for label, value in [
            ("Center",        "center"),
            ("Top-Left",      "top-left"),
            ("Top-Center",    "top-center"),
            ("Top-Right",     "top-right"),
            ("Middle-Left",   "middle-left"),
            ("Middle-Right",  "middle-right"),
            ("Bottom-Left",   "bottom-left"),
            ("Bottom-Center", "bottom-center"),
            ("Bottom-Right",  "bottom-right"),
        ]:
            self._anchor_combo.addItem(label, value)
        anchor_row.addWidget(self._anchor_combo)
        pipeline_layout.addLayout(anchor_row)

        self._apply_btn = QPushButton("Apply Pipeline")
        self._apply_btn.setObjectName("PrimaryBtn")
        self._apply_btn.clicked.connect(self._on_apply)
        self._apply_btn.setMinimumHeight(28)
        pipeline_layout.addWidget(self._apply_btn)

        root.addWidget(pipeline_box)

        # ── properties ────────────────────────────────────────────────────────
        meta_box = QGroupBox("PROPERTIES")
        meta_layout = QFormLayout(meta_box)
        meta_layout.setContentsMargins(0, 8, 0, 4)
        meta_layout.setSpacing(6)
        meta_layout.setLabelAlignment(Qt.AlignRight)

        self._group_combo = QComboBox()
        self._group_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._group_combo.currentIndexChanged.connect(self._on_group_changed)
        meta_layout.addRow("Group", self._group_combo)

        self._weight_spin = QDoubleSpinBox()
        self._weight_spin.setRange(0.01, 10.0)
        self._weight_spin.setSingleStep(0.1)
        self._weight_spin.setValue(1.0)
        self._weight_spin.setDecimals(2)
        self._weight_spin.editingFinished.connect(self._on_weight_changed)
        meta_layout.addRow("Weight", self._weight_spin)

        self._info_label = QLabel()
        self._info_label.setObjectName("HintLabel")
        self._info_label.setWordWrap(True)
        meta_layout.addRow("File", self._info_label)

        root.addWidget(meta_box)
        root.addStretch()

    # ── public API ────────────────────────────────────────────────────────────

    def set_sprite(self, project: dict, sprite: dict, groups: List[str]):
        from backends.project_backend import get_active_file, get_original_path, pipeline_status

        self._sprite = sprite
        self._project = project
        self._title.setText(sprite["id"])
        self._title.setObjectName("InspectorTitleActive")
        self._title.style().unpolish(self._title)
        self._title.style().polish(self._title)

        # Previews
        orig_px = _pil_to_pixmap(get_original_path(project, sprite))
        if orig_px:
            self._original_view.set_image(orig_px)

        active = get_active_file(project, sprite)
        active_px = _pil_to_pixmap(active)
        if active_px:
            self._processed_view.set_image(active_px)
        else:
            self._processed_view.clear()

        # Pipeline config
        pipe = sprite.get("pipeline", {})
        norm = pipe.get("normalize", {})
        scale = pipe.get("resize_sprite", {})
        canvas = pipe.get("resize_canvas", {})

        self._norm_check.blockSignals(True)
        self._norm_check.setChecked(norm.get("enabled", False))
        self._norm_check.blockSignals(False)

        self._scale_check.blockSignals(True)
        self._scale_check.setChecked(scale.get("enabled", False))
        self._scale_check.blockSignals(False)

        self._scale_w.blockSignals(True)
        self._scale_w.setValue(scale.get("width", 64))
        self._scale_w.blockSignals(False)

        self._scale_h.blockSignals(True)
        self._scale_h.setValue(scale.get("height", 0))
        self._scale_h.blockSignals(False)

        self._canvas_check.blockSignals(True)
        self._canvas_check.setChecked(canvas.get("enabled", False))
        self._canvas_check.blockSignals(False)

        self._canvas_w.blockSignals(True)
        self._canvas_w.setValue(canvas.get("width", 64))
        self._canvas_w.blockSignals(False)

        self._canvas_h.blockSignals(True)
        self._canvas_h.setValue(canvas.get("height", 64))
        self._canvas_h.blockSignals(False)

        anchor = canvas.get("anchor", "center")
        self._anchor_combo.blockSignals(True)
        aidx = self._anchor_combo.findData(anchor)
        self._anchor_combo.setCurrentIndex(max(0, aidx))
        self._anchor_combo.blockSignals(False)

        # Group combo
        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        self._group_combo.addItem("— none —", None)
        for g in groups:
            self._group_combo.addItem(g, g)
        current_group = sprite.get("group")
        idx = self._group_combo.findData(current_group)
        self._group_combo.setCurrentIndex(max(0, idx))
        self._group_combo.blockSignals(False)

        # Weight
        self._weight_spin.blockSignals(True)
        self._weight_spin.setValue(sprite.get("weight", 1.0))
        self._weight_spin.blockSignals(False)

        # Info
        status = pipeline_status(project, sprite)
        try:
            orig_img = Image.open(get_original_path(project, sprite))
            orig_size = f"{orig_img.width}×{orig_img.height}"
        except Exception:
            orig_size = "?"
        try:
            act_img = Image.open(active)
            act_size = f"{act_img.width}×{act_img.height}"
        except Exception:
            act_size = "?"
        self._info_label.setText(
            f"{sprite['file']}  |  {orig_size} → {act_size}  |  {status}"
        )

        self._apply_btn.setEnabled(True)

    def refresh_processed(self, project: dict, sprite: dict):
        """Reload only the processed preview (called after pipeline run)."""
        from backends.project_backend import get_active_file, pipeline_status, get_original_path

        active = get_active_file(project, sprite)
        px = _pil_to_pixmap(active)
        if px:
            self._processed_view.set_image(px)

        status = pipeline_status(project, sprite)
        try:
            orig_img = Image.open(get_original_path(project, sprite))
            orig_size = f"{orig_img.width}×{orig_img.height}"
        except Exception:
            orig_size = "?"
        try:
            act_img = Image.open(active)
            act_size = f"{act_img.width}×{act_img.height}"
        except Exception:
            act_size = "?"
        self._info_label.setText(
            f"{sprite['file']}  |  {orig_size} → {act_size}  |  {status}"
        )

    def clear(self):
        self._sprite = None
        self._project = None
        self._title.setText("No selection")
        self._title.setObjectName("InspectorTitle")
        self._title.style().unpolish(self._title)
        self._title.style().polish(self._title)
        self._original_view.clear()
        self._processed_view.clear()
        self._info_label.clear()
        self._apply_btn.setEnabled(False)

    def set_running(self, running: bool):
        self._apply_btn.setEnabled(not running and self._sprite is not None)
        self._apply_btn.setText("Running…" if running else "Apply Pipeline")

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_apply(self):
        if not self._sprite:
            return
        pipeline_cfg = {
            "normalize": {
                "enabled": self._norm_check.isChecked(),
                "auto": True,
            },
            "resize_sprite": {
                "enabled": self._scale_check.isChecked(),
                "width": self._scale_w.value(),
                "height": self._scale_h.value(),
            },
            "resize_canvas": {
                "enabled": self._canvas_check.isChecked(),
                "width": self._canvas_w.value(),
                "height": self._canvas_h.value(),
                "anchor": self._anchor_combo.currentData(),
            },
        }
        self.pipeline_apply_requested.emit(self._sprite["id"], pipeline_cfg)

    def _on_group_changed(self, _idx):
        if self._sprite:
            group = self._group_combo.currentData()
            self.group_changed.emit(self._sprite["id"], group)

    def _on_weight_changed(self):
        if self._sprite:
            self.weight_changed.emit(self._sprite["id"], self._weight_spin.value())
