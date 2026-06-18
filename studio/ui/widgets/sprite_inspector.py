"""
SpriteInspector — pipeline settings panel (right column).

Pure settings: no image previews (those live in the center workspace).

Pipeline steps
  Normalize
  Resize sprite   (params collapse when unchecked)
  Resize canvas   (params collapse when unchecked)
  Remap to palette

Mapping section (visible when remap is enabled)
  Shows every unique source colour and the palette slot it maps to.
  Click any target swatch to reassign; amber arrow = user override.
  Changes save immediately and auto-re-run the remap step.

Signals
  pipeline_apply_requested(sprite_id, pipeline_config)
  group_changed(sprite_id, group_name | None)
  weight_changed(sprite_id, float)
  remap_override_changed(sprite_id, overrides_dict)
"""

from pathlib import Path
from typing import List, Optional

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.color_mapping_widget import ColorMappingWidget

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


class SpriteInspector(QWidget):
    pipeline_apply_requested = Signal(str, dict)
    group_changed            = Signal(str, object)
    weight_changed           = Signal(str, float)
    remap_override_changed   = Signal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sprite:  Optional[dict] = None
        self._project: Optional[dict] = None
        self._build_ui()
        self.clear()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.setObjectName("InspectorPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── title strip ───────────────────────────────────────────────────────
        title_bar = QWidget()
        title_bar.setObjectName("InspectorTitleBar")
        tbl = QHBoxLayout(title_bar)
        tbl.setContentsMargins(14, 10, 14, 10)
        self._title = QLabel("No selection")
        self._title.setObjectName("InspectorTitle")
        tbl.addWidget(self._title)
        root.addWidget(title_bar)

        # ── scrollable settings body ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 4, 12, 12)
        body_layout.setSpacing(0)

        # ── pipeline ──────────────────────────────────────────────────────────
        pipeline_box = QGroupBox("PIPELINE")
        pl = QVBoxLayout(pipeline_box)
        pl.setSpacing(6)
        pl.setContentsMargins(0, 8, 0, 4)

        self._norm_check = QCheckBox("Normalize")
        pl.addWidget(self._norm_check)

        # Resize sprite (collapsible params)
        self._scale_check = QCheckBox("Resize sprite")
        pl.addWidget(self._scale_check)

        self._scale_params = QWidget()
        sp = QVBoxLayout(self._scale_params)
        sp.setContentsMargins(20, 0, 0, 2)
        sp.setSpacing(4)
        scale_dims = QHBoxLayout()
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
        sp.addLayout(scale_dims)
        hint_scale = QLabel("0 = auto (preserves ratio)")
        hint_scale.setObjectName("HintLabel")
        sp.addWidget(hint_scale)
        self._scale_params.setVisible(False)
        self._scale_check.toggled.connect(self._scale_params.setVisible)
        pl.addWidget(self._scale_params)

        # Resize canvas (collapsible params)
        self._canvas_check = QCheckBox("Resize canvas")
        pl.addWidget(self._canvas_check)

        self._canvas_params = QWidget()
        cp = QVBoxLayout(self._canvas_params)
        cp.setContentsMargins(20, 0, 0, 2)
        cp.setSpacing(4)
        canvas_dims = QHBoxLayout()
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
        cp.addLayout(canvas_dims)
        anchor_row = QHBoxLayout()
        anchor_row.setSpacing(4)
        anchor_row.addWidget(QLabel("Anchor"))
        self._anchor_combo = QComboBox()
        self._anchor_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for label_text, value in [
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
            self._anchor_combo.addItem(label_text, value)
        anchor_row.addWidget(self._anchor_combo)
        cp.addLayout(anchor_row)
        self._canvas_params.setVisible(False)
        self._canvas_check.toggled.connect(self._canvas_params.setVisible)
        pl.addWidget(self._canvas_params)

        self._remap_check = QCheckBox("Remap to palette")
        pl.addWidget(self._remap_check)

        self._apply_btn = QPushButton("Apply Pipeline")
        self._apply_btn.setObjectName("PrimaryBtn")
        self._apply_btn.clicked.connect(self._on_apply)
        pl.addWidget(self._apply_btn)

        body_layout.addWidget(pipeline_box)

        # ── colour mapping ────────────────────────────────────────────────────
        self._mapping_box = QGroupBox("MAPPING")
        ml = QVBoxLayout(self._mapping_box)
        ml.setSpacing(4)
        ml.setContentsMargins(0, 8, 0, 4)

        self._mapping_hint = QLabel("Run pipeline to see mapping.")
        self._mapping_hint.setObjectName("HintLabel")
        ml.addWidget(self._mapping_hint)

        map_scroll = QScrollArea()
        map_scroll.setWidgetResizable(True)
        map_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        map_scroll.setMaximumHeight(110)
        map_scroll.setFrameShape(QScrollArea.NoFrame)
        self._color_map = ColorMappingWidget()
        self._color_map.override_changed.connect(self._on_override_changed)
        map_scroll.setWidget(self._color_map)
        ml.addWidget(map_scroll)

        self._mapping_box.setVisible(False)
        body_layout.addWidget(self._mapping_box)

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

        body_layout.addWidget(meta_box)
        body_layout.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    # ── public API ────────────────────────────────────────────────────────────

    def set_sprite(self, project: dict, sprite: dict, groups: List[str]):
        from backends.project_backend import (
            get_active_file, get_original_path, pipeline_status,
        )

        self._sprite  = sprite
        self._project = project
        self._title.setText(sprite["id"])
        self._title.setObjectName("InspectorTitleActive")
        self._title.style().unpolish(self._title)
        self._title.style().polish(self._title)

        # Pipeline config
        pipe   = sprite.get("pipeline", {})
        norm   = pipe.get("normalize",     {})
        scale  = pipe.get("resize_sprite", {})
        canvas = pipe.get("resize_canvas", {})
        remap  = pipe.get("remap_palette", {})

        for widget, val in [
            (self._norm_check,   norm.get("enabled", False)),
            (self._scale_check,  scale.get("enabled", False)),
            (self._canvas_check, canvas.get("enabled", False)),
            (self._remap_check,  remap.get("enabled", False)),
        ]:
            widget.blockSignals(True)
            widget.setChecked(val)
            widget.blockSignals(False)

        self._scale_params.setVisible(scale.get("enabled", False))
        self._canvas_params.setVisible(canvas.get("enabled", False))

        for widget, val in [
            (self._scale_w,   scale.get("width",  64)),
            (self._scale_h,   scale.get("height",  0)),
            (self._canvas_w,  canvas.get("width",  64)),
            (self._canvas_h,  canvas.get("height", 64)),
        ]:
            widget.blockSignals(True)
            widget.setValue(val)
            widget.blockSignals(False)

        anchor = canvas.get("anchor", "center")
        self._anchor_combo.blockSignals(True)
        self._anchor_combo.setCurrentIndex(
            max(0, self._anchor_combo.findData(anchor))
        )
        self._anchor_combo.blockSignals(False)

        # Group / weight
        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        self._group_combo.addItem("— none —", None)
        for g in groups:
            self._group_combo.addItem(g, g)
        idx = self._group_combo.findData(sprite.get("group"))
        self._group_combo.setCurrentIndex(max(0, idx))
        self._group_combo.blockSignals(False)

        self._weight_spin.blockSignals(True)
        self._weight_spin.setValue(sprite.get("weight", 1.0))
        self._weight_spin.blockSignals(False)

        # Info label
        active = get_active_file(project, sprite)
        status = pipeline_status(project, sprite)
        try:
            orig_img  = Image.open(get_original_path(project, sprite))
            orig_size = f"{orig_img.width}×{orig_img.height}"
        except Exception:
            orig_size = "?"
        try:
            act_img  = Image.open(active)
            act_size = f"{act_img.width}×{act_img.height}"
        except Exception:
            act_size = "?"
        self._info_label.setText(
            f"{sprite['file']}  |  {orig_size} → {act_size}  |  {status}"
        )

        self._apply_btn.setEnabled(True)
        self._refresh_mapping()

    def refresh_processed(self, project: dict, sprite: dict):
        """Update info label and mapping after a pipeline run."""
        from backends.project_backend import get_active_file, pipeline_status, get_original_path

        active = get_active_file(project, sprite)
        status = pipeline_status(project, sprite)
        try:
            orig_img  = Image.open(get_original_path(project, sprite))
            orig_size = f"{orig_img.width}×{orig_img.height}"
        except Exception:
            orig_size = "?"
        try:
            act_img  = Image.open(active)
            act_size = f"{act_img.width}×{act_img.height}"
        except Exception:
            act_size = "?"
        self._info_label.setText(
            f"{sprite['file']}  |  {orig_size} → {act_size}  |  {status}"
        )
        self._refresh_mapping()

    def clear(self):
        self._sprite  = None
        self._project = None
        self._title.setText("No selection")
        self._title.setObjectName("InspectorTitle")
        self._title.style().unpolish(self._title)
        self._title.style().polish(self._title)
        self._info_label.clear()
        self._apply_btn.setEnabled(False)
        self._color_map.clear()
        self._mapping_box.setVisible(False)

    def set_running(self, running: bool):
        self._apply_btn.setEnabled(not running and self._sprite is not None)
        self._apply_btn.setText("Running…" if running else "Apply Pipeline")

    # ── mapping refresh ───────────────────────────────────────────────────────

    def _refresh_mapping(self):
        if not self._sprite or not self._project:
            self._mapping_box.setVisible(False)
            return

        pipe = self._sprite.get("pipeline", {})
        if not pipe.get("remap_palette", {}).get("enabled"):
            self._mapping_box.setVisible(False)
            return

        from backends.project_backend import load_palette, get_remap_input
        from backends.remap import compute_mapping

        group   = self._sprite.get("group")
        palette = load_palette(self._project, group) if group else None

        if not palette:
            self._mapping_hint.setText("No palette — assign sprite to a group and run Rebalance.")
            self._color_map.clear()
            self._mapping_box.setVisible(True)
            return

        try:
            src_path = get_remap_input(self._project, self._sprite)
            img      = Image.open(src_path).convert("RGBA")
            overrides = pipe.get("remap_palette", {}).get("overrides", {})
            mapping   = compute_mapping(img, palette, overrides)
        except Exception as e:
            self._mapping_hint.setText(f"Could not compute mapping: {e}")
            self._color_map.clear()
            self._mapping_box.setVisible(True)
            return

        if not mapping:
            self._mapping_hint.setText("No visible pixels.")
            self._color_map.clear()
            self._mapping_box.setVisible(True)
            return

        ov_keys = set(overrides.keys())
        pairs = []
        for src_t, tgt_t in sorted(mapping.items(), key=lambda kv: sum(kv[0])):
            src_hex = f"{src_t[0]:02x}{src_t[1]:02x}{src_t[2]:02x}"
            is_ovr  = src_hex in ov_keys
            pairs.append((src_t, tgt_t, is_ovr))

        self._mapping_hint.setVisible(False)
        self._color_map.set_data(pairs, palette)
        self._mapping_box.setVisible(True)

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_apply(self):
        if not self._sprite:
            return
        pipeline_cfg = {
            "normalize":     {"enabled": self._norm_check.isChecked(),   "auto": True},
            "resize_sprite": {
                "enabled": self._scale_check.isChecked(),
                "width":   self._scale_w.value(),
                "height":  self._scale_h.value(),
            },
            "resize_canvas": {
                "enabled": self._canvas_check.isChecked(),
                "width":   self._canvas_w.value(),
                "height":  self._canvas_h.value(),
                "anchor":  self._anchor_combo.currentData(),
            },
            "remap_palette": {
                "enabled":   self._remap_check.isChecked(),
                "overrides": self._sprite.get("pipeline", {})
                                         .get("remap_palette", {})
                                         .get("overrides", {}),
            },
        }
        self.pipeline_apply_requested.emit(self._sprite["id"], pipeline_cfg)

    def _on_group_changed(self, _idx):
        if self._sprite:
            self.group_changed.emit(self._sprite["id"], self._group_combo.currentData())

    def _on_weight_changed(self):
        if self._sprite:
            self.weight_changed.emit(self._sprite["id"], self._weight_spin.value())

    def _on_override_changed(self, src_hex: str, tgt_hex: str):
        if not self._sprite:
            return
        pipe      = self._sprite.setdefault("pipeline", {})
        remap_cfg = pipe.setdefault("remap_palette", {"enabled": True, "overrides": {}})
        overrides = remap_cfg.setdefault("overrides", {})

        if tgt_hex:
            overrides[src_hex] = tgt_hex
        else:
            overrides.pop(src_hex, None)

        self.remap_override_changed.emit(self._sprite["id"], dict(overrides))
