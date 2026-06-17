"""
Pipeline worker — runs normalize and/or resize on a single sprite.

Step order (non-destructive):
  1. normalize  original → processed/{id}_normalized.png
  2. resize     (normalized or original) → processed/{id}_resized_{W}x{H}.png

Each step is skipped if not enabled in the sprite's pipeline config.
"""

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal

from backends.forge_backend import convert as forge_convert, detect_pixel_size, center_sample
from backends.project_backend import (
    get_normalized_path,
    get_resized_path,
    get_original_path,
    get_resize_input,
)


class PipelineSignals(QObject):
    log = Signal(str)
    result = Signal(object)   # dict: {sprite_id, outputs: {step: Path}}
    error = Signal(str)
    finished = Signal()


class PipelineWorker(QRunnable):
    """
    Runs the enabled pipeline steps for one sprite.
    Pass steps=None to run all enabled steps; or pass ['normalize'] / ['resize']
    to run a single step.
    """

    def __init__(self, project: dict, sprite: dict, steps=None):
        super().__init__()
        self.signals = PipelineSignals()
        self._project = project
        self._sprite = sprite
        self._steps = steps  # None = all enabled steps
        self.setAutoDelete(True)

    def run(self):
        sprite = self._sprite
        project = self._project
        pipe = sprite.get("pipeline", {})
        d = project["_dir"]
        sid = sprite["id"]
        outputs = {}

        try:
            run_normalize = "normalize" in (self._steps or []) or (
                self._steps is None and pipe.get("normalize", {}).get("enabled")
            )
            run_resize = "resize" in (self._steps or []) or (
                self._steps is None and pipe.get("resize", {}).get("enabled")
            )

            # ── Step 1: normalize ─────────────────────────────────────────────
            if run_normalize:
                norm_cfg = pipe.get("normalize", {})
                src = get_original_path(project, sprite)
                out_path = get_normalized_path(d, sid)
                out_path.parent.mkdir(parents=True, exist_ok=True)

                result_path, _, _ = forge_convert(
                    input_path=src,
                    target_w=None,
                    target_h=None,
                    auto=norm_cfg.get("auto", True),
                    colors=None,
                    output_path=out_path,
                    preview_scale=1,
                    log=self.signals.log.emit,
                )
                outputs["normalize"] = result_path
                self.signals.log.emit(f"  normalized → {result_path.name}")

            # ── Step 2: resize ────────────────────────────────────────────────
            if run_resize:
                resize_cfg = pipe.get("resize", {})
                w = resize_cfg.get("width", 0)
                h = resize_cfg.get("height", 0)
                if not w or not h:
                    self.signals.log.emit("  resize skipped: W or H is 0")
                else:
                    src = get_resize_input(project, sprite)
                    out_path = get_resized_path(d, sid, w, h)
                    out_path.parent.mkdir(parents=True, exist_ok=True)

                    img = Image.open(src).convert("RGBA")
                    img = img.resize((w, h), Image.NEAREST)
                    img.save(out_path, "PNG")
                    outputs["resize"] = out_path
                    self.signals.log.emit(f"  resized → {out_path.name}")

            self.signals.result.emit({"sprite_id": sid, "outputs": outputs})

        except Exception as exc:
            self.signals.error.emit(f"{sid}: {exc}")
        finally:
            self.signals.finished.emit()
